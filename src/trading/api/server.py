"""Server entry point for `uv run trading-server`."""

import uvicorn


def main() -> None:
    uvicorn.run("trading.api.app:app", host="0.0.0.0", port=9000, reload=True)


if __name__ == "__main__":
    main()
