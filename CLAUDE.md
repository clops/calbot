# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Calbot** is a Telegram calorie and macronutrient tracker bot. Users send food descriptions or photos; the bot estimates calories and macros (protein, fat, carbs) using Claude AI and logs them to SQLite. The bot is running in production on `ether.emind.at`.

## Environment Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt        # production deps
pip install -r requirements-dev.txt    # adds pytest + plugins
```

Requires a `.env` file (not committed):
```
BOT_TOKEN=<from @BotFather>
ANTHROPIC_API_KEY=<from console.anthropic.com>
ALLOWED_USER_IDS=<comma-separated Telegram user IDs>
LOG_LEVEL=INFO   # optional, defaults to INFO
```

## Running the Bot

```bash
source venv/bin/activate
python main.py
```

## Running Tests

```bash
source venv/bin/activate
pytest
```

77 tests, no API keys or network access required (everything is mocked).

## Architecture

```
calbot/
├── main.py                  # entry point: wiring, allowlist, keyboard, polling
├── handlers/
│   └── food.py              # Telegram handlers (text, photo, today, history, cancel, undo, settings)
├── services/
│   ├── claude.py            # Claude API + per-user conversation state
│   └── database.py          # aiosqlite CRUD (init_db, log_meal, get_today, get_history, delete_last_meal, get_user_settings, toggle_setting)
└── utils/
    └── photos.py            # Telegram photo download → base64
```

### Key design decisions
- **Polling mode** — no inbound ports, no webhook, no TLS cert needed
- **Allowlist** — `ALLOWED_USER_IDS` env var gates all handlers via `filters.User`
- **Lazy Claude client** — `AsyncAnthropic` instantiated on first use so tests import cleanly
- **In-memory conversation state** — `_conversations: dict[int, list[dict]]` in `services/claude.py`; cleared after successful log or `/cancel`
- **JSON fence stripping** — `_parse_response` strips markdown code fences before `json.loads()`
- **Model** — `claude-haiku-4-5-20251001` (fast, cheap, sufficient for calorie estimation)

### Claude response format
```json
{"food_items": ["item"], "calories_estimate": 450, "proteins_g": 20, "fats_g": 15, "carbohydrates_g": 60, "confidence": 0.8, "clarifying_question": null}
```
If `clarifying_question` is set, the handler replies with the question and returns without logging.
Macro fields (`proteins_g`, `fats_g`, `carbohydrates_g`) are `int | None` — parsed with `.get()` so missing fields degrade gracefully to `None`.

### Database schema
```sql
CREATE TABLE meals (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    timestamp     TEXT    NOT NULL,   -- ISO 8601 UTC
    description   TEXT    NOT NULL,
    calories      INTEGER NOT NULL,
    input_type    TEXT    NOT NULL,   -- "text" or "photo"
    proteins      INTEGER,            -- grams, NULL for rows logged before macros were added
    fats          INTEGER,            -- grams
    carbohydrates INTEGER             -- grams
);
```
Macro columns are added automatically by `init_db()` via `ALTER TABLE ADD COLUMN` if missing (migration-safe for existing production data).

```sql
CREATE TABLE user_settings (
    user_id              INTEGER PRIMARY KEY,
    show_calories        INTEGER NOT NULL DEFAULT 1,
    show_proteins        INTEGER NOT NULL DEFAULT 1,
    show_fats            INTEGER NOT NULL DEFAULT 1,
    show_carbohydrates   INTEGER NOT NULL DEFAULT 1
);
```
Per-user display preferences. Created by `init_db()`. Row is inserted on first toggle; absent row means all fields shown.

## Deployment

**Server:** `ether.emind.at`, Ubuntu 22, SSH on port 2000
**Service user:** `calbot` (home: `/opt/calbot`)
**Service file:** `calbot.service` (copy to `/etc/systemd/system/`)

```bash
# Deploy manually
ssh -p 2000 calbot@ether.emind.at
cd /opt/calbot && git pull origin master
venv/bin/pip install -r requirements.txt --quiet
sudo systemctl restart calbot
```

**CI/CD:** `.github/workflows/deploy.yml` — runs pytest then auto-deploys on every push to `master` if tests pass. Requires `DEPLOY_SSH_KEY` GitHub secret.

## Day-to-day server operations

```bash
systemctl status calbot
systemctl restart calbot
journalctl -u calbot -f
journalctl -u calbot --since today
```
