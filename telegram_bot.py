#!/usr/bin/env python3
import os
from pathlib import Path

import dropbox
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from youtube_transcribe import transcribe_youtube_url_with_stats

MODEL_NAME = os.getenv("TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe")
CHUNK_SECONDS = int(os.getenv("CHUNK_SECONDS", "600"))
TRANSCRIPT_DIR = Path(os.getenv("TRANSCRIPT_DIR", "transcripts"))
DROPBOX_ACCESS_TOKEN = os.getenv("DROPBOX_ACCESS_TOKEN", "").strip()
DROPBOX_FOLDER = os.getenv("DROPBOX_FOLDER", "/youtube_transcripts").strip() or "/youtube_transcripts"
TRANSCRIBE_COST_PER_MINUTE_USD = os.getenv("TRANSCRIBE_COST_PER_MINUTE_USD", "").strip()
ALLOWED_USER_IDS = {
    int(v.strip()) for v in os.getenv("TELEGRAM_ALLOWED_USER_IDS", "").split(",") if v.strip().isdigit()
}


def is_allowed(update: Update) -> bool:
    if not ALLOWED_USER_IDS:
        return True
    if not update.effective_user:
        return False
    return update.effective_user.id in ALLOWED_USER_IDS


def upload_to_dropbox(local_path: Path) -> str:
    if not DROPBOX_ACCESS_TOKEN:
        return ""

    target = f"{DROPBOX_FOLDER.rstrip('/')}/{local_path.name}"
    client = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)
    with local_path.open("rb") as fp:
        client.files_upload(fp.read(), target, mode=dropbox.files.WriteMode.overwrite)
    return target


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
        cost_per_minute = None
        if TRANSCRIBE_COST_PER_MINUTE_USD:
            cost_per_minute = float(TRANSCRIBE_COST_PER_MINUTE_USD)

        result = transcribe_youtube_url_with_stats(
            url=text,
            model=MODEL_NAME,
            out_dir=TRANSCRIPT_DIR,
            chunk_seconds=CHUNK_SECONDS,
            cost_per_minute_usd=cost_per_minute,
        )
        transcript_path = result.transcript_path

        minutes = result.audio_seconds / 60.0
        usage_line = f"Usage: {minutes:.2f} audio minutes processed."
        if result.estimated_cost_usd is not None:
            usage_line += f" Estimated cost: ${result.estimated_cost_usd:.4f}."
        dropbox_path = upload_to_dropbox(transcript_path)
        if dropbox_path:
            await update.message.reply_text(
                f"Saved to Dropbox: {dropbox_path}\n{usage_line}"
            )
        else:
            await update.message.reply_text(
                f"Saved locally: {transcript_path}\n{usage_line}"
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
