"""Command-line entry point (`sparklchat`) for running the development server."""

import uvicorn


def main() -> None:
    uvicorn.run("sparklchat.main:app", host="127.0.0.1", port=8000, reload=True)
