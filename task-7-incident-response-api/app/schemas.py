from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Category(str, Enum):
    NETWORK = "network"
    PERMISSIONS = "permissions"
    DEPENDENCY = "dependency"
    TIMEOUT = "timeout"
    RESOURCE = "resource"
    UNKNOWN = "unknown"


class AnalysisMode(str, Enum):
    RULE_BASED = "rule_based"
    AI_ENHANCED = "ai_enhanced"


class IncidentRequest(BaseModel):
    source: str = Field(..., description="Service or component that generated the incident (e.g. nginx, postgres)")
    environment: str = Field(..., description="Deployment environment (e.g. production, staging, dev)")
    log: str = Field(..., description="Raw log message or error text describing the incident")
    metadata: Optional[dict] = Field(default=None, description="Optional key-value metadata for additional context")


class IncidentResponse(BaseModel):
    category: Category
    severity: Severity
    root_cause: str
    recommended_fix: str
    runbook_steps: List[str]
    analysis_mode: AnalysisMode
    source: str
    environment: str


class HealthResponse(BaseModel):
    status: str
