# Step 09 Codex Instructions — Broker Selection and Adapter Design

You are working in the local repository for the lead-lag investment research / shadow-ops stack.

## Objective
Implement Step 09: broker selection framework and broker adapter design.

This is a **non-live, no-credentials, no-order-submission** step. Add the broker abstraction layer and selection artifacts without changing trading behavior.

## Hard constraints
Do **not** change:

- PCA SUB logic.
- Table 1 sample filtering.
- corrected bundle values.
- canonical simulator economics.
- daily hard gate behavior.
- weekly gate / promotion thresholds.
- existing shadow-ops behavior.
- existing legacy or canonical replay outputs except for newly created Step 09 artifacts.

Do **not** add:

- real broker credentials.
- real API tokens.
- live broker connections.
- paper broker connections requiring user credentials.
- any code path that can submit a real order.

If you create a method named `submit_order`, it must either be abstract or guarded so strongly that the provided implementation cannot submit a live order. Prefer names such as `dry_run_order` or `prepare_order_payload` for concrete Step 09 code.

## Step 09 design intent
The repository already supports:

- corrected bundle validation.
- historical shadow run.
- legacy and canonical 60-day shadow replay.
- weekly review and weekly gates.
- runbook rendering.
- shadow-ops wrapper.

Step 09 should add the broker-facing layer **beside** this stack, not inside the strategy computation. The broker layer should consume already-generated order intents or shadow packet orders and normalize them into broker-neutral structures.

## Official-source constraints to capture in docs/config
Record these as research facts in docs and configs, with source URLs in comments or documentation. Do not rely on them as unverified runtime guarantees.

### kabu Station API research facts
- Order API request limit: 5 requests/sec.
- Capacity / information / symbol registration APIs: 10 requests/sec.
- Service availability described as 6:30 to next early morning 6:15, excluding maintenance.
- API accepts requests only from the same IP as kabu Station; the FAQ says to use the same PC.
- kabu Station must be running to use the API.
- Verification environment is for program behavior checks.

### IBKR research facts
- TWS API connects through Trader Workstation or IB Gateway via TCP socket.
- IBKR documents Python, Java, C++, C#, and Visual Basic support for TWS API.
- TWS or IB Gateway must be installed/running for TWS API usage.
- IBKR recommends testing in a paper account before placing live orders.
- IBKR paper trading is simulated and not indicative of real-world execution.
- IBKR order types available through API are documented, but some order ideas should be manually tested in TWS first.

## Required implementation
### 1. Broker configs
Add broker candidate configs under `configs/brokers/`.

Suggested files:

```text
configs/brokers/broker_selection_v1.yaml
configs/brokers/kabu_station_research_v1.yaml
configs/brokers/ibkr_research_v1.yaml
configs/brokers/null_broker_v1.yaml
```

The configs should cover at least:

- broker_id
- display_name
- status: research_only / dry_run_only / paper_candidate / live_candidate
- supported_markets
- supported_asset_types
- order_types_known
- time_in_force_known
- supports_paper
- supports_live_api
- supports_shortability_check
- supports_position_query
- supports_order_status_query
- operational_requirements
- known_limits
- safety_notes
- open_questions
- source_urls
- decision_scores or evaluation criteria

Use conservative defaults. Do not mark any broker as live-ready.

### 2. Broker docs
Add:

```text
docs/broker_selection_v1.md
docs/broker_adapter_contract_v1.md
docs/broker_safety_policy_v1.md
```

Docs must explain:

- why broker logic is separated from strategy logic.
- why Step 09 is non-live.
- how candidate brokers are evaluated.
- how null/dry-run adapters work.
- what must be proven before paper or live integration.
- that AI may summarize and audit but must not be the only live-order authorization mechanism.

### 3. Broker models and adapter contract
Add a broker package, e.g.:

```text
src/leadlag/broker/__init__.py
src/leadlag/broker/models.py
src/leadlag/broker/base.py
src/leadlag/broker/null_adapter.py
src/leadlag/broker/validation.py
```

Define typed models. Use dataclasses or pydantic if already a project dependency; avoid adding heavy dependencies unless necessary.

Minimum internal models:

```text
BrokerMode: NULL / DRY_RUN / PAPER / LIVE
OrderSide: BUY / SELL / SELL_SHORT / BUY_TO_COVER
OrderType: MARKET / LIMIT / MARKET_ON_CLOSE / LIMIT_ON_CLOSE / UNKNOWN
TimeInForce: DAY / IOC / FOK / GTC / UNKNOWN
OrderIntent
BrokerOrderPayload
BrokerOrderAck
BrokerOrderStatus
ExecutionReport
PositionSnapshot
AccountSnapshot
ShortabilitySnapshot
BrokerCapabilities
BrokerDiagnostic
```

`OrderIntent` should be broker-neutral and compatible with existing shadow orders. Include fields such as:

