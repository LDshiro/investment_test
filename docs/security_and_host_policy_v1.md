# Security And Host Policy v1

Step 10 keeps the repo in a shadow-only, dry-run-safe operating stance.

- Shadow operations do not require broker credentials.
- Real secrets must never be committed to git or embedded in artifacts.
- `READY_FOR_SMALL_LIVE` is still only a review label, not permission to trade.
- Step 10 does not send orders and does not connect to brokers.
- Human approval remains mandatory before any future paper or live activation.

## Local host expectations

- Use the pinned Python version from `.python-version`.
- Keep `data/normalized/corrected_bundle`, `runs`, and `artifacts` available.
- Treat missing `logs/` or `state/` as an operational warning to fix before any live-capable work.
- Keep the worktree clean before any future paper/live progression.

## Backup and restore

- Preserve `runs/`, `artifacts/`, and `logs/` with a daily backup plan.
- Maintain a restore test plan so historical packets and reviews can be recovered.
- Runtime safety checks may warn if these expectations are not documented or visible.
