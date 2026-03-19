"""Internationalisation helpers — English, German, Russian."""

_STRINGS: dict[str, dict[str, str]] = {
    # --- Keyboard buttons ---
    "btn_today": {
        "en": "📊 Today",
        "de": "📊 Heute",
        "ru": "📊 Сегодня",
    },
    "btn_history": {
        "en": "📅 History",
        "de": "📅 Verlauf",
        "ru": "📅 История",
    },

    # --- /start & /help ---
    "welcome": {
        "en": (
            "👋 Hi! I'm your personal nutrition tracker.\n\n"
            "Just send me:\n"
            "• 📸 A photo of your food\n"
            "• ✍️ A text description of what you ate\n\n"
            "I'll estimate the nutrients and log them for you.\n\n"
            "Commands:\n"
            "/today — see today's total\n"
            "/history — last 7 days\n"
            "/undo — remove the last logged meal\n"
            "/cancel — cancel a pending question\n"
            "/settings — choose what nutrition info to show\n"
            "/profile — set up your daily nutrition targets\n"
            "/help — show this message"
        ),
        "de": (
            "👋 Hallo! Ich bin dein persönlicher Ernährungstracker.\n\n"
            "Schick mir einfach:\n"
            "• 📸 Ein Foto deines Essens\n"
            "• ✍️ Eine Beschreibung, was du gegessen hast\n\n"
            "Ich schätze die Nährwerte und logge sie für dich.\n\n"
            "Befehle:\n"
            "/today — heutige Übersicht\n"
            "/history — letzte 7 Tage\n"
            "/undo — letzten Eintrag löschen\n"
            "/cancel — ausstehende Frage abbrechen\n"
            "/settings — Anzeigeoptionen wählen\n"
            "/profile — tägliche Nährwertziele festlegen\n"
            "/help — diese Nachricht anzeigen"
        ),
        "ru": (
            "👋 Привет! Я твой персональный трекер питания.\n\n"
            "Просто отправь мне:\n"
            "• 📸 Фото еды\n"
            "• ✍️ Текстовое описание того, что ты съел(а)\n\n"
            "Я оценю нутриенты и запишу их.\n\n"
            "Команды:\n"
            "/today — итоги за сегодня\n"
            "/history — последние 7 дней\n"
            "/undo — удалить последнюю запись\n"
            "/cancel — отменить текущий вопрос\n"
            "/settings — настроить отображение нутриентов\n"
            "/profile — установить дневные цели\n"
            "/help — показать это сообщение"
        ),
    },

    # --- food handler ---
    "msg_too_long": {
        "en": "Message too long — please keep it under {limit} characters.",
        "de": "Nachricht zu lang — bitte maximal {limit} Zeichen.",
        "ru": "Сообщение слишком длинное — не более {limit} символов.",
    },
    "estimating": {
        "en": "⏳ Estimating nutrients...",
        "de": "⏳ Nährwerte werden geschätzt…",
        "ru": "⏳ Оцениваю нутриенты…",
    },
    "error": {
        "en": "Something went wrong — please try again.",
        "de": "Etwas ist schiefgelaufen — bitte versuche es erneut.",
        "ru": "Что-то пошло не так — попробуй ещё раз.",
    },
    "logged": {
        "en": "✅ Logged! {items}{suffix}",
        "de": "✅ Eingetragen! {items}{suffix}",
        "ru": "✅ Записано! {items}{suffix}",
    },
    "analysing_photo": {
        "en": "📸 Analysing your photo...",
        "de": "📸 Foto wird analysiert…",
        "ru": "📸 Анализирую фото…",
    },
    "cancelled": {
        "en": "Cancelled. Send a new food description whenever you're ready.",
        "de": "Abgebrochen. Schick mir eine neue Beschreibung, wenn du bereit bist.",
        "ru": "Отменено. Отправь новое описание, когда будешь готов(а).",
    },
    "nothing_to_cancel": {
        "en": "Nothing to cancel.",
        "de": "Nichts zum Abbrechen.",
        "ru": "Нечего отменять.",
    },
    "undo_done": {
        "en": "↩️ Removed: {desc} — {cal} kcal",
        "de": "↩️ Entfernt: {desc} — {cal} kcal",
        "ru": "↩️ Удалено: {desc} — {cal} kcal",
    },
    "nothing_to_undo": {
        "en": "Nothing to undo — no meals logged yet.",
        "de": "Nichts zum Rückgängigmachen — noch keine Mahlzeiten eingetragen.",
        "ru": "Нечего отменять — записей пока нет.",
    },
    "nothing_today": {
        "en": "📊 Nothing logged today yet.",
        "de": "📊 Heute noch nichts eingetragen.",
        "ru": "📊 Сегодня пока ничего не записано.",
    },
    "today_header": {
        "en": "📊 *Today's log:*",
        "de": "📊 *Heutiges Protokoll:*",
        "ru": "📊 *Записи за сегодня:*",
    },
    "no_history": {
        "en": "📅 No meals logged in the last 7 days.",
        "de": "📅 Keine Mahlzeiten in den letzten 7 Tagen.",
        "ru": "📅 Нет записей за последние 7 дней.",
    },
    "history_header": {
        "en": "📅 *Last 7 days:*",
        "de": "📅 *Letzte 7 Tage:*",
        "ru": "📅 *Последние 7 дней:*",
    },
    "settings_header": {
        "en": "⚙️ *Display settings*\nChoose which nutrition info to show:",
        "de": "⚙️ *Anzeigeoptionen*\nWähle, welche Nährwerte angezeigt werden:",
        "ru": "⚙️ *Настройки отображения*\nВыбери, какие данные показывать:",
    },
    "total": {
        "en": "Total",
        "de": "Gesamt",
        "ru": "Итого",
    },

    # --- setting labels ---
    "label_calories": {
        "en": "Calories",
        "de": "Kalorien",
        "ru": "Калории",
    },
    "label_proteins": {
        "en": "Proteins",
        "de": "Proteine",
        "ru": "Белки",
    },
    "label_fats": {
        "en": "Fats",
        "de": "Fette",
        "ru": "Жиры",
    },
    "label_carbs": {
        "en": "Carbs",
        "de": "Kohlenhydrate",
        "ru": "Углеводы",
    },

    # --- profile flow ---
    "profile_weight": {
        "en": "What is your weight in kg?",
        "de": "Wie viel wiegst du (in kg)?",
        "ru": "Какой у тебя вес (в кг)?",
    },
    "profile_weight_error": {
        "en": "Please enter a valid weight between 30 and 300 kg.",
        "de": "Bitte gib ein gültiges Gewicht zwischen 30 und 300 kg ein.",
        "ru": "Введи корректный вес от 30 до 300 кг.",
    },
    "profile_height": {
        "en": "What is your height in cm?",
        "de": "Wie groß bist du (in cm)?",
        "ru": "Какой у тебя рост (в см)?",
    },
    "profile_height_error": {
        "en": "Please enter a valid height between 100 and 250 cm.",
        "de": "Bitte gib eine gültige Größe zwischen 100 und 250 cm ein.",
        "ru": "Введи корректный рост от 100 до 250 см.",
    },
    "profile_age": {
        "en": "How old are you?",
        "de": "Wie alt bist du?",
        "ru": "Сколько тебе лет?",
    },
    "profile_age_error": {
        "en": "Please enter a valid age between 10 and 120.",
        "de": "Bitte gib ein gültiges Alter zwischen 10 und 120 ein.",
        "ru": "Введи корректный возраст от 10 до 120.",
    },
    "profile_sex": {
        "en": "What is your sex?",
        "de": "Was ist dein Geschlecht?",
        "ru": "Какой у тебя пол?",
    },
    "profile_male": {
        "en": "Male",
        "de": "Männlich",
        "ru": "Мужской",
    },
    "profile_female": {
        "en": "Female",
        "de": "Weiblich",
        "ru": "Женский",
    },
    "profile_activity": {
        "en": "What is your activity level?",
        "de": "Wie aktiv bist du?",
        "ru": "Какой у тебя уровень активности?",
    },
    "profile_sedentary": {
        "en": "Sedentary",
        "de": "Sitzend",
        "ru": "Малоподвижный",
    },
    "profile_light": {
        "en": "Lightly active",
        "de": "Leicht aktiv",
        "ru": "Слегка активный",
    },
    "profile_moderate": {
        "en": "Moderately active",
        "de": "Mäßig aktiv",
        "ru": "Умеренно активный",
    },
    "profile_active": {
        "en": "Very active",
        "de": "Sehr aktiv",
        "ru": "Очень активный",
    },
    "profile_goal": {
        "en": "What is your goal?",
        "de": "Was ist dein Ziel?",
        "ru": "Какая у тебя цель?",
    },
    "profile_lose": {
        "en": "Lose weight",
        "de": "Abnehmen",
        "ru": "Похудеть",
    },
    "profile_maintain": {
        "en": "Maintain",
        "de": "Halten",
        "ru": "Поддерживать",
    },
    "profile_gain": {
        "en": "Gain weight",
        "de": "Zunehmen",
        "ru": "Набрать вес",
    },
    "profile_saved": {
        "en": "✅ Profile saved! Your daily targets:\n{cal} kcal | P: {p}g  F: {f}g  C: {c}g",
        "de": "✅ Profil gespeichert! Deine Tagesziele:\n{cal} kcal | P: {p}g  F: {f}g  K: {c}g",
        "ru": "✅ Профиль сохранён! Твои дневные цели:\n{cal} kcal | Б: {p}г  Ж: {f}г  У: {c}г",
    },
    "profile_cancelled": {
        "en": "Profile setup cancelled.",
        "de": "Profileinrichtung abgebrochen.",
        "ru": "Настройка профиля отменена.",
    },
}


def _normalise_lang(language_code: str | None) -> str:
    """Map a Telegram language_code to a supported language key."""
    if not language_code:
        return "en"
    code = language_code.lower().split("-")[0]
    if code in ("de",):
        return "de"
    if code in ("ru",):
        return "ru"
    return "en"


def t(key: str, lang: str | None = None, **kwargs) -> str:
    """Look up a translated string, with optional format kwargs."""
    lang = _normalise_lang(lang)
    entry = _STRINGS.get(key, {})
    text = entry.get(lang) or entry.get("en", f"[{key}]")
    if kwargs:
        text = text.format(**kwargs)
    return text