- run_id
- trade_date
- symbol
- market
- side
- quantity or notional_jpy
- order_type
- tif
- limit_price
- strategy_id
- source_packet_path
- allow_live_submission default false
- metadata

### 4. Base adapter protocol
Define a base class or protocol with methods such as:

```python
class BrokerAdapter(Protocol):
    def get_capabilities(self) -> BrokerCapabilities: ...
    def validate_environment(self) -> list[BrokerDiagnostic]: ...
    def prepare_order_payload(self, intent: OrderIntent) -> BrokerOrderPayload: ...
    def dry_run_order(self, intent: OrderIntent) -> BrokerOrderAck: ...
    def get_order_status(self, broker_order_id: str) -> BrokerOrderStatus: ...
    def get_positions(self) -> list[PositionSnapshot]: ...
    def get_account_snapshot(self) -> AccountSnapshot: ...
```

Do not implement a live submitter in Step 09.

### 5. Null / dry-run adapter
Implement `NullBrokerAdapter` or equivalent.

It should:

- accept normalized `OrderIntent` objects.
- validate that `allow_live_submission` is false.
- generate deterministic fake broker IDs.
- write or return broker payloads / acknowledgements.
- never send network requests.
- fail closed if mode is LIVE.

### 6. Scripts / CLI
Add at least one utility script:

```text
scripts/evaluate_broker_candidates.py
```

Optionally add:

```text
scripts/broker_dryrun_from_packet.py
```

The candidate evaluator should render:

```text
artifacts/broker_selection/step09/broker_selection_report.md
artifacts/broker_selection/step09/broker_selection_report.json
artifacts/broker_selection/step09/broker_decision_matrix.csv
```

The dry-run utility, if implemented, should read a historical shadow packet directory containing `orders_shadow.csv`, convert rows to `OrderIntent`, pass them through `NullBrokerAdapter`, and write:

```text
broker_order_intents.csv
broker_payloads.csv
broker_acks.csv
broker_dryrun_summary.json
```

Add CLI commands if consistent with the existing repo style, for example:

```bash
python -m leadlag.cli evaluate-brokers --config configs/brokers/broker_selection_v1.yaml --output-dir artifacts/broker_selection/step09
python -m leadlag.cli broker-dryrun --packet-dir <packet_dir> --broker-config configs/brokers/null_broker_v1.yaml --output-dir artifacts/broker_dryrun/step09
```

If adding CLI commands is too invasive, scripts are sufficient, but tests must cover the core logic.

### 7. Tests
Add tests such as:

```text
tests/test_broker_models.py
tests/test_broker_adapter_contract.py
tests/test_null_broker_adapter.py
tests/test_broker_candidate_config.py
```

Tests must prove:

- candidate configs load.
- required candidate fields exist.
- null adapter cannot run in LIVE mode.
- `allow_live_submission=True` is rejected in null/dry-run mode.
- generated fake broker order IDs are deterministic or at least auditable.
- broker dry-run does not require credentials.
- existing test suite still passes.

## Validation commands to run
Run these, adjusting Windows path syntax as needed:

```bash
.venv\Scripts\python.exe scripts\verify_environment.py
.venv\Scripts\python.exe scripts\verify_baseline.py
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m leadlag.cli validate-data-contract --bundle-dir data/normalized/corrected_bundle --contract configs/data_contracts/corrected_bundle_v1.yaml --output-dir artifacts/data_contract/corrected_bundle_v1_step09_preflight
.venv\Scripts\python.exe -m compileall src scripts tests
.venv\Scripts\python.exe -m pytest tests\test_broker_models.py tests\test_broker_adapter_contract.py tests\test_null_broker_adapter.py tests\test_broker_candidate_config.py -q
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts\verify_baseline.py
```

Then run the broker evaluator:

```bash
.venv\Scripts\python.exe scripts\evaluate_broker_candidates.py --config configs/brokers/broker_selection_v1.yaml --output-dir artifacts/broker_selection/step09
```

If you implemented CLI commands, also run the equivalent CLI command.

If you implemented packet dry-run, run it against the most recent shadow packet if available. Do not make Step 09 fail if no suitable packet exists; report it as skipped.

## Final response format to user
Return:

```text
Summary
Files changed
Commands executed
Broker candidate configs added
Adapter interface summary
Dry-run artifact location, if generated
Safety guarantees
Acceptance checklist
Follow-up notes / blockers
```

Explicitly state whether:

- any live broker connection was added.
- any credential handling was added.
- any live order submission path exists.
- strategy logic changed.
- simulator economics changed.
- gates or promotion thresholds changed.

Expected answers should be:

```text
live broker connection added: no
credential handling added: no
live order submission path exists: no
strategy logic changed: no
simulator economics changed: no
gates/promotion thresholds changed: no
```
