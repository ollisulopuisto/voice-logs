"""Lukuoikeus keskusteluarkistoon: ylläpitäjät ja listalle merkityt käyttäjät.

Pidetään ilman Home Assistant -importteja, jotta logiikka voidaan testata suoraan.
"""

from __future__ import annotations


def can_read(is_admin: bool, user_id: str | None, allowed_user_ids: list[str]) -> bool:
    """Return True for administrators and for users on the allow-list."""
    if is_admin:
        return True
    if not user_id:
        return False
    return user_id in allowed_user_ids
