# Step 11 Human Review Checklist

Use this checklist after Codex finishes Step 11.

## 1. Safety review

Confirm that Codex reports all of the following:

- [ ] No real broker connection was added.
- [ ] No credential loading for a real broker was added.
- [ ] No live order submission path was added.
- [ ] `NullBrokerAdapter` remains the only executable adapter in Step 11.
- [ ] Any `PAPER`, `LIVE`, or `allow_live_submission=True` setting fails closed.
- [ ] Runtime safety check is run before broker dry-run.
- [ ] Runtime safety has `ERROR=0`.

## 2. Behavior preservation

Confirm:

- [ ] PCA SUB logic unchanged.
- [ ] Table 1 sample filtering unchanged.
- [ ] corrected bundle values unchanged.
- [ ] canonical simulator economics unchanged.
- [ ] daily hard gates unchanged.
- [ ] weekly gates / promotion thresholds unchanged.
- [ ] shadow-ops still works without broker dry-run when using old profiles.

## 3. Broker dry-run outputs

Check that Codex reports artifact locations for:

- [ ] legacy broker-dryrun ops run.
- [ ] canonical broker-dryrun ops run.
- [ ] standalone batch broker dry-run, if run separately.

Each output should contain:

- [ ] `broker_dryrun_summary.csv`
- [ ] `broker_dryrun_summary.json`
- [ ] `broker_dryrun_summary.md`
- [ ] `broker_dryrun_validation.json`
- [ ] per-day broker intent / payload / ack artifacts

## 4. Numerical sanity

Check the reported totals:

- [ ] `completed_days` equals expected replay days, normally 60.
- [ ] `failed_days = 0`.
- [ ] `intent_count_total > 0`.
- [ ] `ack_count_total == intent_count_total` for NullBroker.
- [ ] `reject_count_total == 0` unless the test intentionally injects invalid orders.
- [ ] canonical reconciliation remains within the existing threshold.

## 5. Test and verification results

Confirm:

- [ ] focused broker dry-run tests pass.
- [ ] full pytest passes.
- [ ] `scripts/verify_baseline.py` passes.
- [ ] data contract validation passes.
- [ ] runtime safety check passes.

## 6. Blockers

Mark Step 11 as blocked if any of the following appears:

- [ ] any real broker network call exists;
- [ ] any real credential is committed;
- [ ] any live or paper mode can run without explicit future approval;
- [ ] old shadow profiles produce different trading results;
- [ ] broker dry-run stage mutates shadow packet economics;
- [ ] runtime safety has `ERROR > 0`.

If none of those blockers appear, paste Codex's final report into the chat for completion judgment.
