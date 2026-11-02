"""Lukuoikeus: ylläpitäjät ja sallitut käyttäjät näkevät arkiston, muut eivät (ACL-logiikka).

Ajo:  python3 tests/test_acl.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "custom_components" / "voice_logs"))
from acl import can_read  # noqa: E402

CASES = [
    ("ylläpitäjä aina", (True, "a", []), True),
    ("sallittu käyttäjä", (False, "k", ["k"]), True),
    ("ei-sallittu käyttäjä", (False, "x", ["k"]), False),
    ("tyhjä lista, tavallinen käyttäjä", (False, "x", []), False),
    ("tuntematon käyttäjä-id", (False, None, ["k"]), False),
]


def main() -> int:
    virheet = [f"{nimi}: {can_read(*args)} != {odotus}" for nimi, args, odotus in CASES if can_read(*args) != odotus]
    for v in virheet:
        print("VIRHE:", v)
    print("OK" if not virheet else f"{len(virheet)} virhettä")
    return 1 if virheet else 0


if __name__ == "__main__":
    sys.exit(main())
