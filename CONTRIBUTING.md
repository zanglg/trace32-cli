# Contributing

Development currently targets the `dev` branch. `main` is reserved for tested integration.

## Setup

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m pip install pytest ruff build
```

Or use `uv` equivalents.

## Validation

```bash
ruff check .
python -m pytest
python -m build
```

Changes that affect CLI behavior should include tests and update README/help text where applicable.

## Pull requests

- Target `dev` during initial development.
- Keep changes focused.
- State whether the change mutates the CLI grammar or JSON contract.
- Do not include proprietary target scripts, credentials, debug-unlock material, or confidential SoC information.
