#!/usr/bin/env python3
import hashlib
import hmac
import json
import os
import threading
import time
from pathlib import Path
from urllib.request import Request, urlopen

from flask import Flask, Response, request
from slack_sdk import WebClient

from youtube_transcribe import transcribe_youtube_url

app = Flask(__name__)

SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
TRANSCRIPT_DIR = Path(os.getenv("TRANSCRIPT_DIR", "transcripts"))
MODEL_NAME = os.getenv("TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe")
CHUNK_SECONDS = int(os.getenv("CHUNK_SECONDS", "600"))


def verify_slack_request() -> bool:
    if not SLACK_SIGNING_SECRET:
        return False

    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    if not timestamp or not signature:
        return False

    try:
        ts = int(timestamp)
    except ValueError:
        return False

    if abs(time.time() - ts) > 60 * 5:
        return False

    body = request.get_data(as_text=True)
    base_string = f"v0:{timestamp}:{body}".encode("utf-8")
    expected = "v0=" + hmac.new(SLACK_SIGNING_SECRET.encode("utf-8"), base_string, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def post_response(response_url: str, text: str) -> None:
    payload = {"response_type": "ephemeral", "text": text}
    data = json.dumps(payload).encode("utf-8")
    req = Request(response_url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(req, timeout=30):
        pass


def process_job(url: str, response_url: str, channel_id: str, user_id: str) -> None:
    try:
        post_response(response_url, f"Processing started for <{url}>. This can take a few minutes.")
        transcript_path = transcribe_youtube_url(
            url=url,
            model=MODEL_NAME,
            out_dir=TRANSCRIPT_DIR,
            chunk_seconds=CHUNK_SECONDS,
        )

        text = transcript_path.read_text(encoding="utf-8")
        preview = text[:1200] + ("..." if len(text) > 1200 else "")

        client = WebClient(token=SLACK_BOT_TOKEN)
        client.files_upload_v2(
            channel=channel_id,
            file=str(transcript_path),
            title=transcript_path.name,
            initial_comment=f"Transcript ready for <@{user_id}>\nPreview:\n{preview}",
        )
        post_response(response_url, "Transcript complete and uploaded in channel.")

    except Exception as exc:
        post_response(response_url, f"Transcription failed: {exc}")


@app.get("/health")
def health() -> Response:
    return Response("ok", status=200)


@app.post("/slack/commands")
def slack_commands() -> Response:
    if not verify_slack_request():
        return Response("invalid signature", status=401)

    text = (request.form.get("text") or "").strip()
    response_url = request.form.get("response_url", "")
    channel_id = request.form.get("channel_id", "")
    user_id = request.form.get("user_id", "")

    if not text.startswith("http"):
        return Response("Usage: /yttranscript <youtube-url>", status=200)

    worker = threading.Thread(target=process_job, args=(text, response_url, channel_id, user_id), daemon=True)
    worker.start()
    return Response("Queued. I will post updates shortly.", status=200)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
