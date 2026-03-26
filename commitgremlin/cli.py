"""
CLI entry point: commit-gremlin <command>
"""

import argparse
import json

from . import tracker, build_hook
from .utils import resolve, DATA_DIR


def main():
    parser = argparse.ArgumentParser(
        prog="commit-gremlin",
        description="Track dev activity and push daily commits to GitHub.",
    )
    sp = parser.add_subparsers(dest="command", metavar="command")

    sp.add_parser("start", help="Start the daemon")

    b = sp.add_parser("build", help="Increment the build counter")
    b.add_argument("-n", "--number", type=int, default=1, metavar="N",
                   help="Number of builds to add (default: 1)")

    sp.add_parser("stats", help="Show cumulative stats")
    sp.add_parser("commit", help="Force a commit right now")

    sp.add_parser("status", help="Show today's in-memory activity (daemon must be running)")

    args = parser.parse_args()

    if args.command == "start":
        tracker.main()

    elif args.command == "build":
        total = build_hook.increment_build(args.number)
        print(f"Added {args.number} build(s). Total today: {total}")

    elif args.command == "stats":
        stats_file = DATA_DIR / "stats.json"
        if stats_file.exists():
            with open(stats_file, encoding="utf-8") as f:
                data = json.load(f)
            # It ~should~ Pretty-print a summary, it may not. YMMV
            total_secs = data.get("total_active_seconds", 0)
            h, rem = divmod(total_secs, 3600)
            m = rem // 60
            print(f"Days logged:       {data.get('total_days_logged', 0)}")
            print(f"Current streak:    {data.get('current_streak', 0)} days")
            print(f"Total active time: {h}h {m:02d}m")
            print(f"Files modified:    {data.get('total_files_modified', 0)}")
            print(f"Total builds:      {data.get('total_builds', 0)}")
        else:
            print("No stats yet — start the daemon and let it run for a day.")

    elif args.command == "status":
        state_file = DATA_DIR / "state.json"
        data = tracker.read_json(state_file)
        if data:
            print(f"--- Today's Activity ({data.get('date')}) ---")
            print(f"Active time:    {data.get('active_time')}")
            print(f"Files modified: {len(data.get('files_modified', []))}")
            print(f"Builds:         {data.get('builds')}")
            print(f"Projects:       {', '.join(data.get('projects', [])) or '\u2014'}")
        else:
            print("No active session data found. Is the daemon running?")

    elif args.command == "commit":
        state_file = DATA_DIR / "state.json"
        if state_file.exists():
            # If daemon is running, it should try to get its latest state
            # for the commit.
            with open(state_file, encoding="utf-8") as f:
                data = json.load(f)
            
            # Update the CLI's in-memory activity state from the daemon's state
            tracker.activity.date = data.get("date")
            tracker.activity.files_modified = set(data.get("files_modified", []))
            tracker.activity.projects = set(data.get("projects", []))
            tracker.activity.builds = data.get("builds", 0)
            tracker.activity._accumulated_seconds = data.get("active_seconds", 0)

        tracker.save_log()
        tracker.commit_activity()
        print("Forced commit done.")

    else:
        parser.print_help()
