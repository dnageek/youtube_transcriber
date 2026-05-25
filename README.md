# YouTube Transcriber (CLI + Slack on Render)

This project transcribes YouTube videos using OpenAI.

It supports:
- CLI usage: run directly from terminal
- Slack usage: `/yttranscript <youtube-url>` from phone/desktop
- Telegram usage: send YouTube URL to your bot from phone/desktop
- Render deployment for always-available webhook hosting

---

## 1) What This App Does

1. Accepts a YouTube URL
2. Downloads best audio via `yt-dlp`
3. Splits long audio into chunks with `ffmpeg`
4. Sends chunks to OpenAI transcription API
5. Writes transcript as `.txt`
6. In Slack mode, uploads the transcript file back to the channel

---

## 2) Repo Files

- `youtube_transcribe.py`: core transcription pipeline + CLI
- `slack_app.py`: Slack slash-command web server
- `telegram_bot.py`: Telegram long-polling bot for local use
- `requirements.txt`: Python dependencies
- `render.yaml`: Render service blueprint

---

## 3) Prerequisites

### Accounts
- OpenAI API account with a valid API key
- Slack workspace where you can install apps
- Render account

### Local tools
- Python 3.10+
- `ffmpeg` + `ffprobe` available on PATH

Install ffmpeg on Ubuntu/WSL:

```bash
sudo apt update
sudo apt install -y ffmpeg
```

Verify:

```bash
ffmpeg -version
ffprobe -version
```

---

## 4) Local Setup (CLI)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set OpenAI key:

```bash
export OPENAI_API_KEY="your_openai_api_key"
```

Run:

```bash
python youtube_transcribe.py "https://www.youtube.com/watch?v=..." --chunk-seconds 600
```

Output:
- Transcript `.txt` file in current folder (or `--out-dir` if provided)

---

## 5) Local Setup (Slack server)

Set env vars:

```bash
export OPENAI_API_KEY="your_openai_api_key"
export SLACK_BOT_TOKEN="xoxb-..."
export SLACK_SIGNING_SECRET="..."
export TRANSCRIBE_MODEL="gpt-4o-mini-transcribe"
export CHUNK_SECONDS="600"
export TRANSCRIPT_DIR="transcripts"
```

Run server:

```bash
python slack_app.py
```

Endpoints:
- `GET /health`
- `POST /slack/commands`

---

## 6) Local Setup (Telegram bot, no public IP needed)

Telegram mode uses long polling, so your computer only makes outbound HTTPS calls to Telegram.

### Create bot token

1. In Telegram, open `@BotFather`.
2. Run `/newbot` and follow prompts.
3. Copy bot token and set:

```bash
export TELEGRAM_BOT_TOKEN="123456:ABCDEF..."
```

### Required env vars

```bash
export OPENAI_API_KEY="your_openai_api_key"
export TELEGRAM_BOT_TOKEN="123456:ABCDEF..."
export TRANSCRIBE_MODEL="gpt-4o-mini-transcribe"
export CHUNK_SECONDS="600"
export TRANSCRIPT_DIR="transcripts"
```

Optional access control (comma-separated Telegram numeric user IDs):

```bash
export TELEGRAM_ALLOWED_USER_IDS="123456789,987654321"
```

Run bot:

```bash
python telegram_bot.py
```

Usage in Telegram:
- Send `/start`
- Send a YouTube URL
- Bot replies with preview + transcript `.txt` file

---

## 7) Slack App Setup (Required)

1. Go to `https://api.slack.com/apps` and create a new app.
2. Open `OAuth & Permissions`.
3. Add Bot Token Scope:
- `files:write`
4. Install app to workspace.
5. Copy values:
- `Bot User OAuth Token` -> `SLACK_BOT_TOKEN`
- `Signing Secret` (Basic Information) -> `SLACK_SIGNING_SECRET`

### Add Slash Command

1. Open `Slash Commands` -> `Create New Command`
2. Command: `/yttranscript`
3. Request URL:
- local dev: tunnel URL + `/slack/commands`
- Render: `https://<your-service>.onrender.com/slack/commands`
4. Save and reinstall app if prompted.

