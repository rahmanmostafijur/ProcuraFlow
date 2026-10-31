"""Removing a person's name and email from stored JSON (audit entries) without losing the entries themselves."""

import re
from collections.abc import Mapping
from typing import Any

REDACTED = "[redacted]"


def _replace_all(text: str, needles: Mapping[str, str]) -> str:
    for needle, replacement in needles.items():
        text = re.sub(re.escape(needle), replacement, text, flags=re.IGNORECASE)
    return text


def redact_json(value: Any, needles: Mapping[str, str]) -> Any:
    """A copy of ``value`` with every occurrence of each needle (any case) replaced inside its strings.

    Longer needles go first so an email is replaced whole before a name that happens to be part of it.
    """
    ordered = dict(sorted(((n, r) for n, r in needles.items() if n), key=lambda pair: -len(pair[0])))
    return _walk(value, ordered)


def _walk(value: Any, needles: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        return _replace_all(value, needles)
    if isinstance(value, Mapping):
        return {key: _walk(item, needles) for key, item in value.items()}
    if isinstance(value, list):
        return [_walk(item, needles) for item in value]
    return value
