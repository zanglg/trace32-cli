"""Public ``t32`` console entry point."""

from __future__ import annotations

from collections.abc import Iterable

from . import app


def build_parser():
    return app.build_parser()


def main(argv: Iterable[str] | None = None) -> int:
    return app.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
