"""
Flask server: JSON price API + embeddable Chart.js chart page.

Endpoints:
  GET /price/<token>                    latest price snapshot
  GET /history/<token>?since=&limit=   time-series JSON
  GET /chart/<token>?currency=hive|usd embeddable chart page
  GET /tokens                           list configured tokens
"""

import functools
import os
import time
from datetime import datetime, timezone

from flask import Flask, abort, jsonify, render_template_string, request

from .config import load_config
from .storage import get_storage

app = Flask(__name__)
_cfg = None
_storage = None

_response_cache = {}
CACHE_TTL_SECONDS = 30


def cached_response(view):
    """
    Cache a view's response per full request path (including query string)
    for CACHE_TTL_SECONDS. Keeps repeated polling (e.g. an embedded chart's
    auto-refresh, or a burst of crawler/client requests) from re-hitting the
    database and upstream price sources on every call.
    """

    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        key = request.full_path
        now = time.time()
        cached = _response_cache.get(key)
        if cached and now - cached[0] < CACHE_TTL_SECONDS:
            return cached[1]
        result = view(*args, **kwargs)
        _response_cache[key] = (now, result)
        return result

    return wrapper


def _get_cfg():
    global _cfg
    if _cfg is None:
        _cfg = load_config(os.environ.get("CONFIG_PATH", "config.yaml"))
    return _cfg


def _get_storage():
    global _storage
    if _storage is None:
        _storage = get_storage(_get_cfg()["database_url"])
    return _storage


@app.route("/tokens")
def list_tokens():
    cfg = _get_cfg()
    return jsonify({"tokens": list(cfg["tokens"].keys())})


@app.route("/price/<token>")
@cached_response
def latest_price(token):
    cfg = _get_cfg()
    token = token.upper()
    if token not in cfg["tokens"]:
        abort(404, f"Token {token!r} not in config")
    row = _get_storage().get_latest(token)
    if not row:
        return jsonify({"token": token, "price": None, "message": "No snapshots yet"}), 202
    return jsonify({
        "token": token,
        "ts": row["ts"],
        "price_hive": row.get("price_hive"),
        "price_usd": row.get("price_usd"),
    })


@app.route("/history/<token>")
@cached_response
def price_history(token):
    cfg = _get_cfg()
    token = token.upper()
    if token not in cfg["tokens"]:
        abort(404, f"Token {token!r} not in config")

    since_str = request.args.get("since")
    limit = int(request.args.get("limit", 500))
    since = None
    if since_str:
        since = datetime.fromisoformat(since_str).replace(tzinfo=timezone.utc)

    rows = _get_storage().get_history(token, since=since, limit=limit)
    return jsonify({"token": token, "count": len(rows), "history": rows})


_CHART_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ token }} Price</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.5.0/dist/chart.umd.min.js" integrity="sha384-XcdcwHqIPULERb2yDEM4R0XaQKU3YnDsrTmjACBZyfdVVqjh6xQ4/DCMd7XLcA6Y" crossorigin="anonymous"></script>
  <style>
    body { margin: 0; background: transparent; font-family: sans-serif; }
    .container { padding: 8px; }
    canvas { max-width: 100%; }
    .label { font-size: 12px; color: #666; text-align: center; margin-top: 4px; }
  </style>
</head>
<body>
<div class="container">
  <canvas id="chart"></canvas>
  <div class="label">{{ token }} price in {{ currency.upper() }}</div>
</div>
<script>
  const API = "{{ api_base }}";
  const TOKEN = "{{ token }}";
  const CURRENCY = "{{ currency }}";
  const LIMIT = {{ limit }};

  async function load() {
    const resp = await fetch(`${API}/history/${TOKEN}?limit=${LIMIT}`);
    const data = await resp.json();
    const rows = data.history.slice().reverse();  // oldest first for chart
    const labels = rows.map(r => new Date(r.ts).toLocaleString());
    const prices = rows.map(r => CURRENCY === "usd" ? r.price_usd : r.price_hive);

    new Chart(document.getElementById("chart"), {
      type: "line",
      data: {
        labels,
        datasets: [{
          label: `${TOKEN} / ${CURRENCY.toUpperCase()}`,
          data: prices,
          borderColor: "#f5a623",
          backgroundColor: "rgba(245,166,35,0.1)",
          borderWidth: 2,
          pointRadius: 2,
          tension: 0.3,
          fill: true,
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          x: { display: false },
          y: { ticks: { maxTicksLimit: 5 } }
        }
      }
    });
  }

  load();
</script>
</body>
</html>"""


@app.route("/chart/<token>")
@cached_response
def chart(token):
    cfg = _get_cfg()
    token = token.upper()
    if token not in cfg["tokens"]:
        abort(404, f"Token {token!r} not in config")

    currency = request.args.get("currency", cfg["terminal_currencies"][0])
    limit = int(request.args.get("limit", 288))  # default: 288 × 5min = 24h

    # Derive API base from the request so the chart JS can call back
    api_base = request.url_root.rstrip("/")

    return render_template_string(
        _CHART_TEMPLATE,
        token=token,
        currency=currency,
        api_base=api_base,
        limit=limit,
    )


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Token price widget server")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5050)
    args = parser.parse_args()

    os.environ["CONFIG_PATH"] = args.config
    app.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
