"""
Shared utilities: config loading, path resolution, and JSON helpers.
"""

import json
import os
import tempfile
from pathlib import Path


def _find_config() -> Path:
    """
    Locate config.json. Priority:
      1. COMMITGREMLIN_CONFIG environment variable
      2. config.json in CWD (Current Working Directory)
      3. config.json in ~/.commitgremlin/
      4. config.json in the project root (fallback)
    """
    env = os.environ.get("COMMITGREMLIN_CONFIG")
    if env:
        p = Path(env).expanduser()
        if p.is_file():
            return p
        raise FileNotFoundError(f"COMMITGREMLIN_CONFIG points to missing file: {env}")

    candidates = [
        Path.cwd() / "config.json",
        Path.home() / ".commitgremlin" / "config.json",
        Path(__file__).parent.parent / "config.json",
    ]
    for c in candidates:
        if c.is_file():
            return c

    # Default to home directory path if nothing exists yet
    return Path.home() / ".commitgremlin" / "config.json"


CONFIG_PATH: Path = _find_config()
BASE_DIR: Path = CONFIG_PATH.parent


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


_cfg = load_config()


def resolve(path: str) -> Path:
    """
    Resolve a config path:
      - Absolute stays absolute
      - Starts with ~ resolves to home
      - Relative anchors to BASE_DIR (where config.json is)
    """
    if not path:
        return Path.cwd()
    p = Path(path).expanduser()
    if p.is_absolute():
        return p
    return BASE_DIR / p


# Data directory: priority config['data_dir'], then ~/.commitgremlin/data
def _get_data_dir() -> Path:
    cfg_data = _cfg.get("data_dir")
    if cfg_data:
        return resolve(cfg_data)
    
    return Path.home() / ".commitgremlin" / "data"


DATA_DIR: Path = _get_data_dir()


def read_json(path: Path) -> dict:
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return {}
                return json.loads(content)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def write_json(path: Path, data: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Create temp file in the same directory as the target path
        with tempfile.NamedTemporaryFile('w', dir=str(path.parent), delete=False, encoding='utf-8') as tf:
            json.dump(data, tf, indent=2)
            tempname = tf.name
        
        # Replace the original file with the temp file (atomic on most systems)
        if os.path.exists(path):
            os.remove(path)
        os.rename(tempname, str(path))
    except (IOError, OSError) as e:
        print(f"[CommitGremlin] Error writing to {path}: {e}")
