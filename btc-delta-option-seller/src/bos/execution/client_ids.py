from __future__ import annotations

from datetime import datetime


class ClientOrderIdGenerator:
    def __init__(self) -> None:
        self._issued: set[str] = set()

    def create(
        self,
        timestamp: datetime,
        structure: str,
        leg: str,
        phase: str,
        attempt: int,
    ) -> str:
        structure_code = "IC" if structure == "IRON_CONDOR" else "DS"
        value = f"BOS1-{phase[:1]}-{timestamp:%y%m%d%H%M}-{structure_code}-{leg[:2]}-{attempt}"
        if len(value) > 32:
            raise ValueError("client_order_id exceeds Delta's 32-character limit")
        if value in self._issued:
            raise ValueError("client_order_id reuse detected")
        self._issued.add(value)
        return value
