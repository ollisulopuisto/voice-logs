"""Säilytysaika: keskustelut vanhenevat, kun ne ovat vanhempia kuin asetettu määrä päiviä.

Pidetään ilman Home Assistant -importteja, jotta logiikka voidaan testata suoraan.
Tietue ilman luettavaa päivämäärää katsotaan vanhentuneeksi (yksityisyys ensin).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Iterable


def _parse(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()  # naive timestamps are local time
    return parsed


def expired_ids(records: Iterable[dict[str, Any]], now: datetime, days: int) -> set[str]:
    """IDs of records older than `days` days (or without a readable date)."""
    limit = timedelta(days=days)
    expired: set[str] = set()
    for record in records:
        created = _parse(record.get("created_at"))
        if created is None or now - created > limit:
            expired.add(str(record.get("id") or record.get("run_id") or ""))
    expired.discard("")
    return expired
