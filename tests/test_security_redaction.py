from __future__ import annotations

from leadlag.security.redaction import redact_value


def test_redact_value_redacts_sensitive_keys_recursively() -> None:
    payload = {
        "api_key": "top-secret",
        "nested": {
            "token_value": "abc123",
            "items": [
                {"password_hint": "hidden"},
                "safe text",
            ],
        },
    }

    redacted = redact_value(payload, ["password", "token", "api_key"], "***REDACTED***")

    assert redacted["api_key"] == "***REDACTED***"
    assert redacted["nested"]["token_value"] == "***REDACTED***"
    assert redacted["nested"]["items"][0]["password_hint"] == "***REDACTED***"
    assert redacted["nested"]["items"][1] == "safe text"


def test_redact_value_redacts_inline_assignments() -> None:
    payload = {
        "message": 'token: abc123 password=letmein "api_key": "xyz789"',
    }

    redacted = redact_value(payload, ["password", "token", "api_key"], "***REDACTED***")

    assert "abc123" not in redacted["message"]
    assert "letmein" not in redacted["message"]
    assert "xyz789" not in redacted["message"]
    assert "***REDACTED***" in redacted["message"]
