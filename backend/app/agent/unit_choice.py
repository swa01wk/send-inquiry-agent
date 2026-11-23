"""A bare answer to the unit type question, in English or Arabic.

Shared by the guard (it saves the answer) and `show_category_options` (a unit type alone is
not what the business offers).
"""

from __future__ import annotations

# A bare answer to the unit type question (the chips, or typed, in English or Arabic). Live
# eval 16 Nov (Arabic user): "متجر" was answered but not saved, or was already saved, and
# the missed-capture rule took the reply back. 18 Nov B1 (N1): Media and Specialty too; a
# unit type the intake doesn't offer is refused by `write_fields`.
_UNIT_CHOICES = {
    "store": "store",
    "a store": "store",
    "office": "office",
    "an office": "office",
    "media": "media",
    "media space": "media",
    "a media space": "media",
    "specialty": "specialty",
    "specialty unit": "specialty",
    "a specialty unit": "specialty",
    "متجر": "store",
    "محل": "store",
    "مكتب": "office",
    "مساحة إعلانية": "media",
    "وحدة متخصصة": "specialty",
}


def bare_unit_choice(text: str) -> str | None:
    """The unit type id when the whole message is that choice, else None."""
    key = " ".join(text.strip().strip(".!،,").lower().split())
    if key.startswith("ال") and key[2:] in _UNIT_CHOICES:
        key = key[2:]
    return _UNIT_CHOICES.get(key)
