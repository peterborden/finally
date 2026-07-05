"""Module entry point: `python -m app` launches the FinAlly server."""

from __future__ import annotations

import uvicorn


def main() -> None:
    """Run the FinAlly FastAPI app with uvicorn on port 8000."""
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
