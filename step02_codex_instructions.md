# Step 02 — Codex Instructions
You are working inside the local repo for the lead-lag shadow/live trading stack.

## Objective
Implement **Step 02: execution environment reproducibility**.

The repo already completed a baseline freeze in Step 01.  
Your job is to make the local environment reproducible with minimal human effort.

## Critical constraints
Do **not** change:
- trading logic
- signal generation semantics
- risk gate logic
- promotion logic
- corrected bundle schema
- output schema for existing packets unless absolutely necessary for environment tooling

This step is allowed to change:
- setup files
- docs
- bootstrap scripts
- verification scripts
- lock files
- environment metadata artifacts
- tests related to environment reproducibility

## High-level target
A fresh local machine should be able to do:

```bash
python scripts/bootstrap_env.py --dev
python scripts/verify_environment.py
python scripts/verify_baseline.py
```

with minimal additional human intervention.

---

## Required deliverables

### 1. Python version pinning
Add a repo-level Python version pin.

Preferred:
- `.python-version`

If needed, also document the chosen version in:
- `README.md`
- `docs/environment_reproducibility.md`

Use the already working baseline environment version if you can discover it reliably.  
If exact patch pinning is inconvenient, pin the minor version and verify compatibility explicitly.

---

### 2. Lock files
Create lock files for local reproducibility.

Required:
- `requirements.lock.txt`
- `requirements-dev.lock.txt`

These must reflect the repo’s intended working environment closely enough that a fresh machine can recreate it.

Acceptable approaches:
- derive from current known-good `.venv`
- derive from `pyproject.toml`
- use a documented compile/export flow

Document clearly how the lock files were produced.

---

### 3. Bootstrap script
Create:
- `scripts/bootstrap_env.py`

This script should:
- detect or validate Python version
- create `.venv` if absent
- optionally recreate `.venv` if a flag is passed
- install runtime or dev dependencies
- prefer lock files when present
- fail with clear messages if prerequisites are missing
- print the next commands to run

Recommended CLI:
```bash
python scripts/bootstrap_env.py --dev
python scripts/bootstrap_env.py --runtime-only
python scripts/bootstrap_env.py --recreate
```

Try to keep it cross-platform.

---

### 4. Environment verification
Create:
- `scripts/verify_environment.py`

It should check at minimum:
- Python version matches repo expectation
- running inside a virtual environment, or warn clearly if not
- required packages import successfully
- lock files exist
- key CLIs can at least be imported / discovered
- optional comparison against baseline metadata if available

The output should be machine-readable enough to be useful, but human-readable is fine.

If helpful, also write:
- `artifacts/environment_repro_v1/environment_report.json`
- `artifacts/environment_repro_v1/environment_report.md`

---

### 5. Optional snapshot export
Preferred, if not too heavy:
- `scripts/export_environment_snapshot.py`

This can record:
- Python version
- platform
- package versions
- important file hashes
- lock-file hashes

Write into:
- `artifacts/environment_repro_v1/`

---

### 6. .env example
Add:
- `.env.example`

It can mostly contain placeholders, but it should make future secrets handling explicit.  
Include sections for:
- general project settings
- data paths if applicable
- broker/API placeholders for future use
- notification placeholders for future use

Do not put real secrets in the repo.

---

### 7. Documentation
Update:
- `README.md`
- `docs/environment_reproducibility.md`

The docs must explain:
- supported Python version
- how to bootstrap
- how to verify
- how lock files are used
- how to refresh lock files
- what artifacts are written
- what this step intentionally does **not** change

---

### 8. Tests
Add:
- `tests/test_environment_repro.py`

Keep tests lightweight.  
Focus on:
- config/metadata helpers
- version parsing
- lock file expectation logic
- environment script helper functions

Avoid tests that are too expensive or network-dependent.

---

### 9. Artifact bundle
Generate:
- `artifacts/environment_repro_v1/`

Expected contents (adjust if needed, but keep the spirit):
- `environment_report.json`
- `environment_report.md`
- `python_version.txt`
- `lock_hashes.json`
- `commands.md`
- optional package export files

---

## Execution plan
Please proceed in this order:

1. Inspect the repo and Step 01 baseline artifacts if present.
2. Determine the current known-good Python version and dependency situation.
3. Implement Python pinning.
4. Implement lock file generation/update.
5. Implement bootstrap script.
6. Implement environment verification.
7. Implement docs.
8. Implement tests.
9. Run the intended commands from a clean or recreated `.venv`.
10. Run:
   - `python scripts/verify_environment.py`
   - `python scripts/verify_baseline.py`
11. Record environment reproducibility artifacts under:
   - `artifacts/environment_repro_v1/`

---

## Required commands to attempt
Use the local environment and adapt paths for the platform.

At minimum, execute and report on:

```bash
python scripts/bootstrap_env.py --dev --recreate
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts\verify_environment.py
.venv\Scripts\python.exe scripts\verify_baseline.py
```

If you are not on Windows, use the equivalent `.venv/bin/python`.

If a different command layout is more robust in this repo, use it, but preserve the spirit.

---

## Acceptance checklist
Only mark the step as done if all of these are satisfied:

- bootstrap script works from a recreated `.venv`
- Python version pin exists
- lock files exist
- `.env.example` exists
- tests pass
- `verify_environment.py` passes
- `verify_baseline.py` passes
- environment artifact bundle exists
- no intentional trading logic changes were introduced

---

## Final report format
Return your answer in this exact structure:

1. Summary
2. Files changed
3. Commands executed
4. Acceptance checklist
5. Environment artifact directory
6. Follow-up notes / blockers

Be explicit about:
- the pinned Python version
- whether lock files were generated from the environment or from project metadata
- whether baseline verification still passed
- whether any dependency additions were needed and why
