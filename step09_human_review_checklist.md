# Step 09 Human Review Checklist — Broker Selection and Adapter Design

Use this checklist after Codex completes Step 09.

## 1. Safety
- [ ] No API credentials were added.
- [ ] No `.env` containing secrets was committed.
- [ ] No live broker network call exists in concrete code.
- [ ] Null/dry-run adapter refuses LIVE mode.
- [ ] `allow_live_submission=True` is rejected by dry-run code.
- [ ] Documentation says Step 09 is non-live.

## 2. Broker candidate framework
- [ ] Broker candidate configs exist under `configs/brokers/`.
- [ ] kabu Station research config exists.
- [ ] IBKR research config exists.
- [ ] Null broker config exists.
- [ ] No broker is marked live-ready.
- [ ] Open questions are recorded.
- [ ] Official source URLs are recorded in docs/config.

## 3. Adapter contract
- [ ] Internal broker models are typed and documented.
- [ ] Base adapter protocol / abstract class exists.
- [ ] Null/dry-run adapter exists.
- [ ] Order intent -> broker payload conversion is auditable.
- [ ] Order ack/status objects exist, even if simulated.
- [ ] Positions/account snapshots have placeholder dry-run behavior.

## 4. Artifacts
- [ ] Broker selection report was generated.
- [ ] Broker decision matrix was generated.
- [ ] If a shadow packet was available, broker dry-run artifacts were generated.
- [ ] Generated artifacts are under `artifacts/broker_selection/step09` or equivalent.

## 5. Regression checks
- [ ] `pytest -q` passed.
- [ ] `scripts/verify_baseline.py` passed.
- [ ] data contract validation passed.
- [ ] Existing shadow-ops behavior was not changed.
- [ ] Strategy logic was not changed.
- [ ] Simulator economics were not changed.
- [ ] Gate / promotion thresholds were not changed.

## 6. Human decision notes
Record these manually after reviewing docs:

```text
Current candidate preference: undecided / kabu / IBKR / other
Existing brokerage account available: yes / no / unknown
Domestic Japan equity priority: high / medium / low
API-first priority: high / medium / low
Paper-trading priority: high / medium / low
Comfort with Windows dedicated host: high / medium / low
Comfort with TWS / IB Gateway operations: high / medium / low
```

## Completion decision
Step 09 can be marked complete if:

```text
no live connection
no secrets
adapter contract exists
candidate configs exist
null/dry-run adapter exists
tests pass
baseline verification passes
```
