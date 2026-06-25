from __future__ import annotations

"""
Chaos Tester -- Data models for test results
"""

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from .impact_estimator import (
    estimate_dollar_impact,
    estimate_fix_time,
    format_dollar_impact,
)


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class TestStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class TestResult:
    """A single test outcome."""
    test_id: str = ""
    module: str = ""              # availability | links | forms | chaos | auth | security
    name: str = ""
    description: str = ""
    status: TestStatus = TestStatus.PASSED
    severity: Severity = Severity.INFO
    url: str = ""
    details: str = ""
    recommendation: str = ""
    screenshot: Optional[str] = None
    duration_ms: float = 0
    timestamp: str = ""
    logs: list = field(default_factory=list)

    def __post_init__(self):
        if not self.test_id:
            self.test_id = str(uuid.uuid4())[:8]
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self):
        # Business-impact & fix-effort estimates, derived from severity + module.
        # See impact_estimator.py for the (tunable, documented) model. These are
        # what the report UI shows as a finding's "$ impact" and "build time to
        # fix" -- the latter REPLACES showing raw test execution time.
        sev = self.severity.value
        dollar_impact = estimate_dollar_impact(sev, self.module)
        fix = estimate_fix_time(sev, self.module)
        return {
            "test_id": self.test_id,
            "module": self.module,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "severity": sev,
            "url": self.url,
            "details": self.details,
            "recommendation": self.recommendation,
            "screenshot": self.screenshot,
            "duration_ms": round(self.duration_ms, 1),
            "timestamp": self.timestamp,
            "logs": self.logs,
            # --- estimates (see impact_estimator.py) ---
            "dollar_impact": dollar_impact,
            "dollar_impact_display": format_dollar_impact(dollar_impact),
            "fix_time": fix["label"],
            "fix_time_minutes": fix["minutes"],
        }


@dataclass
class TestRun:
    """Aggregate object for a full test sweep."""
    run_id: str = ""
    base_url: str = ""
    environment: str = ""
    started_at: str = ""
    finished_at: str = ""
    duration_s: float = 0
    results: list = field(default_factory=list)   # list[TestResult]
    status: str = "pending"  # pending | running | completed | failed

    def __post_init__(self):
        if not self.run_id:
            self.run_id = str(uuid.uuid4())[:12]
        if not self.started_at:
            self.started_at = datetime.utcnow().isoformat()
        self.performance_metrics = {}
        self.ai_visibility = {}

    @property
    def passed(self):
        return [r for r in self.results if r.status == TestStatus.PASSED]

    @property
    def failed(self):
        return [r for r in self.results if r.status == TestStatus.FAILED]

    @property
    def warnings(self):
        return [r for r in self.results if r.status == TestStatus.WARNING]

    @property
    def errors(self):
        return [r for r in self.results if r.status == TestStatus.ERROR]

    @property
    def summary(self):
        total = len(self.results)
        return {
            "total": total,
            "passed": len(self.passed),
            "failed": len(self.failed),
            "warnings": len(self.warnings),
            "errors": len(self.errors),
            "pass_rate": round(len(self.passed) / total * 100, 1) if total else 0,
        }

    def to_dict(self):
        return {
            "run_id": self.run_id,
            "base_url": self.base_url,
            "environment": self.environment,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_s": round(self.duration_s, 1),
            "status": self.status,
            "summary": self.summary,
            "results": [r.to_dict() for r in self.results],
            "performance_metrics": self.performance_metrics,
            "ai_visibility": self.ai_visibility,
        }
