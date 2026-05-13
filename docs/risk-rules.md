# Risk Rules

The risk engine is central and validates every order path.

## Supported rules in the MVP scaffold

- kill switch
- max position size
- max capital per asset
- max open positions
- daily max loss
- per-trade risk percent
- duplicate/conflicting open order checks
- cash reserve for buy-like actions and simulated shorts
- simulated short margin requirement
- simplified exchange-hours guard
- simulated margin-call forced-close scaffold
- live-trading-disabled guard
- simulation/live mode consistency checks

## Cash reserve

The `cash_reserve` rule enforces “Always keep X% in cash.” It uses account value to calculate required cash, then exposes reserved cash and available-to-trade cash in Live and Simulation.

Example: with a 10,000 portfolio and a 20% reserve, 2,000 must remain in cash. New buy orders and simulated shorts can only use cash above that reserve. Closing/reducing long positions and covering shorts are not blocked by the reserve because they reduce exposure.

Simulation accounts can override the global reserve independently per provider/model account.

## Fractional sizing

Orders support three sizing modes:

- `percentage`: invest a share of portfolio value, such as 5% of the account
- `amount`: invest a fixed currency notional, such as 100 USD
- `quantity`: explicitly trade a quantity, including fractional values like 0.25 shares

Risk checks validate notional value rather than whole-share counts. When an otherwise valid order is too large for cash, cash reserve, max position size, asset allocation, sector allocation, or current holdings, the response includes `max_allowed_order_value` and `max_allowed_quantity`. Manual and automation order paths can use those values to resize to the maximum allowed fractional order. If no positive allowed amount remains, the order is rejected with the rule reason.

Simulation accounts also have `decimal_precision`. Fills round quantity down at that precision and store a warning in the order audit context when rounding changed the requested size.

## Short behavior

Live Trading212 shorting is rejected because the adapter does not confirm short execution support. Simulation can open `short` and `cover_short` only when `short_enabled` is enabled for the selected simulation account.

The scaffold includes short borrow fee and margin requirement settings. A margin-call helper can force-close simulated shorts when account equity falls below the configured margin requirement. This is still a simplified model: it does not represent locate availability, broker-specific maintenance tiers, or intraday liquidation sequencing.

## Market hours

Simulation accounts can enable a market-hours guard. The guard uses a small exchange profile table for common US, London, and Xetra sessions, respects configured holiday dates, skips manual/test exchanges, and can either allow or block unknown exchanges. This is not a full exchange calendar, but it prevents obviously out-of-session simulated fills and replay trades.

## Stop provenance

Protective levels are normalized into `position_stop_events` when positions are created, stops are edited, simulated fills apply stop/take-profit/trailing-stop levels, or a simulated margin call forces a close. Signal/order/trade/position traces include these stop events alongside legacy audit-derived entries.

## Stored decisions

Every validation stores structured results including:

- approved or rejected status
- rule-by-rule decisions
- human-readable rejection reasons
- mode and strategy context
- audit trail references
