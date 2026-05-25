#!/usr/bin/env python3
import os
from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from youtube_transcribe import transcribe_youtube_url

MODEL_NAME = os.getenv("TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe")
CHUNK_SECONDS = int(os.getenv("CHUNK_SECONDS", "600"))
TRANSCRIPT_DIR = Path(os.getenv("TRANSCRIPT_DIR", "transcripts"))
ALLOWED_USER_IDS = {
    int(v.strip()) for v in os.getenv("TELEGRAM_ALLOWED_USER_IDS", "").split(",") if v.strip().isdigit()
}


def is_allowed(update: Update) -> bool:
    if not ALLOWED_USER_IDS:
        return True
    if not update.effective_user:
        return False
    return update.effective_user.id in ALLOWED_USER_IDS


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        await update.message.reply_text("Access denied for this bot.")
        return

    await update.message.reply_text(
        "Send a YouTube URL and I will transcribe it.\\n"
        "Example: https://www.youtube.com/watch?v=..."
    )


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        await update.message.reply_text("Access denied for this bot.")
        return

    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    if not ("youtube.com/watch" in text or "youtu.be/" in text):
        await update.message.reply_text("Please send a valid YouTube URL.")
        return

    await update.message.reply_text("Queued. Downloading and transcribing now. This may take a few minutes.")

    try:
        transcript_path = transcribe_youtube_url(
            url=text,
            model=MODEL_NAME,
            out_dir=TRANSCRIPT_DIR,
            chunk_seconds=CHUNK_SECONDS,
        )

        transcript_text = transcript_path.read_text(encoding="utf-8")
        preview = transcript_text[:1200] + ("..." if len(transcript_text) > 1200 else "")
        await update.message.reply_text(f"Preview:\\n{preview}")

        with transcript_path.open("rb") as fp:
            await update.message.reply_document(
                document=fp,
                filename=transcript_path.name,
                caption="Transcript complete.",
            )
    except Exception as exc:
        await update.message.reply_text(f"Transcription failed: {exc}")


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set.")

    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
