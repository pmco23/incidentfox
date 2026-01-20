"""
Cost tracking for ingestion pipeline.

Tracks API costs across extractors and processors.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class CostRecord:
    """Record of a single cost event."""

    timestamp: datetime
    source_id: str
    source_url: str
    operation: str  # "image_processing", "audio_transcription", etc.
    model: Optional[str]
    cost_usd: float
    duration_seconds: Optional[float] = None
    metadata: Dict = field(default_factory=dict)


class CostTracker:
    """Tracks costs across ingestion operations."""

    def __init__(self, log_file: Optional[Path] = None):
        """
        Initialize cost tracker.

        Args:
            log_file: Optional file to persist cost records
        """
        self.log_file = log_file
        self.records: List[CostRecord] = []

        # Load existing records if log file exists
        if self.log_file and self.log_file.exists():
            self._load_records()

    def record_cost(
        self,
        source_id: str,
        source_url: str,
        operation: str,
        cost_usd: float,
        model: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        metadata: Optional[Dict] = None,
    ):
        """Record a cost event."""
        record = CostRecord(
            timestamp=datetime.utcnow(),
            source_id=source_id,
            source_url=source_url,
            operation=operation,
            model=model,
            cost_usd=cost_usd,
            duration_seconds=duration_seconds,
            metadata=metadata or {},
        )
        self.records.append(record)

        # Persist if log file is set
        if self.log_file:
            self._save_record(record)

    def get_total_cost(self) -> float:
        """Get total cost across all records."""
        return sum(r.cost_usd for r in self.records)

    def get_cost_by_operation(self) -> Dict[str, float]:
        """Get cost breakdown by operation type."""
        breakdown: Dict[str, float] = {}
        for record in self.records:
            breakdown[record.operation] = (
                breakdown.get(record.operation, 0.0) + record.cost_usd
            )
        return breakdown

    def get_cost_by_model(self) -> Dict[str, float]:
        """Get cost breakdown by model."""
        breakdown: Dict[str, float] = {}
        for record in self.records:
            if record.model:
                breakdown[record.model] = (
                    breakdown.get(record.model, 0.0) + record.cost_usd
                )
        return breakdown

    def get_summary(self) -> Dict:
        """Get cost summary."""
        return {
            "total_cost_usd": self.get_total_cost(),
            "total_operations": len(self.records),
            "by_operation": self.get_cost_by_operation(),
            "by_model": self.get_cost_by_model(),
        }

    def _save_record(self, record: CostRecord):
        """Save a single record to log file."""
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "timestamp": record.timestamp.isoformat(),
                        "source_id": record.source_id,
                        "source_url": record.source_url,
                        "operation": record.operation,
                        "model": record.model,
                        "cost_usd": record.cost_usd,
                        "duration_seconds": record.duration_seconds,
                        "metadata": record.metadata,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    def _load_records(self):
        """Load records from log file."""
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                for line in f:
                    data = json.loads(line)
                    record = CostRecord(
                        timestamp=datetime.fromisoformat(data["timestamp"]),
                        source_id=data["source_id"],
                        source_url=data["source_url"],
                        operation=data["operation"],
                        model=data.get("model"),
                        cost_usd=data["cost_usd"],
                        duration_seconds=data.get("duration_seconds"),
                        metadata=data.get("metadata", {}),
                    )
                    self.records.append(record)
        except Exception:
            # If loading fails, start fresh
            pass
