"""
Core daemon: watches configured folders, tracks cumulative active time,
and pushes a daily commit to the activity repo.
"""

import datetime
import datetime as dt
import subprocess
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .utils import load_config, resolve, read_json, write_json, DATA_DIR

_cfg = load_config()

WATCH_FOLDERS: list = _cfg.get("watch_folders", [])
ACTIVITY_REPO: Path = resolve(_cfg.get("activity_repo", ""))
COMMIT_HOUR: int = _cfg.get("commit_hour", 23)
IGNORED: list = _cfg.get("ignored_patterns", [])
SESSION_TIMEOUT_SECONDS: int = _cfg.get("session_timeout_seconds", 1800)  # 30 min default you can change this in your config.json

LOG_DIR: Path = DATA_DIR / "logs"
STATS_FILE: Path = DATA_DIR / "stats.json"

class ActivityState:
    """Holds all tracked data for a single calendar day."""

    def __init__(self):
        self.date = datetime.date.today().isoformat()
        self.files_modified = set()
        self.projects = set()
        self.builds = 0

        # Active-time session tracking
        self._session_start = None
        self._last_event = None
        self._accumulated_seconds = 0

    def record_event(self):
        """Call on any file-system activity to advance the active-time clock."""
        now = time.monotonic()

        if self._session_start is None:
            # First event of the day — open a new session.
            # Make sure it shows at least 1s of activity
            self._session_start = now - 1
            self._last_event = now
            return

        gap = now - self._last_event
        if gap > SESSION_TIMEOUT_SECONDS:
            # Gap too long — close the old session and open a fresh one.
            self._accumulated_seconds += int(self._last_event - self._session_start)
            self._session_start = now - 1

        self._last_event = now

    def close_session(self):
        """Flush any open session into the accumulated total."""
        if self._session_start is not None and self._last_event is not None:
            self._accumulated_seconds += int(self._last_event - self._session_start)
            self._session_start = None
            self._last_event = None

    def reset(self):
        """Reset the state for a new day."""
        self.date = datetime.date.today().isoformat()
        self.files_modified = set()
        self.projects = set()
        self.builds = 0
        self._session_start = None
        self._last_event = None
        self._accumulated_seconds = 0

    @property
    def active_seconds(self):
        return self._accumulated_seconds

    @property
    def active_time_str(self):
        total = self._accumulated_seconds
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        return f"{h}h {m:02d}m {s:02d}s"

    def sync_builds(self):
        """Pull the build count written by build_hook so tracker stays in sync."""
        build_file = DATA_DIR / "builds.json"
        data = read_json(build_file)
        self.builds = data.get("builds", 0)

    def to_dict(self):
        # Ensure session is flushed for accurate output in to_dict (used by status)
        # but don't close it permanently.
        temp_accumulated = self._accumulated_seconds
        if self._session_start is not None and self._last_event is not None:
            temp_accumulated += int(self._last_event - self._session_start)

        h, rem = divmod(temp_accumulated, 3600)
        m, s = divmod(rem, 60)
        time_str = f"{h}h {m:02d}m {s:02d}s"

        return {
            "date": self.date,
            "files_modified": sorted(list(self.files_modified)),
            "projects": sorted(list(self.projects)),
            "builds": self.builds,
            "active_seconds": temp_accumulated,
            "active_time": time_str,
        }


activity = ActivityState()

class ChangeHandler(FileSystemEventHandler):
    def on_any_event(self, event):
        if event.is_directory:
            return
        
        # Check if date has changed before recording event
        today = datetime.date.today().isoformat()
        if activity.date != today:
            activity.reset()
            write_json(DATA_DIR / "builds.json", {"builds": 0})
            save_current_state()

        # For moves, we track the destination; for others, the source
        path_str = getattr(event, 'dest_path', event.src_path)
        src = Path(path_str).resolve()
        
        # LOUD DEBUG: Print every event seen
        # print(f"[CommitGremlin] Event: {event.event_type} | Path: {src}")
        # Feel free to leave this commented but if something breaks, this is how you figure what did

        # Ignore anything inside our own data directory to avoid feedback loops
        # Yes ~ This was a problem. No, I didn't see it coming, and yes, I kicked myself for it.
        if DATA_DIR.resolve() in src.parents or DATA_DIR.resolve() == src:
            return

        if any(src.match(pat) for pat in IGNORED):
            return

        abs_path = str(src)
        if abs_path not in activity.files_modified:
            activity.files_modified.add(abs_path)
            print(f"[CommitGremlin] Registered: {abs_path}")
        
        activity.record_event()

        for folder in WATCH_FOLDERS:
            resolved_folder = resolve(folder).resolve()
            # Check if the file is inside this folder (or is the folder itself)
            if resolved_folder == src or resolved_folder in src.parents:
                project_name = resolved_folder.name or str(resolved_folder)
                activity.projects.add(project_name)
        
        save_current_state()


def start_watchers():
    observer = Observer()
    for folder in WATCH_FOLDERS:
        resolved = resolve(folder)
        if resolved.exists():
            observer.schedule(ChangeHandler(), path=str(resolved), recursive=True)
        else:
            print(f"[CommitGremlin] Warning: watch folder does not exist: {resolved}")
    observer.start()
    return observer

def save_current_state():
    """Save the in-memory state for the CLI 'status' command to read."""
    activity.sync_builds()
    state_file = DATA_DIR / "state.json"
    write_json(state_file, activity.to_dict())

