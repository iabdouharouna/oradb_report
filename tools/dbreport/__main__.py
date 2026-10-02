"""Point d'entree pour ``python -m dbreport``."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
