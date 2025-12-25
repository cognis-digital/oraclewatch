# Demo 01 - Basic oracle health check

This demo runs ORACLEWATCH against `feeds.json`, a snapshot of five price-oracle
feeds across three pairs. The evaluation clock is pinned to `1717000600`
(unix seconds) so the output is reproducible.

## The feeds

| Feed                    | Pair    | Issue planted                                   |
|-------------------------|---------|-------------------------------------------------|
| ETH/USD chainlink       | ETH/USD | healthy (on consensus, fresh)                   |
| ETH/USD backup-cex      | ETH/USD | healthy peer (provides consensus)               |
| ETH/USD dex-twap        | ETH/USD | **STALE** - 2h old vs 1h heartbeat              |
| BTC/USD chainlink       | BTC/USD | **DEVIATION** - +4.7% off consensus + thin pool |
| BTC/USD backup-cex      | BTC/USD | healthy peer                                    |
| LINK/USD chainlink      | LINK/USD| **FROZEN** + **ROUND_STALLED** + cheap to attack|

## Run it

```bash
# Table output
python -m oraclewatch check demos/01-basic/feeds.json --now 1717000600

# JSON for CI (exit code 1 because findings are present)
python -m oraclewatch check demos/01-basic/feeds.json --now 1717000600 --format json
```

## Expected result

- The two ETH backup/chainlink feeds and the BTC backup feed report **healthy**.
- `ETH/USD dex-twap` is flagged **STALE** (age 7200s > 3600s heartbeat, CRITICAL
  because it is over 2x the heartbeat).
- `BTC/USD chainlink` is flagged **DEVIATION** (price ~4.7% above the median
  consensus of its peers) and **CHEAP_TO_ATTACK** (shallow liquidity).
- `LINK/USD chainlink` is flagged **FROZEN** (price == prev_price),
  **ROUND_STALLED** (round_id == prev_round_id) and **CHEAP_TO_ATTACK**.
- Because WARNING/CRITICAL findings exist, the process exits with code **1** -
  a CI gate would fail the build.
