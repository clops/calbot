# Calbot 🍽️

A personal Telegram calorie tracker powered by Claude AI. Send a text description or a photo of your food — the bot estimates calories and macronutrients (protein, fat, carbs) and logs them. Ask it what you've eaten today or over the last week.

## Features

- **Text & photo input** — describe your meal or snap a photo; nutrition labels are also supported
- **Calories + macros** — estimates kcal, protein, fat, and carbohydrates per meal
- **Claude vision** — photo analysis via Claude Haiku
- **Clarifying questions** — when Claude needs more info it asks; `/cancel` to abort
- **Persistent log** — SQLite, survives restarts
- **`/today`** — today's meals with calorie and macro totals; shows progress vs daily targets when a profile is set
- **`/history`** — 7-day summary grouped by date with goal icons (✅ on track, ⚠️ over, ❌ under)
- **`/undo`** — remove the last logged meal
- **`/settings`** — toggle visible nutrients, enable/disable daily reminders, choose language
- **`/profile`** — guided setup for weight, height, age, sex, activity level, and goal; computes daily calorie & macro targets via Mifflin-St Jeor
- **Multi-language** — full i18n for English, German, and Russian (UI, keyboard, Claude responses)
- **Daily reminders** — opt-in nudge at 20:00 CET with a Claude-generated message in your language
- **Allowlist** — only authorised Telegram user IDs can interact
- **Systemd service** — auto-restarts on crash, survives reboots
- **CI/CD** — pytest runs on every push; deploys to production only if tests pass

## Tech stack

| Layer | Choice |
|---|---|
| Bot framework | python-telegram-bot 22 |
| AI | Anthropic Claude Haiku (`claude-haiku-4-5-20251001`) |
| Database | SQLite via aiosqlite |
| Runtime | Python 3.11+, polling mode |
| Hosting | Ubuntu 22, systemd |
| CI/CD | GitHub Actions |

## Project structure

```
calbot/
├── main.py                  # entry point — wiring, allowlist, keyboard, daily reminders
├── handlers/
│   ├── food.py              # Telegram handlers (text, photo, today, history, cancel, undo, settings)
│   └── profile.py           # /profile ConversationHandler (guided setup for daily targets)
├── services/
│   ├── claude.py            # Claude API + conversation state + daily nudge generation
│   ├── nutrition.py         # Mifflin-St Jeor daily target calculations
│   └── database.py          # SQLite CRUD (meals, settings, profiles)
├── utils/
│   ├── i18n.py              # translations (EN/DE/RU) and language helpers
│   ├── helpers.py           # shared utilities (language resolution, etc.)
│   └── photos.py            # photo download → base64
├── tests/                   # 153 pytest tests, fully mocked
└── calbot.service           # systemd unit file
```

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file:
```
BOT_TOKEN=<from @BotFather>
ANTHROPIC_API_KEY=<from console.anthropic.com>
ALLOWED_USER_IDS=<comma-separated Telegram user IDs>
LOG_LEVEL=INFO
```

Run:
```bash
python main.py
```

Run tests:
```bash
pip install -r requirements-dev.txt
pytest
```

## Deployment

Copy `calbot.service` to `/etc/systemd/system/`, create `.env` at `/opt/calbot/.env`, then:

```bash
systemctl daemon-reload
systemctl enable --now calbot
journalctl -u calbot -f
```

See `CLAUDE.md` for full deployment and CI/CD setup instructions.
