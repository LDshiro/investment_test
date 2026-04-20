# Environment Repro Commands

## Bootstrap

```bash
python scripts/bootstrap_env.py --dev
python scripts/bootstrap_env.py --dev --recreate
python scripts/bootstrap_env.py --runtime-only
```

## Verify

```bash
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts/verify_environment.py
.venv\Scripts\python.exe scripts/verify_baseline.py
```

## Refresh locks

```bash
python scripts/export_environment_snapshot.py --refresh-locks
```
