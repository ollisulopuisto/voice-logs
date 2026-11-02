"""Piilotus-palvelut tarkistavat lukuoikeuden, ja asetuksissa on sallittujen käyttäjien valinta.

Ajo:  python3 tests/test_services_options.py
"""
import ast
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "custom_components" / "voice_logs"


def main() -> int:
    v = []
    tree = ast.parse((BASE / "__init__.py").read_text(encoding="utf-8"))
    for nimi in ("_async_hide_conversation", "_async_restore_conversation"):
        fn = next((n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == nimi), None)
        if fn is None:
            v.append(f"{nimi} puuttuu")
            continue
        kutsut = {x.func.id for x in ast.walk(fn) if isinstance(x, ast.Call) and isinstance(x.func, ast.Name)}
        if "_require_reader" not in kutsut:
            v.append(f"{nimi} ei tarkista lukuoikeutta (_require_reader)")
    cfg = (BASE / "config_flow.py").read_text(encoding="utf-8")
    if "async_get_options_flow" not in cfg or "allowed_user_ids" not in cfg:
        v.append("config_flow.py: options flow ja allowed_user_ids puuttuvat")
    for kieli in ("en", "fi"):
        t = json.loads((BASE / "translations" / f"{kieli}.json").read_text(encoding="utf-8"))
        if "allowed_user_ids" not in json.dumps(t.get("options", {})):
            v.append(f"{kieli}.json: options.allowed_user_ids puuttuu")
    for x in v:
        print("VIRHE:", x)
    print("OK" if not v else f"{len(v)} virhettä")
    return 1 if v else 0


if __name__ == "__main__":
    sys.exit(main())
