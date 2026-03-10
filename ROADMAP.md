# Calorie Tracker Telegram Bot — Project Roadmap

> Created: 2026-03-10  
> Status: 🟡 In Progress — Phase 1

---

## Phase 1 — Foundation
- [ ] **1. Register the bot with Telegram**
  - Message `@BotFather`, create a new bot, save `BOT_TOKEN` to `.env`
- [ ] **2. Set up development environment**
  - Python venv, `.env` file, install `python-telegram-bot`
- [ ] **3. Build a "hello world" bot**
  - Responds to `/start`, echoes messages, confirms token works

## Phase 2 — The Brain (Core Intelligence)
- [ ] **4. Integrate Claude API as reasoning engine**
  - Handles text + photo input
  - Returns structured JSON: `{food_items, calories_estimate, confidence, clarifying_question}`
- [ ] **5. Build the clarifying question loop**
  - Ask follow-ups when confidence is low
  - Per-user conversation state (in-memory dict)
- [ ] **6. Handle both input types**
  - Text: "I just ate a bowl of oatmeal"
  - Photo: download → base64 → Claude vision

## Phase 3 — Persistence (Logging)
- [ ] **7. Add SQLite database** (`aiosqlite`)
  - Schema: `user_id`, `timestamp`, `description`, `calories`, `input_type`
- [ ] **8. Add basic commands**
  - `/today` — today's total + breakdown
  - `/history` — last 7 days summary

## Phase 4 — Deployment
- [ ] **9. Deploy to ether.emind.at**
  - Start with polling mode
- [ ] **10. Run as systemd service**
  - Auto-restart on crash, survives reboots

## Phase 5 — Nice-to-Haves
- [ ] `/setgoal 2000` — daily calorie target
- [ ] Weekly summary report (scheduled message)
- [ ] Export to CSV
- [ ] Small web dashboard

---

## Build Order

```
BotFather token → hello world bot → Claude integration →
clarifying loop → photo support → SQLite logging →
/today command → deploy on server
```

---

## Current Step
👉 **Phase 1, Step 1** — Get `BOT_TOKEN` from `@BotFather` on Telegram
