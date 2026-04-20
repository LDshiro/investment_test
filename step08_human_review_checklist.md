# Step 08 Human Review Checklist

Use this checklist after Codex reports completion of Step 08.

## 1. Basic completion

- [ ] Codex added `shadow-ops` CLI or equivalent one-command operations runner.
- [ ] Codex added a legacy 60d operations profile.
- [ ] Codex added a canonical 60d operations profile, or clearly explained why not.
- [ ] Codex added documentation for the ops profile.
- [ ] Codex added tests.

## 2. Safety invariants

Confirm Codex reports no changes to:

- [ ] PCA SUB logic
- [ ] Table 1 sample filtering
- [ ] corrected bundle values
- [ ] canonical simulator economics
- [ ] daily hard gates
- [ ] weekly gate thresholds
- [ ] promotion thresholds
- [ ] broker interfaces
- [ ] live order submission behavior

## 3. Commands

Confirm these ran successfully or Codex gave a clear reason if one was skipped:

- [ ] `python -m pytest -q`
- [ ] `python scripts/verify_baseline.py`
- [ ] data contract validation
- [ ] `python -m leadlag.cli shadow-ops --config configs/ops/shadow_ops_legacy_60d_local.yaml`
- [ ] `python -m leadlag.cli shadow-ops --config configs/ops/shadow_ops_canonical_60d_local.yaml`

## 4. Output artifacts

For each ops run, confirm there is an artifact directory with:

- [ ] `operator_digest.md`
- [ ] `shadow_ops_summary.json`
- [ ] stage status file
- [ ] weekly review output or path reference
- [ ] weekly gates output or path reference
- [ ] batch replay output or path reference
- [ ] replay validation output or path reference

## 5. Key numbers to paste back into the chat

Paste these values for legacy and canonical:

```text
completed_days:
failed_days:
GO/WARN/STOP counts:
latest weekly status:
promotion status:
main failed promotion checks:
artifact directory:
```

For canonical only:

```text
max_abs_net_return_diff_bps:
max_abs_gross_return_diff_bps:
max_abs_cost_return_diff_bps:
```

## 6. Decision

Step 08 can be accepted if:

- [ ] both ops profiles run, or skipped run has a defensible reason
- [ ] failed_days is zero for the primary legacy run
- [ ] operator digest is readable and sufficient for AI review
- [ ] summary JSON is machine-readable
- [ ] no live automation was introduced
- [ ] tests and baseline verification pass

