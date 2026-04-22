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
- live-trading-disabled guard
- simulation/live mode consistency checks

## Stored decisions

Every validation stores structured results including:

- approved or rejected status
- rule-by-rule decisions
- human-readable rejection reasons
- mode and strategy context
- audit trail references
