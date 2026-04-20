from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
import re


def _pattern_fragment(patterns: list[str] | tuple[str, ...]) -> str:
    escaped = [re.escape(pattern) for pattern in patterns if pattern]
    if not escaped:
        return r"(?:password|secret|token)"
    return "|".join(escaped)


def is_sensitive_key(key: str, patterns: list[str] | tuple[str, ...]) -> bool:
    lowered = key.lower()
    return any(pattern.lower() in lowered for pattern in patterns)


def redact_inline_secret_assignments(text: str, patterns: list[str] | tuple[str, ...], replacement: str) -> str:
    fragment = _pattern_fragment(patterns)
    json_style = re.compile(
        rf'(?i)(?P<prefix>"?[\w.-]*(?:{fragment})[\w.-]*"?\s*:\s*")(?P<value>[^"]*)(?P<suffix>")'
    )
    generic_style = re.compile(
        rf'(?i)(?P<prefix>\b[\w.-]*(?:{fragment})[\w.-]*\b\s*[:=]\s*)(?P<value>[^\s,;]+)'
    )
    text = json_style.sub(lambda match: f"{match.group('prefix')}{replacement}{match.group('suffix')}", text)
    text = generic_style.sub(lambda match: f"{match.group('prefix')}{replacement}", text)
    return text


def redact_value(value: Any, patterns: list[str] | tuple[str, ...], replacement: str) -> Any:
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if is_sensitive_key(key_text, patterns):
                redacted[key_text] = replacement
            else:
                redacted[key_text] = redact_value(item, patterns, replacement)
        return redacted
    if isinstance(value, list):
        return [redact_value(item, patterns, replacement) for item in value]
    if isinstance(value, tuple):
        return [redact_value(item, patterns, replacement) for item in value]
    if isinstance(value, str):
        return redact_inline_secret_assignments(value, patterns, replacement)
    return value


def collect_sensitive_values(value: Any, patterns: list[str] | tuple[str, ...]) -> set[str]:
    candidates: set[str] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            if is_sensitive_key(key_text, patterns):
                if isinstance(item, str) and item:
                    candidates.add(item)
                else:
                    candidates.update(collect_sensitive_values(item, patterns))
            else:
                candidates.update(collect_sensitive_values(item, patterns))
        return candidates
    if isinstance(value, list) or isinstance(value, tuple):
        for item in value:
            candidates.update(collect_sensitive_values(item, patterns))
        return candidates
    if isinstance(value, str):
        fragment = _pattern_fragment(patterns)
        matches = re.findall(
            rf'(?i)\b[\w.-]*(?:{fragment})[\w.-]*\b\s*[:=]\s*([^\s,;]+)',
            value,
        )
        candidates.update(match for match in matches if match)
    return candidates
