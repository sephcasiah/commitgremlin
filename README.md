# CommitGremlin 🟩

I got tired of my GitHub graph being a graveyard because all my real work lives in private repos or never touches GitHub at all. CommitGremlin watches your dev folders, tracks how long you actually worked, and pushes one commit a day to a public activity repo. Green squares, honest numbers, zero exposure of your actual code.

---

## What it does

- Watches configured folders with Watchdog and logs every file change
- Tracks *cumulative* active time — not wall clock. If you step away for 30 minutes, that gap doesn't count. Come back and a new session opens. At commit time it sums all the sessions for the day.
- Logs daily activity to `data/logs/` (JSON + Markdown). Stays local.
- At 23:00 (configurable), updates a README in your public activity repo and pushes one commit:

```
activity 2025-06-14 | active: 6h 23m 10s | files: 47 | builds: 3
```

That's it. Your code stays wherever your code lives.

---

## Install

Python 3.8+ and Git required.

```bash
git clone https://github.com/YOUR_USERNAME/commit-gremlin
cd commit-gremlin
pip install .
```

This drops a `commit-gremlin` command on your PATH.

---

## Getting it talking to GitHub

You need a public repo for the activity and a way to push to it without a password prompt since the daemon runs unattended.

### 1. Create the activity repo

New public repo on GitHub — `dev-activity`, `commit-activity`, whatever. Initialize it with a README so there's something to push onto.

### 2. SSH setup (recommended)

If you don't have a key yet:

```bash
ssh-keygen -t ed25519 -C "your@email.com"
```

Add `~/.ssh/id_ed25519.pub` to **GitHub → Settings → SSH and GPG keys**.

Test it:
```bash
ssh -T git@github.com
# Hi YOUR_USERNAME! You've successfully authenticated...
```

### 3. Clone the activity repo with the SSH URL

```bash
git clone git@github.com:YOUR_USERNAME/dev-activity C:/dev/github-activity-activity
```

Point `activity_repo` in `config.json` at that path and you're done.

### Already on Windows with GitHub Desktop or VS Code?

Git Credential Manager is probably already handling auth for you. Just try a manual push from the activity repo folder — if it goes through without asking for a password, skip everything above.

---

## Configuration

`config.json` next to the package, or point at it anywhere with `COMMITGREMLIN_CONFIG`:

```json
{
  "watch_folders": [
    "C:/dev/MyProject1",
    "C:/dev/MyProject2"
  ],
  "activity_repo": "C:/dev/github-activity-activity",
  "commit_hour": 23,
  "session_timeout_seconds": 1800,
  "ignored_patterns": ["*.pyc", "__pycache__", ".git", "node_modules", "*.log"]
}
```

| Key | Default | Notes |
|-----|---------|-------|
| `watch_folders` | *required* | Absolute or relative to the config file |
| `activity_repo` | *required* | Local clone of your public activity repo |
| `commit_hour` | `23` | 0–23, when the daily commit fires |
| `session_timeout_seconds` | `1800` | Gap length that ends a session |
| `ignored_patterns` | `[]` | Glob patterns, same syntax as `.gitignore` |

Paths work on Windows and Linux as-is.

---

## Usage

```bash
# Start the daemon
commit-gremlin start

# Tell it you ran a build (call this from your build script)
commit-gremlin build
commit-gremlin build -n 3

# Check cumulative stats
commit-gremlin stats

# Force a commit right now (good for testing your setup)
commit-gremlin commit
```

### Hooking into your build process

```makefile
build:
	gcc -o myapp src/*.c
	commit-gremlin build
```

```bat
msbuild MyProject.sln
commit-gremlin build
```

---

## Autostart

### Windows — Task Scheduler

Create a basic task, trigger on log on, action runs `commit-gremlin start`. If you're on a laptop uncheck "only run on AC power" or it'll silently do nothing on battery.

### Linux — systemd user service

`~/.config/systemd/user/commitgremlin.service`:

```ini
[Unit]
Description=CommitGremlin

[Service]
ExecStart=commit-gremlin start
Environment=COMMITGREMLIN_CONFIG=%h/.config/commitgremlin/config.json
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
```

```bash
systemctl --user enable --now commitgremlin
```

---

## Data layout

```
data/
  stats.json        ← running totals
  builds.json       ← today's build count
  logs/
    2025-06-14.json
    2025-06-14.md
```

Only the activity repo README leaves your machine.

---

## Tests

```bash
pip install -e .[dev]
pytest tests/
```

---

## License

MIT
