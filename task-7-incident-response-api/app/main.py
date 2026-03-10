"""
Incident Response API — main application entry point.

FastAPI service that accepts incident/log payloads, classifies the problem
using a rule engine (with optional AI enrichment), and returns structured
remediation guidance including runbook steps.
"""

import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from app.schemas import IncidentRequest, IncidentResponse, HealthResponse, AnalysisMode
from app import rule_engine, runbook_engine, ai_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Incident Response API",
    description=(
        "Classifies infrastructure and application incidents from raw log messages "
        "and returns structured remediation guidance with SRE runbook steps."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.get("/health", response_model=HealthResponse, tags=["Ops"])
def health() -> HealthResponse:
    """Liveness probe — returns 200 OK when the service is running."""
    return HealthResponse(status="ok")


@app.post("/analyze-incident", response_model=IncidentResponse, tags=["Incident Analysis"])
def analyze_incident(payload: IncidentRequest) -> IncidentResponse:
    """
    Classify an incident and return remediation guidance.

    - Runs rule-based classification on the log message.
    - Optionally enriches the analysis with AI if ANTHROPIC_API_KEY is set.
    - Always returns runbook steps appropriate to the detected category.
    """
    logger.info(
        "Received incident | source=%s env=%s log_preview=%.80s",
        payload.source,
        payload.environment,
        payload.log,
    )

    # Step 1 — rule-based classification (always runs)
    result = rule_engine.classify(log=payload.log, source=payload.source)

    root_cause = result.root_cause
    recommended_fix = result.recommended_fix
    mode = AnalysisMode.RULE_BASED

    # Step 2 — optional AI enrichment
    if ai_engine.is_available():
        enriched = ai_engine.enrich(
            source=payload.source,
            environment=payload.environment,
            log=payload.log,
            rule_category=result.category.value,
            rule_root_cause=result.root_cause,
        )
        if enriched:
            root_cause = enriched["root_cause"]
            recommended_fix = enriched["recommended_fix"]
            mode = AnalysisMode.AI_ENHANCED
            logger.info("AI enrichment applied for incident from %s.", payload.source)

    # Step 3 — fetch runbook steps
    steps = runbook_engine.get_runbook(result.category)

    logger.info(
        "Analysis complete | category=%s severity=%s mode=%s",
        result.category.value,
        result.severity.value,
        mode.value,
    )

    return IncidentResponse(
        category=result.category,
        severity=result.severity,
        root_cause=root_cause,
        recommended_fix=recommended_fix,
        runbook_steps=steps,
        analysis_mode=mode,
        source=payload.source,
        environment=payload.environment,
    )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error. Check service logs."})