def save_log():
    activity.close_session()
    activity.sync_builds()

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    write_json(LOG_DIR / f"{activity.date}.json", activity.to_dict())
    _save_log_md()
    _update_stats()
    _update_readme()


def _save_log_md():
    path = LOG_DIR / f"{activity.date}.md"
    lines = [
        f"# CommitGremlin \u2014 {activity.date}\n\n",
        f"**Active time:** {activity.active_time_str}  \n",
        f"**Projects:** {', '.join(sorted(list(activity.projects))) or '\u2014'}  \n",
        f"**Builds:** {activity.builds}  \n",
        f"**Files modified:** {len(activity.files_modified)}  \n\n",
    ]
    if activity.files_modified:
        lines.append("## Changed files\n\n")
        lines += [f"- `{f}`\n" for f in sorted(list(activity.files_modified))]
    path.write_text("".join(lines), encoding="utf-8")


def _update_stats():
    stats = read_json(STATS_FILE)
    
    # daily_records maps date -> {files, builds, seconds} I may add more fields, but likely not
    # let's be honest, this isn't gonna change the world, just makes the little squares green
    records = stats.setdefault("daily_records", {})
    records[activity.date] = {
        "files": len(activity.files_modified),
        "builds": activity.builds,
        "seconds": activity.active_seconds
    }

    # Math
    stats["total_days_logged"] = len(records)
    stats["total_files_modified"] = sum(r["files"] for r in records.values())
    stats["total_builds"] = sum(r["builds"] for r in records.values())
    stats["total_active_seconds"] = sum(r["seconds"] for r in records.values())

    # More math
    sorted_dates = sorted(records.keys(), reverse=True)
    streak = 0
    if sorted_dates:
        expected = dt.date.fromisoformat(sorted_dates[0])
        today_dt = dt.date.today()
        if expected == today_dt or expected == today_dt - dt.timedelta(days=1):
            for date_str in sorted_dates:
                actual = dt.date.fromisoformat(date_str)
                if actual == expected:
                    streak += 1
                    expected -= dt.timedelta(days=1)
                else:
                    break
    stats["current_streak"] = streak

    write_json(STATS_FILE, stats)


def _update_readme():
    stats = read_json(STATS_FILE)

    total_secs = stats.get("total_active_seconds", 0)
    th, tr = divmod(total_secs, 3600)
    tm = tr // 60
    total_active_str = f"{th}h {tm:02d}m"

    lines = [ # Please remember to update the github link here to your own
      # Also, this is where you can customise your README.md layout before either auto commit or forced commit
        "# CommitGremlin activity\n\n",
        "> Auto-generated by [CommitGremlin](https://github.com/{YOURID}/commitgremlin) "
        "\u2014 a dev activity tracker (honest green square machine).\n\n",
        "## Today\n\n",
        "| Metric | Value |\n",
        "|--------|-------|\n",
        f"| Date | {activity.date} |\n",
        f"| Active time | {activity.active_time_str} |\n",
        f"| Files modified | {len(activity.files_modified)} |\n",
        f"| Builds | {activity.builds} |\n",
        f"| Projects | {', '.join(sorted(list(activity.projects))) or '\u2014'} |\n\n",
        "## All time\n\n",
        "| Metric | Value |\n",
        "|--------|-------|\n",
        f"| Days logged | {stats.get('total_days_logged', 0)} |\n",
        f"| Current streak | {stats.get('current_streak', 0)} days |\n",
        f"| Total active time | {total_active_str} |\n",
        f"| Total files modified | {stats.get('total_files_modified', 0)} |\n",
        f"| Total builds | {stats.get('total_builds', 0)} |\n",
    ]

    readme_path = ACTIVITY_REPO / "README.md"
    readme_path.parent.mkdir(parents=True, exist_ok=True)
    readme_path.write_text("".join(lines), encoding="utf-8")

def commit_activity():
    repo = str(ACTIVITY_REPO)
    if not (ACTIVITY_REPO / ".git").exists():
        print(f"[CommitGremlin] Error: {repo} is not a git repository.")
        return

    subprocess.run(["git", "-C", repo, "add", "."], check=True)
    msg = (
        f"activity {activity.date} | "
        f"active: {activity.active_time_str} | "
        f"files: {len(activity.files_modified)} | "
        f"builds: {activity.builds}"
    )
    result = subprocess.run(["git", "-C", repo, "commit", "-m", msg], capture_output=True)
    if result.returncode == 0:
        subprocess.run(["git", "-C", repo, "push"], check=True)
        print(f"[CommitGremlin] Committed and pushed for {activity.date}")
    else:
        print("[CommitGremlin] Nothing to commit today.")

def main():
    observer = start_watchers()
    print(f"[CommitGremlin] Watching {len(WATCH_FOLDERS)} folder(s). Commit at {COMMIT_HOUR:02d}:00.")
    
    last_commit_date = None
    
    try:
        while True:
            now = datetime.datetime.now()
            today = now.date().isoformat()
            
            if activity.date != today:
                save_log()
                print(f"[CommitGremlin] Day changed to {today}. Resetting tracker.")
                activity.reset()
                write_json(DATA_DIR / "builds.json", {"builds": 0})
                save_current_state()

            if now.hour == COMMIT_HOUR and last_commit_date != today:
                save_log()
                commit_activity()
                last_commit_date = today
            
            save_current_state()
            time.sleep(30)
    except KeyboardInterrupt:
        print("\n[CommitGremlin] Shutting down...")
    finally:
        observer.stop()
        observer.join()
