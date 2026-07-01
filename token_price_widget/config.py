"""Load and validate config.yaml."""

import yaml


DEFAULTS = {
    "node": "https://engine.hive.pizza",
    "poll_interval": 300,
    "retention_days": 90,
    "database_url": "sqlite:///prices.db",
    "terminal_currencies": ["hive", "usd"],
    "hive_usd_source": {
        "type": "external_api",
        "url": "https://api.coingecko.com/api/v3/simple/price?ids=hive&vs_currencies=usd",
        "path": "hive.usd",
    },
    "tokens": {},
}


def load_config(path="config.yaml"):
    with open(path) as f:
        user = yaml.safe_load(f) or {}
    cfg = {**DEFAULTS, **user}
    if not cfg["tokens"]:
        raise ValueError("config.yaml must define at least one token")
    return cfg
