# token-price-widget

A composable, embeddable price tracker for [Hive-Engine](https://hive-engine.com/) tokens.

Resolves token prices by chaining together configurable steps — LP pool ratios, known pegs, and external price feeds — and stores snapshots over time so you can display a price chart on your token's site.

---

## How it works

Prices are derived by walking a **resolution chain** defined in your config. Each step multiplies the running price by a ratio from one of these sources:

| Step type | What it does |
|---|---|
| `lp` | Reads a Hive-Engine LP pool and returns the price ratio for the base or quote token |
| `constant` | Applies a fixed multiplier (e.g. a known soft peg) |
| `external_api` | Fetches a JSON URL and extracts a value by dot path |
| `hive_to_usd` | Converts the current HIVE-denominated price to USD using your configured source |

**Example chain for ECOBANK:**

```
ECOBANK ──[LP: HSBIDAO:ECOBANK]──► HSBIDAO ──[constant: 0.5]──► HIVE ──[hive_to_usd]──► USD
```

Chains are composable — any token with a path to a known anchor (HIVE, USD, etc.) can be tracked. Multi-hop chains work too:

```
MYTOKEN ──[LP: BEE:MYTOKEN]──► BEE ──[LP: SWAP.HIVE:BEE]──► SWAP.HIVE ──[constant: 1.0]──► HIVE
```

---

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

---

## Installation

```bash
git clone <your-repo-url>
cd token-price-widget
uv sync
```

Or with pip:

```bash
pip install -e .
```

For PostgreSQL support:

```bash
uv sync --extra postgres
```

For MongoDB support:

```bash
uv sync --extra mongo
```

---

## Configuration

Copy the example config and edit it:

```bash
cp config.example.yaml config.yaml
```

### Full config reference

```yaml
# Hive-Engine node to query
node: "https://engine.hive.pizza"

# Seconds between price snapshots
poll_interval: 300

# Delete snapshots older than this many days (null = keep forever)
retention_days: 90

# Storage backend connection string
# SQLite (default, no extra deps):
database_url: "sqlite:///prices.db"
# PostgreSQL:
# database_url: "postgresql://user:pass@localhost/mydb"
# MongoDB:
# database_url: "mongodb://localhost:27017/mydb"
# Flat JSON file (dev/testing):
# database_url: "json:///prices.json"

# Which currencies to resolve prices into (one or both)
terminal_currencies:
  - hive
  - usd

# How to get the HIVE/USD rate
hive_usd_source:
  type: external_api
  url: "https://api.coingecko.com/api/v3/simple/price?ids=hive&vs_currencies=usd"
  path: "hive.usd"
  # Alternatively, use a fixed rate for testing:
  # type: constant
  # value: 0.25

# Token resolution chains
tokens:
  ECOBANK:
    chain:
      - type: lp
        pair: "HSBIDAO:ECOBANK"
        role: quote       # "quote" = price the right-hand token in left-hand terms
                          # "base"  = price the left-hand token in right-hand terms
      - type: constant
        value: 0.5        # HSBIDAO soft-peg: 1 HSBIDAO = 0.5 HIVE
      - type: hive_to_usd # converts running HIVE price to USD, stores both
```

### `role` in LP steps

When you add an `lp` step, you must tell the resolver which side of the pair you are pricing:

- `role: quote` — you want the price of the **right-hand** token (e.g. in `HSBIDAO:ECOBANK`, you want ECOBANK priced in HSBIDAO)
- `role: base` — you want the price of the **left-hand** token

The resolver will automatically try the reversed pair if the pool is not found under the name you provided, adjusting the role accordingly.

---

## Running

### 1. Start the price tracker (background poller)

This polls Hive-Engine on your configured interval and writes snapshots to the database.

```bash
uv run token-price-tracker --config config.yaml
```

Or directly:

```bash
uv run python -m token_price_widget.tracker --config config.yaml
```

You will see log output like:

```
2026-07-01 12:00:00 INFO Tracker started — tokens: ['ECOBANK'], interval: 300s
2026-07-01 12:00:01 INFO Snapshot saved: ECOBANK → {'hive': 26.79, 'usd': 6.70}
```

### 2. Start the API server

```bash
uv run token-price-widget --config config.yaml --port 5050
```

Or directly:

```bash
uv run python -m token_price_widget.server --config config.yaml --port 5050
```

---

## API endpoints

### `GET /tokens`
List all configured tokens.
```json
{"tokens": ["ECOBANK"]}
```

### `GET /price/<TOKEN>`
Latest price snapshot.
```json
{
  "token": "ECOBANK",
  "ts": "2026-07-01T12:00:01+00:00",
  "price_hive": 26.79,
  "price_usd": 6.70
}
```

### `GET /history/<TOKEN>`
Time-series data, newest first.

| Query param | Default | Description |
|---|---|---|
| `since` | — | ISO 8601 timestamp to filter from |
| `limit` | 500 | Max number of rows to return |

```bash
curl "http://localhost:5050/history/ECOBANK?limit=10"
curl "http://localhost:5050/history/ECOBANK?since=2026-07-01T00:00:00"
```

### `GET /chart/<TOKEN>`
Self-contained HTML page with a Chart.js line chart. Designed to be embedded as an `<iframe>`.

| Query param | Default | Description |
|---|---|---|
| `currency` | first in `terminal_currencies` | `hive` or `usd` |
| `limit` | 288 | Number of snapshots to display (288 × 5 min = 24 h) |

```bash
# View in browser
open http://localhost:5050/chart/ECOBANK?currency=hive

# Embed on your site
<iframe src="https://your-server/chart/ECOBANK?currency=usd" width="600" height="300" frameborder="0"></iframe>
```

---

## Testing the resolver without the server

You can test a chain directly from a Python shell before running the full stack:

```python
from token_price_widget.config import load_config
from token_price_widget.resolvers import resolve_chain

cfg = load_config("config.yaml")
token_cfg = cfg["tokens"]["ECOBANK"]

prices = resolve_chain(
    token_cfg["chain"],
    cfg["node"],
    cfg["hive_usd_source"],
    cfg["terminal_currencies"],
)
print(prices)
# {'hive': 26.79, 'usd': 6.70}
```

Or as a one-liner from the terminal:

```bash
uv run python -c "
from token_price_widget.config import load_config
from token_price_widget.resolvers import resolve_chain
cfg = load_config('config.yaml')
tc = cfg['tokens']['ECOBANK']
print(resolve_chain(tc['chain'], cfg['node'], cfg['hive_usd_source'], cfg['terminal_currencies']))
"
```

---

## Storage backends

| URL scheme | Backend | Extra dep |
|---|---|---|
| `sqlite:///path.db` | SQLite (default) | none |
| `json:///path.json` | Flat JSON file | none |
| `postgresql://...` | PostgreSQL | `pip install -e ".[postgres]"` |
| `mongodb://...` | MongoDB | `pip install -e ".[mongo]"` |

---

## Deployment

The tracker and server are two separate processes. Run them together with a process manager or two terminal tabs:

```bash
# Tab 1 — poller
uv run token-price-tracker

# Tab 2 — API + chart server
uv run token-price-widget --host 0.0.0.0 --port 5050
```

For production, run the server under gunicorn:

```bash
uv run gunicorn "token_price_widget.server:app" --bind 0.0.0.0:5050
```

For the tracker, use a systemd service, supervisor, or a cron job:

```cron
# Poll every 5 minutes via cron instead of the built-in loop
*/5 * * * * cd /path/to/token-price-widget && uv run python -m token_price_widget.tracker --once
```

> **Note:** `--once` mode (single poll then exit) is not yet implemented but is the right pattern for cron-based deployment. The current tracker runs as a continuous loop.

---

## Adding a new token

1. Add an entry under `tokens:` in `config.yaml`
2. Define the chain from the token's LP pair all the way to your terminal currency
3. Restart the tracker — it will begin collecting snapshots immediately

No code changes required.

---

## Project structure

```
token-price-widget/
  config.example.yaml          # copy to config.yaml
  pyproject.toml
  token_price_widget/
    config.py                  # config loader
    resolvers.py               # chain resolver nodes
    tracker.py                 # polling loop
    server.py                  # Flask API + chart
    storage/
      base.py                  # abstract interface
      sqlite.py                # SQLite backend
      json_file.py             # flat JSON backend
```
