#!/usr/bin/env python3
import argparse
import base64
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yt_dlp
from openai import OpenAI


def sanitize_filename(name: str) -> str:
    # Keep filenames portable across major OSes.
    cleaned = re.sub(r"[\\/:*?\"<>|]", "_", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:180] or "transcript"


def download_audio(youtube_url: str, output_dir: Path) -> tuple[Path, str]:
    output_template = str(output_dir / "%(title)s.%(ext)s")
    base_ydl_opts = {
        "outtmpl": output_template,
        "quiet": False,
        "noplaylist": True,
        "extractor_args": {
            # Server environments can miss formats with default web client.
            "youtube": {"player_client": ["android"]},
        },
    }

    cookies_b64 = os.getenv("YTDLP_COOKIES_B64", "").strip()
    cookie_file: Path | None = None
    if cookies_b64:
        try:
            cookie_data = base64.b64decode(cookies_b64, validate=True)
        except Exception as exc:
            raise ValueError(f"Invalid YTDLP_COOKIES_B64 value: {exc}") from exc

        cookie_file = output_dir / "yt_cookies.txt"
        cookie_file.write_bytes(cookie_data)
        base_ydl_opts["cookiefile"] = str(cookie_file)

    try:
        format_candidates = [
            "bestaudio/best",
            "bestaudio*/best",
            "best",
        ]
        last_exc: Exception | None = None

        for fmt in format_candidates:
            ydl_opts = dict(base_ydl_opts)
            ydl_opts["format"] = fmt
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(youtube_url, download=True)
                    downloaded = Path(ydl.prepare_filename(info))
                    title = info.get("title") or "transcript"

                    requested = info.get("requested_downloads") or []
                    if requested:
                        actual = requested[0].get("filepath")
                        if actual:
                            downloaded = Path(actual)

                    if not downloaded.exists():
                        matches = sorted(output_dir.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
                        if not matches:
                            raise FileNotFoundError("yt-dlp finished but no audio file was found.")
                        downloaded = matches[0]

                    return downloaded, title

            except yt_dlp.utils.DownloadError as exc:
                last_exc = exc
                if "Requested format is not available" in str(exc):
                    continue
                raise

        if last_exc:
            raise last_exc
        raise RuntimeError("yt-dlp failed to download with all fallback formats.")
    finally:
        if cookie_file and cookie_file.exists():
            cookie_file.unlink()


def transcribe_file(audio_path: Path, model: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY is not set.")

    client = OpenAI(api_key=api_key)
    with audio_path.open("rb") as audio_fp:
        result = client.audio.transcriptions.create(
            model=model,
            file=audio_fp,
        )

    return result.text


def audio_duration_seconds(audio_path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]
    output = subprocess.check_output(cmd, text=True).strip()
    return float(output)


def split_audio(audio_path: Path, output_dir: Path, chunk_seconds: int) -> list[Path]:
    pattern = output_dir / "chunk_%03d.mp3"
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(audio_path),
        "-vn",
        "-f",
        "segment",
        "-segment_time",
        str(chunk_seconds),
        "-c:a",
        "libmp3lame",
        "-b:a",
        "128k",
        str(pattern),
    ]
    subprocess.check_call(cmd)
    chunks = sorted(output_dir.glob("chunk_*.mp3"))
    if not chunks:
        raise RuntimeError("Audio splitting produced no chunks.")
    return chunks


def transcribe_youtube_url(
    url: str,
    model: str = "gpt-4o-mini-transcribe",
    out_dir: str | Path = ".",
    chunk_seconds: int = 600,
) -> Path:
    output_dir = Path(out_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="yt_audio_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        audio_path, title = download_audio(url, tmp_path)
        duration = audio_duration_seconds(audio_path)

        if duration <= chunk_seconds:
            transcript = transcribe_file(audio_path, model)
        else:
            chunk_dir = tmp_path / "chunks"
            chunk_dir.mkdir(parents=True, exist_ok=True)
            chunks = split_audio(audio_path, chunk_dir, chunk_seconds)
            total = len(chunks)
            parts: list[str] = []

            for i, chunk in enumerate(chunks, start=1):
                print(f"Transcribing chunk {i}/{total}: {chunk.name}")
                parts.append(transcribe_file(chunk, model))

            transcript = "\n\n".join(parts)

    transcript_filename = f"{sanitize_filename(title)}.txt"
    transcript_path = output_dir / transcript_filename
    transcript_path.write_text(transcript, encoding="utf-8")
    return transcript_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Download YouTube audio and transcribe it with OpenAI.")
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument(
        "--model",
        default="gpt-4o-mini-transcribe",
        help="Transcription model (default: gpt-4o-mini-transcribe)",
    )
    parser.add_argument(
        "--out-dir",
        default=".",
        help="Directory where transcript text file will be written (default: current directory)",
    )
    parser.add_argument(
        "--chunk-seconds",
        type=int,
        default=600,
        help="Chunk size for transcription in seconds (default: 600)",
    )
    args = parser.parse_args()

    try:
        transcript_path = transcribe_youtube_url(
            url=args.url,
            model=args.model,
            out_dir=args.out_dir,
            chunk_seconds=args.chunk_seconds,
        )
        print(f"Transcript saved: {transcript_path}")
        return 0

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
