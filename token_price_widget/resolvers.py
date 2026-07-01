"""
Composable price resolver chain.

Each resolver takes the accumulated price so far and returns a new price
by multiplying by a ratio fetched from its source. Chaining them together
walks from the token's native unit all the way to HIVE or USD.
"""

import requests


def _he_post(node, method, params):
    payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    r = requests.post(f"{node}/contracts", json=payload, timeout=10)
    r.raise_for_status()
    return r.json().get("result")


def resolve_lp(node, pair, role):
    """
    Fetch a Hive-Engine LP pool and return the price ratio for one side.

    role="quote"  → price of the right-hand token in left-hand token terms
                    uses pool quotePrice  (e.g. HSBIDAO:ECOBANK → ECOBANK per HSBIDAO)
    role="base"   → price of the left-hand token in right-hand token terms
                    uses pool basePrice
    """
    result = _he_post(
        node,
        "findOne",
        {"contract": "marketpools", "table": "pools", "query": {"tokenPair": pair}},
    )
    if not result:
        # Try reversed pair
        tokens = pair.split(":")
        reversed_pair = f"{tokens[1]}:{tokens[0]}"
        result = _he_post(
            node,
            "findOne",
            {
                "contract": "marketpools",
                "table": "pools",
                "query": {"tokenPair": reversed_pair},
            },
        )
        if not result:
            raise ValueError(f"LP pool not found: {pair} (also tried reversed)")
        # Flip the role since we found the reversed pair
        role = "base" if role == "quote" else "quote"

    key = "quotePrice" if role == "quote" else "basePrice"
    price = float(result[key])
    return price


def resolve_constant(value):
    return float(value)


def resolve_external_api(url, path):
    """
    Fetch a JSON URL and extract a value by dot-separated path.
    e.g. path="hive.usd" extracts response["hive"]["usd"]
    """
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    data = r.json()
    for key in path.split("."):
        data = data[key]
    return float(data)


def resolve_chain(chain_config, node, hive_usd_source, terminal_currencies):
    """
    Walk a token's resolver chain and return a dict of terminal prices.

    Each step multiplies the running price by a ratio. The chain must end
    with enough steps to reach each requested terminal currency.

    Returns: {"hive": float, "usd": float}  (only keys in terminal_currencies)
    """
    price = 1.0
    hive_price = None
    usd_price = None

    steps = list(chain_config)
    for i, step in enumerate(steps):
        stype = step["type"]

        if stype == "lp":
            ratio = resolve_lp(node, step["pair"], step.get("role", "quote"))
            price *= ratio

        elif stype == "constant":
            price *= resolve_constant(step["value"])

        elif stype == "external_api":
            price *= resolve_external_api(step["url"], step["path"])

        elif stype == "hive_to_usd":
            # Snapshot HIVE price at this point, then multiply for USD
            hive_price = price
            usd_rate = _get_hive_usd(hive_usd_source)
            price = price * usd_rate
            usd_price = price

        else:
            raise ValueError(f"Unknown resolver type: {stype!r}")

    # If the chain never hit hive_to_usd, the final price IS the hive price
    if hive_price is None and "hive" in terminal_currencies:
        hive_price = price
    if usd_price is None and "usd" in terminal_currencies and hive_price is not None:
        usd_rate = _get_hive_usd(hive_usd_source)
        usd_price = hive_price * usd_rate

    result = {}
    if "hive" in terminal_currencies and hive_price is not None:
        result["hive"] = hive_price
    if "usd" in terminal_currencies and usd_price is not None:
        result["usd"] = usd_price
    return result


_hive_usd_cache = {"value": None, "ts": 0}


def _get_hive_usd(source):
    """Fetch HIVE/USD with a 60-second in-process cache to avoid redundant calls."""
    import time

    now = time.time()
    if _hive_usd_cache["value"] is not None and now - _hive_usd_cache["ts"] < 60:
        return _hive_usd_cache["value"]

    stype = source.get("type", "external_api")
    if stype == "external_api":
        value = resolve_external_api(source["url"], source["path"])
    elif stype == "constant":
        value = float(source["value"])
    else:
        raise ValueError(f"Unsupported hive_usd_source type: {stype!r}")

    _hive_usd_cache["value"] = value
    _hive_usd_cache["ts"] = now
    return value
