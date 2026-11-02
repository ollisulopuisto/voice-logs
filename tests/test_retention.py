"""Säilytysaika: vanhat keskustelut poistetaan, ja asetus on asetusten lomakkeessa.

Ajo:  python3 tests/test_retention.py
"""
import ast
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "custom_components" / "voice_logs"
sys.path.insert(0, str(BASE))
from retention import expired_ids  # noqa: E402

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)


def rec(id_, days_ago=None, created_at=None):
    if created_at is None:
        created_at = (NOW - timedelta(days=days_ago)).isoformat()
    return {"id": id_, "created_at": created_at}


def main() -> int:
    v = []
    records = [
        rec("vanha", days_ago=100),
        rec("raja", days_ago=90),
        rec("tuore", days_ago=10),
        rec("rikki", created_at="ei-päivämäärää"),
        rec("tyhja", created_at=""),
    ]
    poistettavat = expired_ids(records, NOW, 90)
    if poistettavat != {"vanha", "rikki", "tyhja"}:
        v.append(f"väärät poistettavat (90 pv): {sorted(poistettavat)}")
    if expired_ids([rec("a", days_ago=40)], NOW, 30) != {"a"}:
        v.append("säilytysajan ylitys (40 pv > 30 pv) pitää poistaa")

    tree = ast.parse((BASE / "store.py").read_text(encoding="utf-8"))
    add = next(n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef) and n.name == "async_add")
    if "_prune_records" not in {x.attr for x in ast.walk(add) if isinstance(x, ast.Attribute)}:
        v.append("async_add pitää karsia säilytysajan jälkeen")

    init = (BASE / "__init__.py").read_text(encoding="utf-8")
    if "add_update_listener" not in init:
        v.append("__init__.py: asetusten muutos pitää vaikuttaa heti (add_update_listener)")

    cfg = (BASE / "config_flow.py").read_text(encoding="utf-8")
    if "retention_days" not in cfg:
        v.append("config_flow.py: retention_days puuttuu asetuksista")
    for kieli in ("en", "fi"):
        t = json.loads((BASE / "translations" / f"{kieli}.json").read_text(encoding="utf-8"))
        if "retention_days" not in json.dumps(t.get("options", {})):
            v.append(f"{kieli}.json: options.retention_days puuttuu")

    for x in v:
        print("VIRHE:", x)
    print("OK" if not v else f"{len(v)} virhettä")
    return 1 if v else 0


if __name__ == "__main__":
    sys.exit(main())
