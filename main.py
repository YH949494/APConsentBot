import os
import sqlite3
from datetime import datetime, timezone

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DB_PATH = os.getenv("CONSENT_DB_PATH", "consent.db")

# Callback data
CB_CONFIRM_18 = "confirm_18"
CB_EXIT = "exit"
CB_CONTINUE = "continue"
CB_LEAVE = "leave"

STEP1_TEXT = (
    "This is a private access hub.\n\n"
    "Before continuing, please confirm:\n"
    "• You are 18 or older\n"
    "• You understand this is invite-only\n"
    "• No illegal content is allowed"
)

STEP2_TEXT = (
    "Thank you.\n\n"
    "Access here is limited and not indexed.\n"
    "Please read carefully before proceeding."
)

STEP3_TEXT = (
    "Important note:\n\n"
    "This hub does NOT host adult content.\n\n"
    "It exists to:\n"
    "• Connect adults to private communities\n"
    "• Share member-only perks\n"
    "• Provide access to non-public groups\n\n"
    "If this is not what you’re looking for, you may leave now."
)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS consent_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            action TEXT NOT NULL,        -- confirm_18 / exit / continue / leave
            consent_flag INTEGER,        -- 1 for confirm_18, else NULL
            ts_utc TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def log_action(user, action: str, consent_flag: int | None = None):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    ts_utc = datetime.now(timezone.utc).isoformat()
    cur.execute(
        """
        INSERT INTO consent_log (user_id, username, first_name, last_name, action, consent_flag, ts_utc)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user.id,
            user.username,
            user.first_name,
            user.last_name,
            action,
            consent_flag,
            ts_utc,
        ),
    )
    conn.commit()
    conn.close()


def kb_step1():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ I confirm (18+)", callback_data=CB_CONFIRM_18)],
            [InlineKeyboardButton("❌ Exit", callback_data=CB_EXIT)],
        ]
    )


def kb_step3():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Continue", callback_data=CB_CONTINUE)],
            [InlineKeyboardButton("Leave", callback_data=CB_LEAVE)],
        ]
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Always show Step 1 on /start. No “retry loop” on Exit; user must manually /start again.
    await update.message.reply_text(STEP1_TEXT, reply_markup=kb_step1())


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    data = query.data

    if data == CB_EXIT:
        # Log exit, end. No retry loop.
        log_action(user, action="exit", consent_flag=None)
        await query.edit_message_text("You have exited. No access was granted.")
        return

    if data == CB_CONFIRM_18:
        # Step 2 + silent consent log
        log_action(user, action="confirm_18", consent_flag=1)
        await query.edit_message_text(STEP2_TEXT)
        # Immediately follow with Step 3 (reframing)
        await query.message.reply_text(STEP3_TEXT, reply_markup=kb_step3())
        return

    if data == CB_LEAVE:
        log_action(user, action="leave", consent_flag=None)
        await query.edit_message_text("You may leave now. No access was granted.")
        return

    if data == CB_CONTINUE:
        log_action(user, action="continue", consent_flag=None)

        # ✅ TODO: Replace this with your next safe step.
        # Examples:
        # - Send a private group invite link
        # - Show “Member Perks” menu
        # - Redirect to a neutral landing page
        #
        # IMPORTANT: Keep wording neutral. No porn/gambling words here either.
        await query.edit_message_text(
            "Access granted.\n\n"
            "Next steps:\n"
            "• You will receive member options shortly.\n"
            "• If you do not recognize this hub, you may leave at any time."
        )
        return

    # Fallback: unknown callback
    await query.edit_message_text("Session ended.")


def main():
    if not BOT_TOKEN:
        raise RuntimeError("Missing BOT_TOKEN env var")

    init_db()

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(on_callback))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
