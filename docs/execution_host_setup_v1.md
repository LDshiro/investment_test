# Execution Host Setup v1

Step 10 prepares the local execution host for safer shadow and future pre-live work.

## Required now

1. Keep the repo on the Asia/Tokyo operating calendar.
2. Use the Python version pinned in `.python-version`.
3. Ensure `data/normalized/corrected_bundle`, `runs`, and `artifacts` are present.
4. Keep `.env.example` placeholder-only and keep real secrets outside git.

## Recommended before any future live-capable work

1. Create and monitor `logs/`.
2. Create and manage `state/` for kill-switch and trading-disabled files.
3. Define a backup plan for `runs/`, `artifacts/`, and `logs/`.
4. Practice a restore procedure before depending on the host operationally.

This step does not install a scheduler, connect to a broker, or enable paper/live trading.
