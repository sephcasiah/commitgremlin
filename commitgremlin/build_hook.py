"""
Build hook: call `commit-gremlin build` (or import this directly) to
increment the build counter. tracker.py reads this file at commit time
so both stay in sync.
"""

from .utils import DATA_DIR, read_json, write_json

BUILD_FILE = DATA_DIR / "builds.json"


def increment_build(count: int = 1) -> int:
    # Increment build count by *count* and return the new total
    # I will eventually figure out how to automate this.
    data = read_json(BUILD_FILE)
    data.setdefault("builds", 0)
    data["builds"] += count
    write_json(BUILD_FILE, data)
    return data["builds"]


def current_build() -> int:
    # Return the current build count without modifying it.
    return read_json(BUILD_FILE).get("builds", 0)
