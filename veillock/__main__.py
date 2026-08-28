"""Allow ``python -m veillock`` to invoke the CLI."""

from veillock.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
