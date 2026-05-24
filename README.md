# YouTube Transcriber (CLI + Slack)

Transcribes YouTube videos with OpenAI. Supports direct CLI use and Slack slash-command usage for phone access.

## Requirements

- Python 3.10+
- `ffmpeg` and `ffprobe` on PATH
- `OPENAI_API_KEY`

## CLI setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run:

```bash
python youtube_transcribe.py "https://www.youtube.com/watch?v=..." --chunk-seconds 600
```

## Slack mode

Run locally:

```bash
export OPENAI_API_KEY=...
export SLACK_BOT_TOKEN=...
export SLACK_SIGNING_SECRET=...
python slack_app.py
```

Endpoints:

- `POST /slack/commands`
- `GET /health`

Slash command format:

- `/yttranscript <youtube-url>`

## Render deploy

This repo includes `render.yaml` for a free web service.

Render env vars required:

- `OPENAI_API_KEY`
- `SLACK_BOT_TOKEN`
- `SLACK_SIGNING_SECRET`

## Slack app config

- Create a slash command `/yttranscript`
- Set Request URL to `https://<your-render-url>/slack/commands`
- Add bot scope `files:write` (for transcript upload)
- Install app to workspace

## Notes

- Long videos are split into chunks before transcription.
- API usage costs come from OpenAI; hosting costs come from Render.
