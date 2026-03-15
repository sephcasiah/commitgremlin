"""
Shared utilities: config loading, path resolution, and JSON helpers.
"""

import json
import os
from pathlib import Path


def _find_config() -> Path:
    """
    Locate config.json. Priority:
      1. COMMITGREMLIN_CONFIG environment variable
      2. config.json in the project root (next to this package)
      3. config.json in CWD
    """
    env = os.environ.get("COMMITGREMLIN_CONFIG")
    if env:
        p = Path(env)
        if p.is_file():
            return p
        raise FileNotFoundError(f"COMMITGREMLIN_CONFIG points to missing file: {env}")

    candidates = [
        Path(__file__).parent.parent / "config.json",  # repo root
        Path.cwd() / "config.json",
    ]
    for c in candidates:
        if c.is_file():
            return c

    raise FileNotFoundError(
        "config.json not found. Set the COMMITGREMLIN_CONFIG env var or place "
        "config.json in the project root."
    )


CONFIG_PATH: Path = _find_config()
BASE_DIR: Path = CONFIG_PATH.parent


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve(path: str) -> Path:
    """Resolve a config path — absolute stays absolute, relative anchors to BASE_DIR."""
    p = Path(path)
    return p if p.is_absolute() else BASE_DIR / p


def read_json(path: Path) -> dict:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
