from __future__ import annotations

from .null_adapter import NullBrokerAdapter


class NullBroker(NullBrokerAdapter):
    """Compatibility shim for older imports.

    Step 09 keeps this name available, but the implementation is still the
    credential-free dry-run adapter and has no live submission path.
    """

