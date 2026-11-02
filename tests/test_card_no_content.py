"""Kortti ei lue keskustelun sisältöä tilasta; sisältö haetaan voice_logs/history/list-komennolla.

Ajo:  python3 tests/test_card_no_content.py
"""
import re
import sys
from pathlib import Path

CARD = Path(__file__).resolve().parent.parent / "custom_components" / "voice_logs" / "www" / "voice-logs-card.js"
KIELLETYT = [r"attrs\.answer\b", r"attrs\.question\b", r"attrs\.active\b", r"attrs\.run_id\b"]


def main() -> int:
    teksti = CARD.read_text(encoding="utf-8")
    v = [f"kortti lukee sisältöä tilasta: {k}" for k in KIELLETYT if re.search(k, teksti)]
    if teksti.count('type: "voice_logs/history/list"') < 2:
        v.append("kortin pitää hakea sisältö voice_logs/history/list-komennolla (myös viimeisin vastaus)")
    for x in v:
        print("VIRHE:", x)
    print("OK" if not v else f"{len(v)} virhettä")
    return 1 if v else 0


if __name__ == "__main__":
    sys.exit(main())
