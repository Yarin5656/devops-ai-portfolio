"""
Schemas for incident data structures and analysis results.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class AnalysisMode(str, Enum):
    RULE_BASED = "rule-based"
    AI_ENHANCED = "ai-enhanced"


@dataclass
class Incident:
    title: str
    description: str
    service: str
    environment: str
    timestamp: str
    logs: List[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


@dataclass
class AnalysisResult:
    root_cause: str
    severity: Severity
    recommended_fix: str
    runbook_steps: List[str]
    analysis_mode: AnalysisMode
    detected_categories: List[str] = field(default_factory=list)
    confidence_score: float = 0.0
    ai_insights: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "root_cause": self.root_cause,
            "severity": self.severity.value,
            "recommended_fix": self.recommended_fix,
            "runbook_steps": self.runbook_steps,
            "analysis_mode": self.analysis_mode.value,
            "detected_categories": self.detected_categories,
            "confidence_score": round(self.confidence_score, 2),
            "ai_insights": self.ai_insights,
        }
