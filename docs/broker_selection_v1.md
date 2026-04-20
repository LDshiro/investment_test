# Broker Selection v1

Step 09 adds a broker selection framework beside the existing research, shadow,
and shadow-ops stack. It does not change strategy computation, replay behavior,
or any live connectivity path.

## Why broker logic is separate

- Strategy logic decides **what** the portfolio wants to trade.
- Broker logic decides **how** an already-generated order intent would be mapped
  to an external venue.
- Keeping them separate prevents broker constraints from leaking into PCA SUB,
  sample filtering, simulator economics, or gate logic.

## Why Step 09 is non-live

- No real broker credentials are added.
- No paper or live sockets are opened.
- No code path can submit a real order.
- The default Step 09 adapter is `null_broker_v1`, which is local-only and
  credential-free.

## Candidate evaluation

The selection matrix in `configs/brokers/broker_selection_v1.yaml` scores each
candidate across:

- operational safety
- JP cash equity fit
- dry-run readiness
- paper progression clarity
- live API maturity
- observability

Current safe Step 09 recommendation:

- `null_broker_v1` for adapter-contract verification and packet dry-run

Future external research comparison:

- `kabu_station_research_v1`
- `ibkr_research_v1`

No broker is marked live-ready in this step.

## Research facts recorded from official sources

### kabu Station API

- API portal: https://kabucom.github.io/kabusapi/ptal/
- FAQ: https://kabucom.github.io/kabusapi/ptal/faq.html
- Getting started / operation notes: https://kabucom.github.io/kabusapi/ptal/howto.html

Recorded research facts:

- order API request limit: 5 requests/sec
- capacity / information / symbol registration APIs: 10 requests/sec
- service availability described as 6:30 to next early morning 6:15, excluding maintenance
- API accepts requests only from the same IP as kabu Station, and the FAQ says to use the same PC
- kabu Station must be running
- verification environment is for program behavior checks

### IBKR TWS API

- TWS API overview: https://ibkrcampus.com/campus/ibkr-api-page/trader-workstation-api/
- Getting started: https://ibkrcampus.com/campus/ibkr-api-page/getting-started/
- TWS / IB Gateway setup: https://ibkrcampus.com/campus/trading-lessons/installing-configuring-tws-for-the-api/
- Paper account note: https://ibkrcampus.com/campus/glossary-terms/paper-trading-account/
- Basic orders: https://interactivebrokers.github.io/tws-api/basic_orders.html
- Advanced orders: https://interactivebrokers.github.io/tws-api/advanced_orders.html

Recorded research facts:

- TWS API connects through Trader Workstation or IB Gateway via TCP socket
- Python, Java, C++, C#, and Visual Basic are documented
- TWS or IB Gateway must be installed and running
- IBKR recommends paper testing before live orders
- paper trading is simulated and not indicative of real-world execution
- order types are documented, but some ideas should be tested manually in TWS first

## What must be proven before paper or live work

- packet-to-intent normalization is stable and auditable
- broker-neutral intents preserve enough metadata for review
- dry-run payload generation is deterministic
- order status, position, and account snapshots have safe contracts
- explicit human review gates exist before any paper or live integration

AI may summarize and audit artifacts, but it must not be the only live-order
authorization mechanism.
