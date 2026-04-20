# Broker Selection Report

Step 09 is a non-live broker research and dry-run design step.

- selection_id: `broker_selection_v1`
- default Step 09 dry-run adapter: `null_broker_v1`
- live-ready broker selected: `none`

## Current safe recommendation

- Use `null_broker_v1` for Step 09 packet dry-run and adapter-contract verification.
- This adapter is local-only, credential-free, and cannot submit a live order.

## Future external broker comparison

| broker_id                | display_name                           | status          |   total_score | selection_recommendation     | blocking_notes                                                                                                                                                                                                                                                                                                                                                                                 |
|:-------------------------|:---------------------------------------|:----------------|--------------:|:-----------------------------|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| kabu_station_research_v1 | au Kabucom kabu Station API (Research) | research_only   |        0.5675 | future_external_front_runner | Research facts only; no Step 09 runtime integration beyond documentation.; Step 09 treats kabu Station as research only and does not add any connection path.; Local application dependency and same-PC routing increase operational coupling.; How stable is the API around maintenance windows for pre-open operations?; What is the safest dry-run harness before any paper-like rehearsal? |
| ibkr_research_v1         | Interactive Brokers TWS API (Research) | paper_candidate |        0.5425 | future_external_secondary    | Paper-first only; Step 09 does not add sockets or credentials.; Step 09 does not add any TWS or IB Gateway connectivity.; IBKR is a future paper-first candidate only, not a live-ready recommendation.; What is the cleanest JP cash-equity routing path for this strategy subset?; Which minimum paper workflows must pass before a tiny live-dryrun phase?                                  |

## Full decision matrix

| broker_id                | display_name                           | status          | supported_markets   | supports_paper   | supports_live_api   |   total_score | selection_recommendation     | blocking_notes                                                                                                                                                                                                                                                                                                                                                                                 |
|:-------------------------|:---------------------------------------|:----------------|:--------------------|:-----------------|:--------------------|--------------:|:-----------------------------|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| null_broker_v1           | Null Broker Adapter v1                 | dry_run_only    | JP;US               | False            | False               |        0.715  | step09_default_dry_run       | No external connectivity; safe local dry-run only.; Safest Step 09 adapter because it never leaves the local process.; Fail closed outside NULL or DRY_RUN mode.; Future broker-specific symbol normalization policy is still pending.; Future mapping for JP order quantity rounding is still pending.                                                                                        |
| kabu_station_research_v1 | au Kabucom kabu Station API (Research) | research_only   | JP                  | False            | True                |        0.5675 | future_external_front_runner | Research facts only; no Step 09 runtime integration beyond documentation.; Step 09 treats kabu Station as research only and does not add any connection path.; Local application dependency and same-PC routing increase operational coupling.; How stable is the API around maintenance windows for pre-open operations?; What is the safest dry-run harness before any paper-like rehearsal? |
| ibkr_research_v1         | Interactive Brokers TWS API (Research) | paper_candidate | US;JP               | True             | True                |        0.5425 | future_external_secondary    | Paper-first only; Step 09 does not add sockets or credentials.; Step 09 does not add any TWS or IB Gateway connectivity.; IBKR is a future paper-first candidate only, not a live-ready recommendation.; What is the cleanest JP cash-equity routing path for this strategy subset?; Which minimum paper workflows must pass before a tiny live-dryrun phase?                                  |

## Research fact sources

### `null_broker_v1`
- `null_adapter_local_only`: The Step 09 null adapter is a local-only dry-run adapter with no network path. (internal://docs/broker_safety_policy_v1.md)

### `kabu_station_research_v1`
- `order_api_rate_limit`: The order API request limit is documented as 5 requests per second. (https://kabucom.github.io/kabusapi/ptal/faq.html)
- `info_api_rate_limit`: Capacity, information, and symbol registration APIs are documented as 10 requests per second. (https://kabucom.github.io/kabusapi/ptal/faq.html)
- `service_availability`: Service availability is documented as 6:30 to the next early morning 6:15 excluding maintenance. (https://kabucom.github.io/kabusapi/ptal/howto.html)
- `same_pc_same_ip`: The FAQ says requests must come from the same IP as kabu Station and to use the same PC. (https://kabucom.github.io/kabusapi/ptal/faq.html)
- `kabu_station_required`: kabu Station must be running to use the API. (https://kabucom.github.io/kabusapi/ptal/howto.html)
- `verification_environment_scope`: The verification environment is positioned for program behavior checks. (https://kabucom.github.io/kabusapi/ptal/faq.html)

### `ibkr_research_v1`
- `tws_api_socket`: TWS API connects through Trader Workstation or IB Gateway via TCP socket. (https://ibkrcampus.com/campus/ibkr-api-page/trader-workstation-api/)
- `language_support`: IBKR documents Python, Java, C++, C#, and Visual Basic support for the TWS API. (https://ibkrcampus.com/campus/ibkr-api-page/trader-workstation-api/)
- `tws_or_gateway_required`: Trader Workstation or IB Gateway must be installed and running to use the TWS API. (https://ibkrcampus.com/campus/trading-lessons/installing-configuring-tws-for-the-api/)
- `paper_before_live`: IBKR recommends testing in a paper account before placing live orders. (https://ibkrcampus.com/campus/ibkr-api-page/getting-started/)
- `paper_simulated`: IBKR paper trading is simulated and not indicative of real-world execution. (https://ibkrcampus.com/campus/glossary-terms/paper-trading-account/)
- `order_types_documented`: IBKR order types are documented for API use, but some order ideas should be manually tested in TWS first. (https://interactivebrokers.github.io/tws-api/advanced_orders.html)

AI may summarize and audit these results, but it must not be the only live-order authorization mechanism.
