# Weekly Gate Calibration Policy

Step 06 fixes the interpretation policy for weekly GO / WARN / STOP decisions and
for promotion toward tiny or small live deployment. The goal is not to tune the
rules until the current sample passes. The goal is to make sure the rules remain
safety-oriented, explainable, and conservative when the system is moved closer to
live operation.

## Weekly status vs promotion status

Weekly status answers an operational question: "Was this recent week safe and
orderly enough to keep shadow monitoring healthy?" Promotion status answers a
deployment question: "Has the system earned enough evidence to move one step
closer to live?" Those are related but different decisions.

- `GO` means the week stayed inside the current operational envelope.
- `WARN` means the week was operationally acceptable but deserves review.
- `STOP` means something safety-relevant or operationally abnormal happened.
- `HOLD_SHADOW` means stay in shadow and keep gathering evidence.
- `BLOCKED` means promotion is disallowed because a disqualifying event occurred.

## Why STOP is operational and safety-oriented

`STOP` should be reserved for conditions that undermine trust in the replay or the
operational safety envelope. Examples include failed daily runs, hard-gate
triggered days, critical alerts, or a material collapse in tradable breadth.

Poor but non-catastrophic performance is not enough on its own to justify `STOP`.
A weak return patch may indicate model drift, market conditions, or plain noise,
but it does not automatically mean the system is unsafe to keep observing in
shadow.

## Why weak performance usually maps to WARN / HOLD

If the stack is operationally sound but the performance evidence is weak, the
normal response is:

- weekly status: `WARN` when a soft threshold is crossed
- promotion status: `HOLD_SHADOW` until the evidence improves

That keeps the distinction clear:

- `STOP` protects operations and safety
- `HOLD_SHADOW` protects capital allocation and deployment discipline

## Why promotion rules must not be tuned to pass the current sample

Promotion rules are supposed to resist sample-specific pressure. If the latest
window is negative, the right response is usually to remain on hold, not to relax
the non-negative return requirement until the sample passes.

This matters especially for Step 06 because the current 60-day Step 05 window is
operationally stable but still fails promotion on compounded shadow return. That is
acceptable and desirable. The calibration artifact should make that visible rather
than optimize it away.

## Required evidence before moving toward tiny or small live

Before moving toward `live_dryrun` or a tiny live pilot, the system should show:

- no failed days in the review window
- no critical alert days
- no triggered hard-gate days
- no STOP weeks
- a recent week that is still `GO`
- a majority of recent weeks that are `GO`
- non-negative compounded shadow return over the review window
- weighted hit rate around or above 40%
- stable tradable breadth
- expected costs that remain inside the observed stable operating range

The pre-live ruleset intentionally asks for more evidence than the existing
small-live candidate ruleset.

## How to interpret legacy vs canonical replay consistency

Legacy and canonical replay do not need to be identical at the file level, but
they should tell the same operational story. If both produce the same weekly status
and the same promotion outcome, that is strong evidence that the deployment
decision is not an artifact of a simulator accounting detail.

If they diverge, the difference must be understood before promotion is considered.
Consistency improves confidence; inconsistency increases review burden.

## Relation to future live_dryrun and tiny live phases

Step 06 is still a shadow-calibration step. It does not authorize live trading on
its own. The intended sequence is:

1. stable historical replay
2. calibrated weekly status and promotion policy
3. live_dryrun with tiny operational scope
4. tiny live execution to measure live-vs-shadow friction
5. only then consider small-live expansion

The recommended live overrides in the pre-live ruleset are intentionally small.
Their objective is to measure execution friction and operational discipline, not to
maximize live PnL.
