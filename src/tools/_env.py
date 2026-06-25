"""Load .env and resolve API keys with alias names."""
from __future__ import annotations

import os
from pathlib import Path


def load_env() -> None:
    """Load repo-root .env once (no-op if python-dotenv missing)."""
    if os.environ.get("_CASSANDRA_ENV_LOADED"):
        return
    try:
        from dotenv import load_dotenv
        root = Path(__file__).resolve().parent.parent.parent
        load_dotenv(root / ".env")
        os.environ["_CASSANDRA_ENV_LOADED"] = "1"
    except ImportError:
        pass


def get_key(*names: str, required: bool = False) -> str:
    """Return first non-empty env var from `names`."""
    load_env()
    for name in names:
        val = os.environ.get(name, "").strip()
        if val:
            return val
    if required:
        raise EnvironmentError(f"none of {names} set in .env")
    return ""
