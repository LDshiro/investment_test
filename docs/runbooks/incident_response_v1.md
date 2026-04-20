# Incident Response v1

## P0

- Trigger examples: possible capital loss, unauthorized order, API or secrets exposure, live order mismatch, broken kill switch, hard gate bypass, corrupted production data
- Immediate action: engage the kill switch, halt any live-facing activity, isolate credentials, preserve logs and artifacts
- Review owner: human operator with kill-switch authority plus engineering owner
- Trading / shadow continues: no
- Required artifact: incident ticket and completed postmortem
- Resolution criteria: containment verified, root cause understood, and explicit human sign-off recorded

## P1

- Trigger examples: STOP run or STOP week, failed shadow replay day, failed data contract, missing required packet, baseline verification failure, unresolved canonical reconciliation failure
- Immediate action: freeze promotion decisions, preserve the packet set, assign an owner for same-day investigation
- Review owner: strategy owner and operations reviewer
- Trading / shadow continues: no until the failure is understood
- Required artifact: incident note linked to the failed packet or validation artifact
- Resolution criteria: failure reproduced or explained, fix verified, and relevant review rerun cleanly

## P2

- Trigger examples: repeated WARN, abnormal cost drift, low hit rate, high alert density, recurrent reconciliation drift under STOP threshold, non-critical scheduler failure
- Immediate action: open a tracking issue, compare recent packets, and decide whether extra monitoring or a temporary pause is warranted
- Review owner: operations reviewer with strategy support
- Trading / shadow continues: yes, unless escalated
- Required artifact: tracking issue or review memo
- Resolution criteria: trend explained or stabilized and follow-up action documented

## P3

- Trigger examples: documentation issue, cleanup, known warning, minor reporting issue, non-urgent technical debt
- Immediate action: log the issue and schedule it in normal maintenance
- Review owner: repo maintainer
- Trading / shadow continues: yes
- Required artifact: backlog item or maintenance note
- Resolution criteria: item fixed or accepted into tracked backlog
