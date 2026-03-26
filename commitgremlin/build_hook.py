"""
Build hook: call `commit-gremlin build` (or import this directly) to
increment the build counter. tracker.py reads this file at commit time
so both stay in sync.
"""

from .utils import resolve, read_json, write_json

BUILD_FILE = resolve("data") / "builds.json"


def increment_build(count: int = 1) -> int:
    # Increment build count by *count* and return the new total. 
    #I will figure out how to automate this, but until then, 
    # remember to run the counter per build otherwise feel free to ignore
    data = read_json(BUILD_FILE)
    data.setdefault("builds", 0)
    data["builds"] += count
    write_json(BUILD_FILE, data)
    return data["builds"]


def current_build() -> int:
    # Returns the current build count - Please note build count may not update local stats until 30 seconds AFTER command is run
    return read_json(BUILD_FILE).get("builds", 0)
