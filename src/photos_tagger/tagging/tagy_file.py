from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True, slots=True)
class TagyShortcuts:
    letters: dict[str, str]
    subcategories: dict[tuple[str, str], str]
    special_keys: dict[str, str]

    @classmethod
    def empty(cls) -> "TagyShortcuts":
        return cls(letters={}, subcategories={}, special_keys={})


_SUBCATEGORY_KEY_RE = re.compile(r"^([A-Z])\s*[:._]?\s*([0-9])$")


def load_tagy_shortcuts(file_path: Path) -> TagyShortcuts:
    if not file_path.exists():
        return TagyShortcuts.empty()

    text = ""
    for encoding in ("utf-8-sig", "cp1250", "latin2"):
        try:
            text = file_path.read_text(encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
    if text == "":
        return TagyShortcuts.empty()

    letters: dict[str, str] = {}
    subcategories: dict[tuple[str, str], str] = {}
    special_keys: dict[str, str] = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "-" not in line:
            continue

        left_raw, right_raw = line.split("-", 1)
        raw_key_part = left_raw.strip()
        key_part = raw_key_part.upper()
        tag_name = right_raw.strip()
        if not tag_name:
            continue

        if len(key_part) == 1 and key_part.isalpha():
            letters[key_part] = tag_name
            continue

        # Special single-key shortcuts such as ';' or '\'.
        if len(raw_key_part) == 1 and not raw_key_part.isalnum():
            special_keys[raw_key_part] = tag_name
            continue

        match = _SUBCATEGORY_KEY_RE.fullmatch(key_part)
        if match is None:
            continue
        letter = match.group(1)
        digit = match.group(2)
        subcategories[(letter, digit)] = tag_name

    return TagyShortcuts(letters=letters, subcategories=subcategories, special_keys=special_keys)
