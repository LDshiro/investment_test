# Broker Safety Policy v1

Step 09 is a broker research and adapter-contract step. It is not a paper or
live trading step.

## Non-live guarantees

- no real broker credentials are stored in the repo
- no real API tokens are handled
- no live broker connection is added
- no paper broker connection requiring credentials is added
- no code path can submit a real order

## Fail-closed policy

- `NullBrokerAdapter` only runs in `NULL` or `DRY_RUN`
- `PAPER` and `LIVE` modes are rejected
- `allow_live_submission=True` is rejected before payload preparation
- broker dry-run uses local artifacts only

## Human review policy

- `READY_FOR_SMALL_LIVE` or any future readiness signal is not automatic
  permission to trade
- AI may summarize, diff, and audit artifacts
- deterministic controls and human approval must take precedence over AI output
- AI must not be the only live-order authorization mechanism

## Evidence required before future paper or live work

- environment validation for the chosen external broker
- explicit credential and secret-handling design
- paper-only connection harness
- paper execution reconciliation against shadow expectations
- runbook updates for incident response and kill switch handling
- human-reviewed promotion criteria for any broker-connected mode

## What Step 09 does not do

- it does not change strategy logic
- it does not change simulator economics
- it does not change daily or weekly gates
- it does not add broker order submission
- it does not mark any broker as live-ready
