# YouTube Transcriber with Local Speaker Diarization

This project downloads audio from a video URL, transcribes it locally, and saves organized outputs in a readable folder structure under:

```text
/Users/tristan/Documents/Transcripts/
```

Each run creates a folder named like:

```text
2026-03-12_future-of-local-journalism_nrtXap6h2Dw/
```

Inside that folder, the script saves:

* the original downloaded audio
* a plain Whisper transcript
* a diarized transcript in `SPEAKER A / SPEAKER B` block format
* the raw WhisperX diarization JSON
* metadata about the run

## Features

* Downloads audio from a video URL with `yt-dlp`
* Converts audio for transcription with `ffmpeg`
* Generates a plain local transcript with WhisperX
* Generates a speaker-diarized transcript with WhisperX + pyannote
* Saves all outputs in a readable, date-based folder
* Uses a local heuristic to generate a short human-readable folder slug from transcript content

## Output structure

The script saves results to:

```text
/Users/tristan/Documents/Transcripts/YYYY-MM-DD_short-headline_videoid/
```

Example:

```text
/Users/tristan/Documents/Transcripts/2026-03-12_future-of-local-journalism_nrtXap6h2Dw/
```

Typical contents:

```text
source_audio.m4a
whisper_transcript.txt
diarized_transcript.txt
whisperx_diarized_raw.json
metadata.json
```

## Transcript format

The diarized transcript is formatted like this:

```text
SPEAKER A
Lorem ipsum dolor sit amet, consectetur adipiscing elit.

SPEAKER B
Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
```

Speaker labels are generic by design. The script identifies who spoke when, but it does not infer real speaker names.

## Requirements

* macOS Terminal
* Python 3.12
* Homebrew
* `ffmpeg`
* `yt-dlp`
* `whisperx`
* A Hugging Face account
* Access to the gated `pyannote/speaker-diarization-community-1` model
* A Hugging Face read token

## Installation

### 1. Go to the project folder

```bash
cd /Users/tristan/Documents/Repos/youtube_transcriber
```

### 2. Recreate the virtual environment with Python 3.12

Python 3.12 is the recommended version for this project.

```bash
rm -rf .venv
/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate
python --version
```

If that Python path does not exist, find it with:

```bash
which python3.12
```

Then use the returned full path instead.

### 3. Install system dependencies

```bash
brew install ffmpeg yt-dlp
```

### 4. Install Python dependencies

With the virtual environment activated:

```bash
pip install --upgrade pip
pip install whisperx yt-dlp
```

## Hugging Face setup

Speaker diarization requires access to a gated pyannote model.

### 5. Create a Hugging Face token

Use the minimum permissions needed:

* Token type: **Fine-grained**
* Permission: **Read**

### 6. Accept access to the diarization model

In your browser, visit the pyannote speaker diarization model page and accept the access conditions for:

* `pyannote/speaker-diarization-community-1`

Make sure you do this with the **same Hugging Face account** that created your token.

### 7. Export the token

```bash
export HF_TOKEN="your_new_read_only_token"
```

If you previously exposed a token, revoke it and generate a fresh one first.

## Verify your environment

Run the following checks inside the virtual environment:

```bash
python --version
which python
which whisperx
which yt-dlp
which ffmpeg
which ffprobe
```

All commands should return valid paths.

## Usage

Run the script with a real video URL:

```bash
python app.py "https://www.youtube.com/watch?v=nrtXap6h2Dw"
```

The script will create a folder inside:

```text
/Users/tristan/Documents/Transcripts/
```

and save all generated outputs there.

## Expected workflow

When the script runs successfully, it should:

1. Download the source audio
2. Save the original audio file
3. Convert the audio with `ffmpeg`
4. Generate a plain Whisper transcript
5. Generate a speaker-diarized transcript
6. Save the raw diarization JSON
7. Write a metadata file
8. Rename the folder to a readable date + headline + video ID format

## Metadata

The script writes a `metadata.json` file containing details such as:

* original URL
* video ID
* video title
* output folder name
* creation date
* model used
* language setting

## Notes on naming

Folder names are generated using:

* the current date
* a short readable slug derived from transcript content
* the video ID

This keeps folders readable while still making them easy to trace back to the original source.

The current implementation uses a deterministic local heuristic for the slug rather than an online AI service.

## Troubleshooting

### Hugging Face 403 or gated model error

If you see a 403 error when WhisperX tries to run diarization, usually one of these is true:

* You did not accept the model’s access conditions
* Your token belongs to a different Hugging Face account
* Your token does not have read access
* Your old token was revoked and your shell is still using it

Set a fresh token and try again:

```bash
export HF_TOKEN="your_new_read_only_token"
```

### `whisperx` not found

Reinstall it inside the active virtual environment:

```bash
pip install whisperx
```

Then verify:

```bash
which whisperx
```

### `ffmpeg` or `ffprobe` not found

Install or reinstall ffmpeg:

```bash
brew install ffmpeg
```

Then verify:

```bash
which ffmpeg
which ffprobe
```

### `yt-dlp` not found

Install or reinstall it:

```bash
brew install yt-dlp
```

Or inside the virtual environment:

```bash
pip install yt-dlp
```

### Wrong Python version

If you run into environment issues under Python 3.14 or newer, recreate the virtual environment with Python 3.12 and reinstall dependencies.

## Notes on quality

Speaker diarization works best when:

* speakers do not talk over one another too much
* the audio is reasonably clean
* the speakers have distinct voices
* there is not excessive background noise or music

Interviews, panels, and stage conversations usually work better than noisy recordings or heavily edited audio.

## Security note

Do not paste API keys or Hugging Face tokens into issue threads, chat logs, or screenshots. If a token is exposed, revoke it and create a new one.

## Future improvements

Potential upgrades for this project:

* optional timestamps in a second output file
* export to `.md` or `.docx`
* a simple web interface for pasting video URLs
* manual speaker renaming after transcription
* replacing the local slug heuristic with a local LLM-generated headline
* broader support for non-YouTube embedded video pages

## License

Add your preferred license here.

## Acknowledgments

This workflow depends on:

* WhisperX for local transcription and diarization
* pyannote for speaker diarization
* yt-dlp for audio download
* ffmpeg for audio conversion
