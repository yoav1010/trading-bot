# paper-log

Automatic records from the paper-trading bot on the `main` branch. Nothing here is written by hand.

- `logs/signals.csv`: every bar the bot evaluated, with the action and the reason
- `logs/trades.csv`: every order it placed (paper trading, simulated money)
- `logs/equity.csv`: paper account equity at each run
- `state/bot_state.json`: what the bot must remember between runs (last bar seen, stop prices, equity peak)

Each commit is one scheduled GitHub Actions run, so the history shows exactly when the bot ran and what it did.
