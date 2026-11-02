"""Anturi kuuluu integraation laitteeseen, jolloin se näkyy integraation sivulla eikä vain entiteettilistassa.

Nimi ja entity_id pysyvät ennallaan (has_entity_name ei muutu), joten kojelaudat eivät rriko.
Ajo:  python3 tests/test_sensor_device.py
"""
import ast
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "custom_components" / "voice_logs" / "sensor.py"


def main() -> int:
    v = []
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    cls = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == "LatestConversationSensor")
    funcs = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
    text = ast.unparse(cls)
    if "device_info" not in funcs and "_attr_device_info" not in text:
        v.append("anturilla ei ole laitetta (device_info)")
    if "identifiers" not in text or "entry.entry_id" not in text:
        v.append("laitteen tunniste pitää olla integraation entry_id (identifiers)")
    raw = SRC.read_text(encoding="utf-8")
    if "_attr_name = \"Voice Logs Latest\"" not in raw or "_attr_has_entity_name = False" not in raw:
        v.append("nimi ja has_entity_name pitää pysyä ennallaan, ettei entity_id tai kojelaudat muutu")
    for x in v:
        print("VIRHE:", x)
    print("OK" if not v else f"{len(v)} virhettä")
    return 1 if v else 0


if __name__ == "__main__":
    sys.exit(main())
