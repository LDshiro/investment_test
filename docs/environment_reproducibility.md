# Environment Reproducibility

Step 02 makes the local execution environment reproducible with minimal human effort while leaving trading logic untouched.

## Supported Python version

The reproducible local environment is pinned to:

- `3.14.3`

This pin is recorded in:

- `.python-version`
- `artifacts/baseline_shadow_stack_v1/baseline_manifest.json`

`pyproject.toml` still advertises the broader package compatibility floor (`>=3.11`), but the supported local reproducibility workflow for this repo is pinned to `3.14.3`.

## What this step changes

- Python version pinning
- lock files
- bootstrap / verification / export scripts
- environment reproducibility artifacts
- environment-focused tests and docs

## What this step does not change

- trading logic
- signal generation semantics
- risk gate logic
- promotion logic
- corrected bundle schema
- existing packet output semantics

## Bootstrap from scratch

From the repo root:

```bash
python scripts/bootstrap_env.py --dev
```

To force a clean rebuild of the repo-local virtual environment:

```bash
python scripts/bootstrap_env.py --dev --recreate
```

For runtime-only installation:

```bash
python scripts/bootstrap_env.py --runtime-only
```

The bootstrap script:

1. validates that the current interpreter is `3.14.3`
2. creates `.venv` if needed
3. recreates `.venv` when `--recreate` is passed
4. upgrades `pip`
5. installs from lock files when present
6. prints the next verification commands

## Lock files

Repo-level lock files:

- `requirements-dev.lock.txt`
- `requirements.lock.txt`

They are produced as follows:

- `requirements-dev.lock.txt`
  - preferred source: `artifacts/baseline_shadow_stack_v1/pip_freeze.txt`
  - fallback source: current `.venv` `pip freeze`
  - editable repo entries are normalized to `-e .`
- `requirements.lock.txt`
  - generated from a clean temporary venv created with Python `3.14.3`
  - installs `-e .`
  - uses `requirements-dev.lock.txt` as a constraint when present

To refresh lock files and snapshot metadata:

```bash
python scripts/export_environment_snapshot.py --refresh-locks
```

## Verification

Primary verification commands:

```bash
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts/verify_environment.py
.venv\Scripts\python.exe scripts/verify_baseline.py
```

On non-Windows platforms, use `.venv/bin/python`.

`verify_environment.py` checks:

- pinned Python version compatibility
- virtual environment presence
- runtime package imports
- tooling imports
- lock file existence
- normalized `pip freeze` vs lock-file match
- optional comparison with Step 01 baseline metadata

## Artifact bundle

Step 02 writes artifacts under:

- `artifacts/environment_repro_v1/`

Expected contents:

- `environment_report.json`
- `environment_report.md`
- `python_version.txt`
- `lock_hashes.json`
- `commands.md`
- `pip_freeze.current.txt`

## Relationship to Step 01 baseline

Step 02 intentionally reuses Step 01 as the known-good environment anchor:

- Python pin comes from the baseline environment metadata
- dev lock generation prefers the baseline `pip_freeze.txt`
- `verify_baseline.py` remains part of the acceptance flow

This keeps environment reproducibility aligned with the frozen baseline rather than inventing a new reference point.
