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
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse


TRANSCRIPTS_ROOT = Path("/Users/tristan/Documents/Transcripts")


def sanitize_filename(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9._ -]", "_", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:120] or "transcript"


def slugify(value: str, max_words: int = 8, max_len: int = 60) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9\s-]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    words = value.split()[:max_words]
    slug = "-".join(words)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:max_len].strip("-") or "untitled"


def check_command(name: str) -> None:
    if shutil.which(name) is None:
        print(f"Error: '{name}' is not installed or not on PATH.", file=sys.stderr)
        sys.exit(1)


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def run_capture(cmd: list[str]) -> str:
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def extract_video_id(url: str) -> str:
    parsed = urlparse(url)

    if parsed.netloc in {"youtu.be", "www.youtu.be"}:
        return parsed.path.strip("/") or "video"

    qs = parse_qs(parsed.query)
    if "v" in qs and qs["v"]:
        return qs["v"][0]

    tail = parsed.path.strip("/").split("/")[-1]
    return tail or "video"


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


def run_whisper_plain(audio_path: Path, output_dir: Path, model: str, language: str | None) -> Path:
    cmd = [
        "whisperx",
        str(audio_path),
        "--model", model,
        "--output_dir", str(output_dir),
        "--output_format", "txt",
        "--device", "cpu",
    ]
    if language:
        cmd.extend(["--language", language])

    run(cmd)

    txt_path = output_dir / f"{audio_path.stem}.txt"
    if not txt_path.exists():
        raise RuntimeError("Plain Whisper transcript file was not created.")
    return txt_path


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
            label = string.ascii_uppercase[idx]
        else:
            label = f"A{idx}"
        mapping[raw] = f"SPEAKER {label}"
    return mapping[raw]


def compact_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def format_diarized_transcript(json_path: Path) -> str:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    segments = data.get("segments", [])

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
        raise RuntimeError("No speaker-labeled transcript segments were found.")

    return "\n\n".join(f"{speaker}\n{text}" for speaker, text in blocks).strip() + "\n"


def generate_headline_slug(video_title: str, transcript_text: str, video_id: str) -> str:
    # Deterministic, local-only heuristic.
    # Prefer transcript content if available, otherwise fall back to title.
    text = transcript_text[:2500].strip()
    if not text:
        return slugify(video_title) or video_id

    candidates = re.findall(r"[A-Za-z][A-Za-z'-]{2,}", text.lower())
    stopwords = {
        "the", "and", "that", "with", "this", "from", "have", "they", "their", "about",
        "would", "there", "which", "what", "when", "where", "into", "because", "while",
        "were", "been", "them", "then", "than", "your", "just", "more", "also", "very",
        "will", "here", "like", "some", "much", "many", "over", "only", "really", "thank",
        "thanks", "good", "great", "well", "today", "tonight", "journalism", "news",
    }

    freq: dict[str, int] = {}
    for word in candidates:
        if word in stopwords or len(word) < 4:
            continue
        freq[word] = freq.get(word, 0) + 1

    keywords = [w for w, _ in sorted(freq.items(), key=lambda x: (-x[1], x[0]))[:6]]
    if keywords:
        return slugify(" ".join(keywords), max_words=6)

    return slugify(video_title) or video_id


def write_metadata(
    path: Path,
    *,
    url: str,
    video_id: str,
    video_title: str,
    folder_name: str,
    whisper_model: str,
    language: str | None,
) -> None:
    metadata = {
        "url": url,
        "video_id": video_id,
        "video_title": video_title,
        "folder_name": folder_name,
        "created_on": str(date.today()),
        "whisper_model": whisper_model,
        "language": language,
    }
    path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download a video, transcribe it locally, and save organized transcript outputs.")
    parser.add_argument("url", help="Video URL")
    parser.add_argument("--model", default="small", help="WhisperX model")
    parser.add_argument("--language", default=None, help="Optional language hint, e.g. en")
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

    TRANSCRIPTS_ROOT.mkdir(parents=True, exist_ok=True)

    video_id = extract_video_id(args.url)
    temp_folder = TRANSCRIPTS_ROOT / f"tmp_{video_id}"
    temp_folder.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="yt_diarize_") as tmp:
        tmp_dir = Path(tmp)

        print("Downloading audio...")
        source_path, video_title = download_audio(args.url, tmp_dir)
        original_ext = source_path.suffix or ".audio"
        saved_audio_path = temp_folder / f"source_audio{original_ext}"
        shutil.copy2(source_path, saved_audio_path)

        print("Converting audio...")
        wav_path = tmp_dir / "audio.wav"
        convert_to_wav(source_path, wav_path)

        print("Generating plain transcript...")
        whisper_txt_tmp = run_whisper_plain(
            audio_path=wav_path,
            output_dir=tmp_dir,
            model=args.model,
            language=args.language,
        )
        whisper_transcript = whisper_txt_tmp.read_text(encoding="utf-8")
        (temp_folder / "whisper_transcript.txt").write_text(whisper_transcript, encoding="utf-8")

        print("Generating diarized transcript...")
        diarized_json_tmp = whisperx_transcribe_and_diarize(
            audio_path=wav_path,
            output_dir=tmp_dir,
            model=args.model,
            language=args.language,
            hf_token=hf_token,
        )
        diarized_transcript = format_diarized_transcript(diarized_json_tmp)
        (temp_folder / "diarized_transcript.txt").write_text(diarized_transcript, encoding="utf-8")
        (temp_folder / "whisperx_diarized_raw.json").write_text(
            diarized_json_tmp.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        headline_slug = generate_headline_slug(video_title, diarized_transcript or whisper_transcript, video_id)
        final_folder_name = f"{date.today()}_{headline_slug}_{video_id}"
        final_folder = TRANSCRIPTS_ROOT / final_folder_name

        counter = 2
        while final_folder.exists():
            final_folder = TRANSCRIPTS_ROOT / f"{final_folder_name}_{counter}"
            counter += 1

        write_metadata(
            temp_folder / "metadata.json",
            url=args.url,
            video_id=video_id,
            video_title=video_title,
            folder_name=final_folder.name,
            whisper_model=args.model,
            language=args.language,
        )

        temp_folder.rename(final_folder)

        print("\nDone.")
        print(f"Saved folder:\n{final_folder}")
        print(f"Original audio:\n{final_folder / f'source_audio{original_ext}'}")
        print(f"Whisper transcript:\n{final_folder / 'whisper_transcript.txt'}")
        print(f"Diarized transcript:\n{final_folder / 'diarized_transcript.txt'}")


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
