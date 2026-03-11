# Calorie Tracker Telegram Bot — Project Roadmap

> Created: 2026-03-10
> Status: ✅ Phases 1–4 complete — running in production

---

## Phase 1 — Foundation ✅
- [x] **1. Register the bot with Telegram**
  - Message `@BotFather`, create a new bot, save `BOT_TOKEN` to `.env`
- [x] **2. Set up development environment**
  - Python venv, `.env` file, install `python-telegram-bot`
- [x] **3. Build a "hello world" bot**
  - Responds to `/start`, echoes messages, confirms token works

## Phase 2 — The Brain (Core Intelligence) ✅
- [x] **4. Integrate Claude API as reasoning engine**
  - Handles text + photo input
  - Returns structured JSON: `{food_items, calories_estimate, confidence, clarifying_question}`
- [x] **5. Build the clarifying question loop**
  - Ask follow-ups when confidence is low
  - Per-user conversation state (in-memory dict)
  - `/cancel` command to abort a stuck loop
- [x] **6. Handle both input types**
  - Text: "I just ate a bowl of oatmeal"
  - Photo: download → base64 → Claude vision

## Phase 3 — Persistence (Logging) ✅
- [x] **7. Add SQLite database** (`aiosqlite`)
  - Schema: `user_id`, `timestamp`, `description`, `calories`, `input_type`
- [x] **8. Add basic commands**
  - `/today` — today's total + breakdown
  - `/history` — last 7 days summary
  - Persistent keyboard buttons for Today / History

## Phase 4 — Deployment ✅
- [x] **9. Deploy to ether.emind.at**
  - Polling mode, no webhook needed
- [x] **10. Run as systemd service**
  - Auto-restart on crash, survives reboots
- [x] **11. CI/CD via GitHub Actions**
  - Runs pytest on every push; deploys only if tests pass

## Phase 5 — Nice-to-Haves
- [ ] `/setgoal 2000` — daily calorie target
- [ ] Weekly summary report (scheduled message)
- [ ] Export to CSV
- [ ] Small web dashboard

---

## Current Step
👉 **Phase 5** — nice-to-haves, pick any
