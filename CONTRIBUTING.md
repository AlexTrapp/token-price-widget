# Contributing

This is Open Source — issues, comments, and pull requests are welcome.

A few ground rules that keep review fast for everyone:

1. Use issues, or tightly-scoped PRs. One resolver type, one storage backend, one bug — not a grab bag.
2. Comments welcome, including disagreement with a design decision. This project is opinionated on purpose (see the README's "How it works" section); if you think a default is wrong, open an issue and make the case.
3. We are happy to review real effort. A PR that adds a new resolver step type or storage backend should include a short usage example in the PR description, matching the style already in `config.example.yaml`.

## Adding a resolver step type

New step types live in `token_price_widget/resolvers.py` and are dispatched by `resolve_chain`. Keep them pure: given inputs, return a float ratio, no side effects, no I/O beyond what's needed to answer that one step.

## Adding a storage backend

Only SQLite and flat-JSON ship today. If you want Postgres, Mongo, or something else, implement the abstract interface in `token_price_widget/storage/base.py` and register the new URL scheme in `token_price_widget/storage/__init__.py`'s `get_storage()` dispatch (see `sqlite.py` and `json_file.py` for reference implementations). This is exactly the kind of tightly-scoped PR described above — one backend per PR.

## Running locally

```bash
uv sync
cp config.example.yaml config.yaml
uv run token-price-tracker --config config.yaml
uv run token-price-widget --config config.yaml --port 5050
```
