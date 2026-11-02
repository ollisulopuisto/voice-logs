"""voice_logs/history/list palauttaa koko Assist-arkiston, joten vain ylläpitäjä saa lukea sen.

Tarkistus lukee lähdekoodin AST:lla, joten testi ei tarvitse Home Assistantia.
Ajo:  python3 tests/test_history_admin.py
"""
import ast
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "custom_components" / "voice_logs" / "__init__.py"


def decorator_names(fn: ast.FunctionDef) -> list[str]:
    names = []
    for d in fn.decorator_list:
        node = d.func if isinstance(d, ast.Call) else d
        if isinstance(node, ast.Attribute):
            names.append(node.attr)
        elif isinstance(node, ast.Name):
            names.append(node.id)
    return names


def main() -> int:
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    fn = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "websocket_get_history"), None)
    if fn is None:
        print("VIRHE: websocket_get_history puuttuu")
        return 1
    if "require_admin" not in decorator_names(fn):
        print("VIRHE: voice_logs/history/list ei vaadi ylläpitäjää (@websocket_api.require_admin puuttuu)")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