Command usage in Slack:

```text
/yttranscript https://www.youtube.com/watch?v=...
```

---

## 8) Deploy to Render

You have two deployment choices.

### Option A: Native Python (quick start)

1. Push repo to GitHub/GitLab.
2. In Render: `New +` -> `Web Service`.
3. Connect repo.
4. Render should read `render.yaml`.
5. Deploy.

Set env vars in Render service -> `Environment`:
- `OPENAI_API_KEY`
- `SLACK_BOT_TOKEN`
- `SLACK_SIGNING_SECRET`
- `YTDLP_COOKIES_B64` (recommended for YouTube bot-check issues)
- `TRANSCRIBE_MODEL` (optional, default `gpt-4o-mini-transcribe`)
- `CHUNK_SECONDS` (optional, default `600`)
- `TRANSCRIPT_DIR` (optional, default `transcripts`)

If deploy/runtime logs show missing `ffmpeg` or `ffprobe`, use Option B.

### Option B: Docker on Render (recommended if ffmpeg missing)

Use the repo's `Dockerfile` (already included).

Then create a new Render Web Service from this repo; Render auto-detects Dockerfile.
Set the same env vars listed above.

### YouTube bot-check fix (cookies)

If you see this error in logs:
- `Sign in to confirm you're not a bot`

Add authenticated YouTube cookies for `yt-dlp`:

1. Export YouTube cookies from your browser in Netscape cookie format (file like `youtube_cookies.txt`).
2. Convert file to base64 on your machine:

```bash
base64 -w 0 youtube_cookies.txt
```

3. In Render -> Environment, set:
- `YTDLP_COOKIES_B64` = `<base64 output>`

4. Redeploy service.

The app decodes this env var at runtime and passes it to `yt-dlp` as `cookiefile`.

Official `yt-dlp` docs for cookies:
- FAQ: https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp
- YouTube extractor notes: https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies

Important notes:
- Export cookies from a browser profile currently signed into YouTube.
- Keep cookie file format as Netscape cookie format.
- Treat cookies like credentials; do not commit or share them.

---

## 9) Render Free Tier Notes

- Free services can sleep after inactivity.
- First request after sleep may be slower (cold start).
- This is expected behavior.

---

## 10) End-to-End Test Checklist

1. `https://<render-url>/health` returns `ok`
2. Slash command Request URL is correct
3. Bot app installed in workspace
4. Bot has `files:write`
5. In Slack channel, run:
   `/yttranscript <youtube-url>`
6. You should see:
- immediate queue response
- final transcript file upload + short preview

---

## 11) Troubleshooting

### `invalid signature`
- `SLACK_SIGNING_SECRET` is wrong or outdated.

### Slack command times out
- Service is sleeping/cold-started.
- Retry once after wake-up.

### `ffprobe` / `ffmpeg` not found
- Host does not have ffmpeg packages.
- Use Docker deploy with ffmpeg installed.

### Slack file upload error (`not_in_channel`, `missing_scope`)
- Invite bot to target channel.
- Ensure bot has `files:write` scope.
- Reinstall app after scope changes.

### OpenAI errors
- Confirm `OPENAI_API_KEY` is valid.
- Check API billing/usage limits.

### Transcript seems partial
- Reduce chunk size:

```bash
export CHUNK_SECONDS=300
```

or CLI:

```bash
python youtube_transcribe.py "<url>" --chunk-seconds 300
```

---

## 12) Security Notes

- Never commit API keys or tokens.
- Set secrets only in env vars (Render Environment settings).
- Slack signature verification is enabled in `slack_app.py`.

---

## 13) Useful Commands

Local syntax check:

```bash
python -m py_compile youtube_transcribe.py slack_app.py
```

Telegram bot syntax check:

```bash
python -m py_compile telegram_bot.py
```

Run server locally:

```bash
python slack_app.py
```

Run Telegram bot locally:

```bash
python telegram_bot.py
```

Run CLI locally:

```bash
python youtube_transcribe.py "https://www.youtube.com/watch?v=..."
```
