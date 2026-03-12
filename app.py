#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import string
import subprocess
import sys
import tempfile
from pathlib import Path


def sanitize_filename(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9._ -]", "_", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:120] or "transcript"


def check_command(name: str) -> None:
    if shutil.which(name) is None:
        print(f"Error: '{name}' is not installed or not on PATH.", file=sys.stderr)
        sys.exit(1)


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def download_audio(url: str, out_dir: Path) -> tuple[Path, str]:
    out_template = str(out_dir / "%(title)s.%(ext)s")
    run([
        "yt-dlp",
        "-f", "bestaudio/best",
        "--no-playlist",
        "-o", out_template,
        url,
    ])

    files = sorted(
        [p for p in out_dir.iterdir() if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not files:
        raise RuntimeError("No downloaded audio/video file found.")

    source_file = files[0]
    return source_file, source_file.stem


def convert_to_wav(source_path: Path, wav_path: Path) -> Path:
    run([
        "ffmpeg",
        "-y",
        "-i", str(source_path),
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        str(wav_path),
    ])
    return wav_path


def whisperx_transcribe_and_diarize(
    audio_path: Path,
    output_dir: Path,
    model: str,
    language: str | None,
    hf_token: str,
) -> Path:
    cmd = [
        "whisperx",
        str(audio_path),
        "--model", model,
        "--diarize",
        "--hf_token", hf_token,
        "--output_dir", str(output_dir),
        "--output_format", "json",
        "--device", "cpu",
    ]
    if language:
        cmd.extend(["--language", language])

    run(cmd)

    json_path = output_dir / f"{audio_path.stem}.json"
    if not json_path.exists():
        raise RuntimeError("WhisperX finished but no JSON output was created.")
    return json_path


def normalize_speaker_name(raw: str, mapping: dict[str, str]) -> str:
    if raw not in mapping:
        idx = len(mapping)
        if idx < 26:
            letter = string.ascii_uppercase[idx]
        else:
            letter = f"A{idx}"
        mapping[raw] = f"SPEAKER {letter}"
    return mapping[raw]


def compact_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def format_speaker_blocks(json_path: Path) -> str:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    segments = data.get("segments", [])

    missing_speaker = sum(1 for seg in segments if "speaker" not in seg)
    print(f"Segments found: {len(segments)}")
    print(f"Segments missing speaker label: {missing_speaker}")

    speaker_map: dict[str, str] = {}
    blocks: list[tuple[str, str]] = []

    for seg in segments:
        speaker = seg.get("speaker")
        text = compact_text(seg.get("text", ""))

        if not speaker or not text:
            continue

        label = normalize_speaker_name(speaker, speaker_map)

        if blocks and blocks[-1][0] == label:
            blocks[-1] = (label, f"{blocks[-1][1]} {text}".strip())
        else:
            blocks.append((label, text))

    if not blocks:
        raise RuntimeError(
            "No speaker-labeled transcript segments were found in the JSON. "
            "Diarization likely did not attach speaker IDs to transcript segments."
        )

    parts = []
    for speaker, text in blocks:
        parts.append(f"{speaker}\n{text}")

    return "\n\n".join(parts).strip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download a YouTube video and create a diarized local transcript."
    )
    parser.add_argument("url", help="YouTube URL")
    parser.add_argument("--model", default="small", help="WhisperX model")
    parser.add_argument("--language", default=None, help="Optional language hint, e.g. en")
    parser.add_argument("--output", default=None, help="Optional output .txt file path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        print("Error: HF_TOKEN is not set.", file=sys.stderr)
        sys.exit(1)

    check_command("yt-dlp")
    check_command("ffmpeg")
    check_command("ffprobe")
    check_command("whisperx")

    debug_dir = Path.cwd() / "debug_output"
    debug_dir.mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="yt_diarize_") as tmp:
        tmp_dir = Path(tmp)

        print("Downloading audio from YouTube...")
        source_path, title = download_audio(args.url, tmp_dir)
        print(f"Downloaded: {source_path.name}")

        wav_path = tmp_dir / "audio.wav"
        print("Converting audio...")
        convert_to_wav(source_path, wav_path)

        print("Running WhisperX diarization...")
        json_path = whisperx_transcribe_and_diarize(
            audio_path=wav_path,
            output_dir=tmp_dir,
            model=args.model,
            language=args.language,
            hf_token=hf_token,
        )

        saved_json = debug_dir / f"{sanitize_filename(title)}.json"
        saved_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Saved raw JSON to: {saved_json}")

        print("Formatting transcript...")
        transcript = format_speaker_blocks(saved_json)

        if args.output:
            final_path = Path(args.output).expanduser().resolve()
        else:
            final_path = Path.cwd() / f"{sanitize_filename(title)}.txt"

        final_path.write_text(transcript, encoding="utf-8")
        print(f"\nDone. Transcript saved to:\n{final_path}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        sys.exit(130)
    except subprocess.CalledProcessError as exc:
        print(f"\nCommand failed: {' '.join(exc.cmd)}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        sys.exit(1)
