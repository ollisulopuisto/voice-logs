"""voice_logs/history/list: lukuoikeus tarkistetaan (ylläpitäjä tai sallittu käyttäjä), ja vastaus
sisältää aktiivisen vuoron ja viimeisimmän keskustelun (kortit lukevat sisällön vain täältä).

Tarkistus lukee lähdekoodin AST:lla, joten testi ei tarvitse Home Assistantia.
Ajo:  python3 tests/test_history_admin.py
"""
import ast
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "custom_components" / "voice_logs" / "__init__.py"


def main() -> int:
    v = []
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    fn = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "websocket_get_history"), None)
    if fn is None:
        print("VIRHE: websocket_get_history puuttuu")
        return 1
    decorators = []
    for d in fn.decorator_list:
        node = d.func if isinstance(d, ast.Call) else d
        decorators.append(node.attr if isinstance(node, ast.Attribute) else getattr(node, "id", ""))
    if "require_admin" in decorators:
        v.append("require_admin estää sallitut käyttäjät; tarkistus pitää tehdä _can_read-kutsulla")
    body_names = {x.id for x in ast.walk(fn) if isinstance(x, ast.Name)} | {
        x.attr for x in ast.walk(fn) if isinstance(x, ast.Attribute)}
    if "_can_read" not in body_names:
        v.append("websocket_get_history ei tarkista lukuoikeutta (_can_read)")
    keys = {k.value for x in ast.walk(fn) if isinstance(x, ast.Dict) for k in x.keys if isinstance(k, ast.Constant)}
    if not {"active", "latest"} <= keys:
        v.append("vastauksessa pitää olla active ja latest")
    for x in v:
        print("VIRHE:", x)
    print("OK" if not v else f"{len(v)} virhettä")
    return 1 if v else 0


if __name__ == "__main__":
    sys.exit(main())
