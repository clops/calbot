# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Calbot** is a Telegram calorie tracker bot. Users send food descriptions or photos; the bot estimates calories using Claude AI and logs them to SQLite. See `ROADMAP.md` for the phased build plan.

## Environment Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Requires a `.env` file (not committed):
```
BOT_TOKEN=<from @BotFather>
ANTHROPIC_API_KEY=<from console.anthropic.com>
LOG_LEVEL=INFO   # optional, defaults to INFO
```

## Running the Bot

```bash
source venv/bin/activate
python main.py
```

## Architecture

The project follows a layered structure being built phase-by-phase:

- **`main.py`** — entry point; registers Telegram command/message handlers and starts polling
- **`handlers/`** — Telegram handler functions (to be extracted from main.py in Phase 2+)
- **`services/`** — business logic: Claude API calls, calorie estimation, clarifying question loop
- **`utils/`** — shared helpers (e.g., base64 photo encoding for vision)
- **`data/`** — SQLite database files (`.db` files are gitignored)

### Phase 2 design (Claude integration)
Claude responses should be structured JSON:
```json
{"food_items": [...], "calories_estimate": 450, "confidence": 0.8, "clarifying_question": null}
```
Per-user conversation state for the clarifying loop is kept in an in-memory dict keyed by `user_id`.

### Phase 3 design (SQLite)
Schema: `user_id | timestamp | description | calories | input_type`
Use `aiosqlite` for async DB access compatible with `python-telegram-bot`'s async handlers.

### Photo handling (Phase 2)
Download the highest-resolution photo from `update.message.photo[-1]`, base64-encode it, and pass to Claude vision API.

## Deployment Target

Server: `ether.emind.at` — run as a `systemd` service in polling mode (no webhook needed).
