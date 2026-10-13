# Danish Price Spike Radar

A reproducible Danish energy-risk project connecting **48-hour price-spike forecasts** to a **SQLite paper hedge book**. It uses real DK1/DK2 day-ahead prices, compares probability models, measures calibration drift, and replays risk-controlled synthetic cap positions.

**The main finding:** the logistic model ranks expensive hours well, but substantially understates spike probabilities after a price-regime change. A recent-week frequency benchmark has better held-out Brier scores. The paper hedge savings depend on hypothetical premiums and are not evidence of an executable trading opportunity.

## Explore the project

Download or clone the repository and open [the interactive report](reports/benchmark/report.html) locally. GitHub displays HTML source rather than running the dashboard.

The report contains:

- DK1/DK2 weekly price charts with 48-hour risk alerts.
- Reliability plots and a comparison against two probability benchmarks.
- Six hedge scenarios: premiums of €3, €8 or €15/MWh, at 25% or 50% requested load coverage.
- Daily procurement-cost and historical tail-cost comparisons.
- A time-replay trade table showing OPEN, SETTLED and REJECTED orders.
- Downloadable forecast, order, event and daily-cost records.

The report works offline without external JavaScript, fonts, tracking or API keys.

## Reproduce

Python 3.11+ and NumPy are required. From the repository root:

~~~bash
python -m venv .venv
# Activate the environment using your platform's standard command.
python -m pip install -e .
python -m unittest discover -s tests -v
python -m spikeradar.cli download --data data
python -m spikeradar.cli run --data data --out reports/my-run
python -m http.server 8768 --bind 127.0.0.1 --directory reports/my-run
~~~

Then open http://127.0.0.1:8768/report.html. Opening the HTML file directly also works.

Each run requires a fresh output directory if a ledger already exists. This prevents accidentally mixing two backtests. The download command fetches the fixed benchmark period; dates and model settings are intentionally explicit constants in the pipeline, not an automatic live-trading service.

Raw API responses and binary SQLite databases are excluded from Git. A fresh run rebuilds the ledger. The included CSV files preserve the complete published order and event history.

## Data and availability

