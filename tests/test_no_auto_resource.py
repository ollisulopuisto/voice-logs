"""Integraatio ei lisää Lovelace-resursseja käyttäjän dashboardille itse. Kortti otetaan käyttöön
käsin (Asetukset > Dashboardit > Resurssit). Integraatio vain tarjoaa tiedoston.

Ajo:  python3 tests/test_no_auto_resource.py
"""
import ast
import sys
from pathlib import Path

INIT = Path(__file__).resolve().parent.parent / "custom_components" / "voice_logs" / "__init__.py"


def main() -> int:
    v = []
    tree = ast.parse(INIT.read_text(encoding="utf-8"))
    fn = next((n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "_async_register_card"), None)
    if fn is None:
        v.append("_async_register_card puuttuu")
    else:
        teksti = ast.unparse(fn)
        if "lovelace" in teksti or "async_create_item" in teksti or "async_update_item" in teksti:
            v.append("_async_register_card lisää Lovelace-resurssin käyttäjän puolesta; poista se")
        if "async_register_static_paths" not in teksti:
            v.append("tiedoston tarjoaminen (static path) puuttuu")
    for x in v:
        print("VIRHE:", x)
    print("OK" if not v else f"{len(v)} virhettä")
    return 1 if v else 0


if __name__ == "__main__":
    sys.exit(main())
