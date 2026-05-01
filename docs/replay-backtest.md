# Replay / Backtest Scaffold

Replay runs are stored separately from live-forward simulation:

- `replay_runs`
- `replay_model_results`

A replay run records date range, starting cash, selected model profiles, selected symbols, fees, slippage, cash reserve, whether simulated shorts are allowed, and optional simplified market-hours enforcement. Each selected model consumes the same stored market/news input window, and fills use the latest stored price at or before the signal timestamp to avoid future leakage.

Current limitations:

- replay uses stored model signals; it does not yet regenerate every model decision for every historical timestep
- historical coverage is limited to market/news data already stored in the database
- fills are simplified and do not yet model full exchange order books; market-hours checks are deterministic session guards, not full exchange calendars
- replay trades are metrics-only and intentionally do not create normal simulation orders, trades, positions, or cash movements

Model results include latency and model-cost totals when `model_runs` include usage/cost metadata.

Use the Simulation page’s Replay / Backtest section to create a run and compare model results side by side. Use Analytics > Model tournament for combined simulation and replay metrics, or export `/api/v1/analytics/model-comparison.csv`.
