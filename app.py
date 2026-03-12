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
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

TRANSCRIPTS_ROOT = Path("/Users/tristan/Documents/Transcripts")
DEFAULT_BROWSER = "chrome"
PAGE_FETCH_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


@dataclass
class SourceContext:
    source_kind: str
    original_input: str
    source_label: str
    folder_id: str
    original_url: str | None = None
    local_file: str | None = None
    download_url: str | None = None
    referer: str | None = None


class UserFacingError(RuntimeError):
    pass


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


def compact_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def check_command(name: str) -> None:
    if shutil.which(name) is None:
        raise UserFacingError(f"'{name}' is not installed or not on PATH.")


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def is_youtube_url(url: str) -> bool:
    netloc = urlparse(url).netloc.lower()
    return any(host in netloc for host in ("youtube.com", "youtu.be", "www.youtube.com", "m.youtube.com"))


def is_probable_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def is_local_file_input(value: str) -> bool:
    return Path(value).expanduser().exists()


def extract_video_id(url: str) -> str:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)

    if parsed.netloc in {"youtu.be", "www.youtu.be"}:
        return parsed.path.strip("/") or "video"

    if "v" in qs and qs["v"]:
        return qs["v"][0]

    tail = parsed.path.strip("/").split("/")[-1]
    return tail or "video"


def load_browser_cookies(browser: str):
    import browser_cookie3

    browser = browser.lower()
    if browser == "chrome":
        return browser_cookie3.chrome()
    if browser == "brave":
        return browser_cookie3.brave()
    if browser == "firefox":
        return browser_cookie3.firefox()
    if browser == "safari":
        return browser_cookie3.safari()
    raise UserFacingError(f"Unsupported browser for cookie loading: {browser}")


def fetch_page_html(url: str, browser: str) -> str:
    import requests

    try:
        cookies = load_browser_cookies(browser)
        response = requests.get(
            url,
            cookies=cookies,
            headers={"User-Agent": PAGE_FETCH_USER_AGENT},
            timeout=60,
        )
        response.raise_for_status()
        return response.text
    except Exception as exc:  # noqa: BLE001
        raise UserFacingError(f"Could not fetch page HTML for {url}: {exc}") from exc


def extract_vimeo_embed_urls(page_url: str, html: str) -> list[str]:
    patterns = [
        r"https?://player\.vimeo\.com/video/\d+(?:\?[^\"'\s<>]+)?",
        r"//player\.vimeo\.com/video/\d+(?:\?[^\"'\s<>]+)?",
        r"https?:\\\\/\\\\/player\.vimeo\.com\\\\/video\\\\/\d+(?:\?[^\"'\s<>]+)?",
    ]

    found: list[str] = []
    for pattern in patterns:
        found.extend(re.findall(pattern, html))

    cleaned: list[str] = []
    for item in found:
        item = item.replace("\\/", "/")
        if item.startswith("//"):
            item = "https:" + item
        item = urljoin(page_url, item)
        if item not in cleaned:
            cleaned.append(item)
    return cleaned


