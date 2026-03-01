"""Server entry point for `uv run trading-server`."""

import uvicorn

from trading.core.logging import configure_logging


def main() -> None:
    configure_logging()
    uvicorn.run("trading.api.app:app", host="0.0.0.0", port=9000, reload=True)


if __name__ == "__main__":
    main()