Source: [Energinet Day-Ahead Prices](https://www.energidataservice.dk/tso-electricity/DayAheadPrices), [official metadata](https://api.energidataservice.dk/meta/dataset/DayAheadPrices), [API guide](https://www.energidataservice.dk/guides/api-guides).

The default request covers **1 October 2025 inclusive through 1 October 2026 exclusive, in Danish local time**, for DK1 and DK2. The dataset uses quarter-hour products and EUR/MWh. The benchmark contains **70,080 quarter-hour records**, aggregated into **8,760 complete UTC hours per zone**, with no missing or invalid intervals.

Four equal quarter-hour prices are averaged into one hourly reference. This corresponds to a flat within-hour load. A cap on this hourly average is not equivalent to four separate quarter-hour caps. Negative prices are retained. Duplicate or misaligned observations raise errors; incomplete hours are excluded without interpolation. UTC timestamps avoid collapsing the repeated local hour at daylight-saving changes.

The exact request URL, retrieval time, raw-response SHA-256, dataset metadata, quality counts and fitted coefficients are recorded in [metrics.json](reports/benchmark/metrics.json). The cache loader verifies the hash before use. Future API revisions may change rerun results; the API is not a historical publication-vintage archive.

## Forecasting design

A “spike” is an hourly price **strictly above the zone's 90th percentile in the eligible training samples**. This threshold is fixed thereafter:

| Zone | Fixed threshold |
|---|---:|
| DK1 | €138.00075/MWh |
| DK2 | €147.04375/MWh |

This is a relative historical definition, not a market scarcity-price definition. Spikes need not remain rare under a new price level.

For delivery hour t:

- The simulated forecast and hedge decision occur at t − 48 hours.
- The newest observed price feature starts at t − 72 hours, a 24-hour buffer before the decision.
- Features include price lags of 72, 73, 74, 96, 120, 168 and 240 hours; mean, standard deviation, maximum and minimum over lags 72–95; a price change; and UTC calendar features.
- All 169 historical hours at lags 72–240 must be present so all candidate models share the same eligible sample.
- Standardization, spike thresholds and logistic coefficients use training data only. Calendar features use the known delivery time.
- The model is a deterministic L2-regularized logistic regression, with penalty 0.01, an unpenalized intercept, and full-batch gradient descent.

Candidate models are logistic regression, the training spike frequency, and a trailing 168-hour spike frequency using only available observations. The rolling benchmark uses Laplace smoothing: (spikes + 1) / (168 + 2). The candidate with the lowest validation Brier score is selected independently per zone.

| Partition | Delivery timestamps, UTC | Samples per zone |
|---|---|---:|
| Training | First eligible hour through 30 April 2026 | 4,850 |
| Validation | 4 May–28 June 2026 | 1,344 |
| Simulated selection lock | 30 June 2026 00:00 | — |
| Test | 2 July–29 September 2026 | 2,160 |

The gaps allow labels to mature before the next simulated decision period. Models are not refitted after training. Validation is used only for candidate selection; the test period does not set the strike, coefficients or selected model. As the test advances, each prediction may use newly eligible past prices.

This was a retrospective project built in October 2026. The simulated lock date describes the evaluation protocol, not a claim that forecasts were actually issued in June.

## Held-out results

Both zones selected logistic regression on validation. **The recent-week benchmark subsequently performs better on Brier score**, especially in DK1. Lower Brier is better; ROC AUC measures ranking and does not establish calibration.

| Zone / model | Brier score | ROC AUC |
|---|---:|---:|
| DK1 logistic | 0.2853 | 0.8167 |
| DK1 training frequency | 0.4026 | 0.5000 |
| DK1 recent-week frequency | 0.2675 | 0.5461 |
| DK2 logistic | 0.2497 | 0.8081 |
| DK2 training frequency | 0.3385 | 0.5000 |
| DK2 recent-week frequency | 0.2497 | 0.5999 |

The training spike rate is 10% in each zone. In the test it rises to **49.1% in DK1 and 41.1% in DK2**. Reliability plots expose substantial underprediction. At the illustrative 20% alert threshold, logistic precision is 77.7% / 74.5%, but recall is only 56.2% / 52.1%.

The project retains the validation-selected model instead of switching after inspecting the test. These results support a discussion of distribution shift and monitoring, not a production-ready claim.

## Paper contracts and risk controls

The portfolio consumes **1 MWh every hour in each zone**. A model probability of at least 20% proposes a long hourly cap, with strike equal to that zone's fixed spike threshold.

~~~text
premium paid EUR = hedge MWh × assumed premium EUR/MWh
cap payout EUR = hedge MWh × max(hourly spot EUR/MWh − strike EUR/MWh, 0)
hedged procurement cost EUR = spot price × 1 MWh + premium paid − cap payout
~~~

The trigger is a research rule, not an optimal pricing rule: probability alone does not estimate the severity of a spike or the fair option premium. Contract availability, liquidity and the assumed flat premiums are not supported by the price dataset.

The SQLite ledger checks a shared **€60 premium budget per UTC issue day**, **8 MWh maximum open volume**, and **0.5 MWh maximum order size**. A kill switch rejects new orders. It also rejects backdated events, duplicate zone/delivery contracts, invalid inputs, premature settlements and repeated settlements.

Accepted orders have SUBMITTED → APPROVED → OPEN → SETTLED events. Rejected orders preserve their rejection reason. Premiums are paid at assumed immediate paper fills. Settlement occurs after the delivery hour ends. Due settlements release open capacity before new orders at the same timestamp; DK1 is processed first for tied submissions. Rejected orders are not resubmitted. There is no broker connection, actual execution, cancel/replace workflow or live position monitoring. The ledger is a single-process research component, not a concurrent production order system.

In the **€8/MWh, 50%-coverage default scenario**:

| Measure | Result |
|---|---:|
| Settled contracts | 605 |
| Rejected proposals | 782, all due to open-volume limit |
| Premiums paid | €2,420.00 |
| Synthetic payouts | €12,593.72 |
| Procurement-cost change versus unhedged | −€10,173.72 |
| Daily cost 95th percentile: unhedged → hedged | €9,105.30 → €8,767.17 |
| Mean of five most expensive days: unhedged → hedged | €10,298.70 → €9,777.91 |

These are historical scenario costs, **not trading returns or actual savings**. No collateral, transaction charges, taxes, financing, discounting or counterparty failures are modeled. Premiums are assigned to delivery days for cost comparison but counted on issue days for budget checks.

Tail summaries require complete 24-hour UTC days in both zones. They use 90 days; the worst-5% mean is the average of the five largest daily costs, calculated separately for each strategy. It is a descriptive historical statistic with very few tail observations, not a forward risk guarantee.

## Trade table replay

The final table naturally contains SETTLED and REJECTED records because all accepted historical contracts have reached delivery. Click **Show an active book**, or move the replay slider, to see OPEN positions at earlier times. Filter by status to inspect rejected proposals. The replay uses event timestamps and hides payouts until settlement.

Premium and hedge-size controls change the scenario analysis. The trade replay deliberately remains tied to the clearly labelled default €8 / 50% ledger; it does not silently switch to a different book.

## Validation

The project has **30 passing local tests** covering:

- Quarterly aggregation, negative prices, missing observations, duplicates, UTC offsets and cache integrity.
- Feature availability, rolling-window availability, model selection and training invariance to future target changes.
- AUC ties, reliability binning and logistic fitting.
- Shared risk limits, kill switch, duplicate protection, chronology, settlement identities and database persistence.
- Full-day cost summaries, empty books, tail statistics and safe report-data embedding.

The report's area/week controls, premium/coverage controls and active-book replay were also checked in the browser.

GitHub Actions is configured for Python 3.11, 3.12 and 3.13. A workflow badge is intentionally omitted: a configured workflow is not evidence of a successful run. Account-level Actions restrictions can prevent execution independently of local test results.

## Repository layout

~~~text
spikeradar/
  data.py        official API ingestion, source fingerprint and strict UTC normalization
  model.py       lag features, logistic regression, probability metrics
  ledger.py      SQLite orders, event history and risk checks
  pipeline.py    chronological evaluation, scenarios and exports
  report.py      self-contained interactive report
  cli.py         reproducible entry points
tests/
  test_spikeradar.py
reports/benchmark/
  report.html
  metrics.json
  forecasts.csv
  orders.csv
  events.csv
  daily_costs.csv
~~~

## Sensible next steps

A prospective evaluation should test a recalibration scheme on a new validation window, monitor probability drift, and compare a severity-aware decision rule. Any executable hedge study also needs independently sourced option quotes, contract terms, transaction costs and liquidity constraints. An untouched future period is needed before making performance claims about those changes.

Code is MIT-licensed. Energinet data remains subject to its source terms; the code license does not replace those terms.

