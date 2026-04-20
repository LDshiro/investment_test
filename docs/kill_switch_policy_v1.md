# Kill Switch Policy v1

The current repo phase remains shadow-only, but the kill-switch semantics are fixed now so later live-capable work has a conservative default.

- `state/KILL_SWITCH_ON` means do not proceed to any future paper/live order-sending workflow.
- `state/TRADING_DISABLED` means all live-capable workflows must remain disabled.
- Human operators keep final authority to halt or suspend any future broker-connected process.
- AI review is advisory only and cannot override deterministic guards or human stop authority.

## Current Step 10 behavior

- No broker network connection is attempted.
- No order is submitted.
- Missing kill-switch files are reported as host state, not treated as permission to trade.
- Any future paper/live activation still requires explicit human approval beyond `READY_FOR_SMALL_LIVE`.
