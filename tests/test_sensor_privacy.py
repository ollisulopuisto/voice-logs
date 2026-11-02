"""sensor.voice_logs_latest ei saa sisältää keskustelun tekstiä (ei tilassa eikä attribuuteissa).

Tekstit luetaan vain voice_logs/history/list-komennolla, joka tarkistaa lukuoikeuden.
Ajo:  python3 tests/test_sensor_privacy.py
"""
import ast
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "custom_components" / "voice_logs" / "sensor.py"
SALLITUT = {"total_conversations", "history_updated", "has_active", "active_updated", "latest_id"}
KIELLETYT = {"query", "answer", "question", "debug", "run_id", "active"}


def main() -> int:
    v = []
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    cls = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == "LatestConversationSensor")
    funcs = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}

    def strings(node):
        return {x.value for x in ast.walk(node) if isinstance(x, ast.Constant) and isinstance(x.value, str)}

    def names(node):
        return {x.attr for x in ast.walk(node) if isinstance(x, ast.Attribute)} | {
            x.id for x in ast.walk(node) if isinstance(x, ast.Name)}

    nv = funcs.get("native_value")
    if nv is None:
        v.append("native_value puuttuu")
    elif (strings(nv) | names(nv)) & {"query", "answer", "question"}:
        v.append("native_value (tila) lukee keskustelun tekstiä")

    ea = funcs.get("extra_state_attributes")
    if ea is None:
        v.append("extra_state_attributes puuttuu")
    else:
        avaimet = set()
        for x in ast.walk(ea):
            if isinstance(x, ast.Dict):
                avaimet |= {k.value for k in x.keys if isinstance(k, ast.Constant)}
        vaarat = avaimet & KIELLETYT
        if vaarat:
            v.append(f"attribuutit sisältävät sisältöä: {sorted(vaarat)}")
        ylimaaraiset = avaimet - SALLITUT
        if ylimaaraiset:
            v.append(f"attribuutit tuntemattomia (lisää SALLITUT jos tarkoituksellinen): {sorted(ylimaaraiset)}")

    for x in v:
        print("VIRHE:", x)
    print("OK" if not v else f"{len(v)} virhettä")
    return 1 if v else 0


if __name__ == "__main__":
    sys.exit(main())
