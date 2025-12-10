#!/usr/bin/env python3
"""
Core models and result schemas for Tessera-2600.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Literal, Optional
import time

Status = Literal["found", "not_found", "error", "rate_limited", "invalid", "unknown"]


@dataclass(frozen=True)
class CheckResult:
    service: str
    phone: str
    status: Status
    details: Dict[str, Any]
    ts: float = time.time()
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RunSummary:
    run_id: str
    total_checked: int = 0
    found: int = 0
    errors: int = 0
    rate_limited: int = 0

    def update_with(self, result: CheckResult) -> None:
        self.total_checked += 1
        if result.status == "found":
            self.found += 1
        elif result.status == "error":
            self.errors += 1
        elif result.status == "rate_limited":
            self.rate_limited += 1