def download_audio_from_url(
    source_url: str,
    *,
    referer: str | None,
    browser: str,
    out_dir: Path,
) -> tuple[Path, str]:
    out_template = str(out_dir / "%(title)s.%(ext)s")
    cmd = [
        "yt-dlp",
        "--cookies-from-browser", browser,
        "-f", "bestaudio/best",
        "--no-playlist",
        "-o", out_template,
    ]
    if referer:
        cmd.extend(["--referer", referer])
    cmd.append(source_url)

    try:
        run(cmd)
    except subprocess.CalledProcessError as exc:
        raise UserFacingError(f"Could not download audio from {source_url}") from exc

    files = sorted(
        [p for p in out_dir.iterdir() if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not files:
        raise UserFacingError(f"Download appeared to succeed, but no media file was found for {source_url}")

    source_file = files[0]
    return source_file, source_file.stem


def convert_to_wav(source_path: Path, wav_path: Path) -> Path:
    try:
        run([
            "ffmpeg",
            "-y",
            "-i", str(source_path),
            "-vn",
            "-ac", "1",
            "-ar", "16000",
            str(wav_path),
        ])
    except subprocess.CalledProcessError as exc:
        raise UserFacingError(f"ffmpeg could not convert {source_path.name} to wav") from exc
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

    try:
        run(cmd)
    except subprocess.CalledProcessError as exc:
        raise UserFacingError("Plain transcript generation failed") from exc

    txt_path = output_dir / f"{audio_path.stem}.txt"
    if not txt_path.exists():
        raise UserFacingError("Plain transcript file was not created")
    return txt_path


def run_whisper_diarized(audio_path: Path, output_dir: Path, model: str, language: str | None, hf_token: str) -> Path:
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

    try:
        run(cmd)
    except subprocess.CalledProcessError as exc:
        raise UserFacingError("Diarized transcript generation failed") from exc

    json_path = output_dir / f"{audio_path.stem}.json"
    if not json_path.exists():
        raise UserFacingError("WhisperX finished but no diarized JSON output was created")
    return json_path


def normalize_speaker_name(raw: str, mapping: dict[str, str]) -> str:
    if raw not in mapping:
        idx = len(mapping)
        label = string.ascii_uppercase[idx] if idx < 26 else f"A{idx}"
        mapping[raw] = f"SPEAKER {label}"
    return mapping[raw]


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
        raise UserFacingError("No speaker-labeled transcript segments were found in the diarized output")

    return "\n\n".join(f"{speaker}\n{text}" for speaker, text in blocks).strip() + "\n"


def generate_headline_slug(label: str, transcript_text: str, fallback_id: str) -> str:
    text = transcript_text[:2500].strip()
    if not text:
        return slugify(label) or fallback_id

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
    return slugify(label) or fallback_id


def ensure_unique_temp_dir(base_name: str) -> Path:
    temp_dir = TRANSCRIPTS_ROOT / f"tmp_{base_name}"
    counter = 2
    while temp_dir.exists():
        temp_dir = TRANSCRIPTS_ROOT / f"tmp_{base_name}_{counter}"
        counter += 1
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def ensure_unique_final_dir(base_name: str) -> Path:
    final_dir = TRANSCRIPTS_ROOT / base_name
    counter = 2
    while final_dir.exists():
        final_dir = TRANSCRIPTS_ROOT / f"{base_name}_{counter}"
        counter += 1
    return final_dir


def write_metadata(path: Path, context: SourceContext, whisper_model: str, language: str | None, browser: str) -> None:
    metadata = {
        "source_kind": context.source_kind,
        "original_input": context.original_input,
        "original_url": context.original_url,
        "local_file": context.local_file,
        "download_url": context.download_url,
        "referer": context.referer,
        "folder_id": context.folder_id,
        "video_title": context.source_label,
        "folder_name": path.parent.name,
        "created_on": str(date.today()),
        "whisper_model": whisper_model,
        "language": language,
        "browser_cookies": browser,
    }
    path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def process_source_file(source_file: Path, context: SourceContext, browser: str, model: str, language: str | None, hf_token: str) -> Path:
    temp_folder = ensure_unique_temp_dir(context.folder_id)

    try:
        source_ext = source_file.suffix or ".audio"
        saved_audio_path = temp_folder / f"source_audio{source_ext}"
        shutil.copy2(source_file, saved_audio_path)

        with tempfile.TemporaryDirectory(prefix="yt_diarize_") as tmp:
            tmp_dir = Path(tmp)
            wav_path = tmp_dir / "audio.wav"

            print("Converting audio...")
            convert_to_wav(saved_audio_path, wav_path)

            print("Generating plain transcript...")
            whisper_txt = run_whisper_plain(wav_path, tmp_dir, model, language)
            whisper_text = whisper_txt.read_text(encoding="utf-8")
            (temp_folder / "whisper_transcript.txt").write_text(whisper_text, encoding="utf-8")

            print("Generating diarized transcript...")
            diarized_json = run_whisper_diarized(wav_path, tmp_dir, model, language, hf_token)
            diarized_text = format_diarized_transcript(diarized_json)
            (temp_folder / "diarized_transcript.txt").write_text(diarized_text, encoding="utf-8")
            (temp_folder / "whisperx_diarized_raw.json").write_text(
                diarized_json.read_text(encoding="utf-8"),
                encoding="utf-8",
            )

        headline_slug = generate_headline_slug(context.source_label, diarized_text or whisper_text, context.folder_id)
        final_name = f"{date.today()}_{headline_slug}_{context.folder_id}"
        final_folder = ensure_unique_final_dir(final_name)

        write_metadata(temp_folder / "metadata.json", context, model, language, browser)
        temp_folder.rename(final_folder)

        print("\nDone.")
        print(f"Saved folder:\n{final_folder}")
        return final_folder
    except Exception:
        if temp_folder.exists():
            shutil.rmtree(temp_folder, ignore_errors=True)
        raise


def process_local_file(local_input: str, browser: str, model: str, language: str | None, hf_token: str) -> Path:
    source_path = Path(local_input).expanduser().resolve()
    if not source_path.exists():
        raise UserFacingError(f"Local file not found: {source_path}")

    context = SourceContext(
        source_kind="local_file",
        original_input=local_input,
        source_label=source_path.stem,
        folder_id=slugify(source_path.stem, max_words=4) or "local-media",
        local_file=str(source_path),
    )
    return process_source_file(source_path, context, browser, model, language, hf_token)


def process_youtube_url(url: str, browser: str, model: str, language: str | None, hf_token: str) -> Path:
    with tempfile.TemporaryDirectory(prefix="source_download_") as tmp:
        tmp_dir = Path(tmp)
        print(f"Downloading audio from: {url}")
        source_path, title = download_audio_from_url(url, referer=None, browser=browser, out_dir=tmp_dir)
        context = SourceContext(
            source_kind="youtube_direct",
            original_input=url,
            original_url=url,
            download_url=url,
            source_label=title,
            folder_id=extract_video_id(url),
        )
        return process_source_file(source_path, context, browser, model, language, hf_token)


def process_embedded_page(page_url: str, browser: str, model: str, language: str | None, hf_token: str) -> list[Path]:
    print("Fetching page and scanning for embedded Vimeo players...")
    html = fetch_page_html(page_url, browser)
    embed_urls = extract_vimeo_embed_urls(page_url, html)
    if not embed_urls:
        raise UserFacingError("No embedded Vimeo player URLs were found on the page")

    print(f"Found {len(embed_urls)} Vimeo embed(s).")
    results: list[Path] = []

    for idx, embed_url in enumerate(embed_urls, start=1):
        print(f"\n=== Processing embed {idx}/{len(embed_urls)} ===")
        with tempfile.TemporaryDirectory(prefix="embed_download_") as tmp:
            tmp_dir = Path(tmp)
            print(f"Downloading audio from embed: {embed_url}")
            source_path, title = download_audio_from_url(embed_url, referer=page_url, browser=browser, out_dir=tmp_dir)
            context = SourceContext(
                source_kind="embedded_vimeo",
                original_input=page_url,
                original_url=page_url,
                download_url=embed_url,
                referer=page_url,
                source_label=title,
                folder_id=extract_video_id(embed_url),
            )
            results.append(process_source_file(source_path, context, browser, model, language, hf_token))

    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transcribe a local media file, a YouTube URL, or a webpage with embedded Vimeo videos."
    )
    parser.add_argument("input", help="Local file path, YouTube URL, or webpage URL")
    parser.add_argument("--model", default="small", help="WhisperX model")
    parser.add_argument("--language", default=None, help="Optional language hint, e.g. en")
    parser.add_argument("--browser", default=DEFAULT_BROWSER, help="Browser for cookies, e.g. chrome")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        raise UserFacingError("HF_TOKEN is not set")

    check_command("yt-dlp")
    check_command("ffmpeg")
    check_command("ffprobe")
    check_command("whisperx")
    TRANSCRIPTS_ROOT.mkdir(parents=True, exist_ok=True)

    user_input = args.input
    if is_local_file_input(user_input):
        process_local_file(user_input, args.browser, args.model, args.language, hf_token)
        return

    if is_youtube_url(user_input):
        process_youtube_url(user_input, args.browser, args.model, args.language, hf_token)
        return

    if is_probable_url(user_input):
        process_embedded_page(user_input, args.browser, args.model, args.language, hf_token)
        return

    raise UserFacingError(
        "Input was not recognized as an existing local file, a YouTube URL, or a valid webpage URL"
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        sys.exit(130)
    except UserFacingError as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as exc:
        print(f"\nCommand failed: {' '.join(exc.cmd)}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        print(f"\nUnexpected error: {exc}", file=sys.stderr)
        sys.exit(1)
