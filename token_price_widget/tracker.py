"""
Scheduler: poll all configured tokens → resolve prices → store → prune.

Run directly:  python -m token_price_widget.tracker
Or via CLI:    token-price-tracker
"""

import logging
import time
from datetime import datetime, timedelta, timezone

from .config import load_config
from .resolvers import resolve_chain
from .storage import get_storage

log = logging.getLogger(__name__)


def tick(cfg, storage):
    now = datetime.now(timezone.utc)
    for token, token_cfg in cfg["tokens"].items():
        try:
            prices = resolve_chain(
                token_cfg["chain"],
                cfg["node"],
                cfg["hive_usd_source"],
                cfg["terminal_currencies"],
            )
            storage.save_snapshot(token, prices, token_cfg["chain"], ts=now)
            log.info("Snapshot saved: %s → %s", token, prices)
        except Exception as e:
            log.error("Failed to resolve %s: %s", token, e)

    # Prune old snapshots
    retention = cfg.get("retention_days")
    if retention:
        cutoff = now - timedelta(days=retention)
        for token in cfg["tokens"]:
            storage.prune(token, cutoff)


def run(config_path="config.yaml"):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = load_config(config_path)
    storage = get_storage(cfg["database_url"])
    interval = cfg["poll_interval"]

    log.info(
        "Tracker started — tokens: %s, interval: %ss",
        list(cfg["tokens"]),
        interval,
    )

    while True:
        tick(cfg, storage)
        time.sleep(interval)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Token price tracker")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()
    run(args.config)


if __name__ == "__main__":
    main()
