# Local Video Transcriber with Speaker Diarization

This project transcribes audio and video into two text outputs:

* a plain transcript
* a diarized transcript grouped into `SPEAKER A`, `SPEAKER B`, and so on

It is designed for local use on macOS and saves each run into a structured folder under the current user's Documents directory:

```text
/Users/<your-username>/Documents/Transcripts/
```

The script creates `Documents/Transcripts` automatically if it does not already exist. It does not create unrelated directories such as `Repos`.

## What it supports

The script accepts three kinds of input:

### 1. Local media file

Examples:

```bash
python app.py "/Users/<your-username>/Downloads/interview.mp3"
python app.py "/Users/<your-username>/Movies/panel.mp4"
```

### 2. YouTube URL

Example:

```bash
python app.py "https://www.youtube.com/watch?v=nrtXap6h2Dw"
```

### 3. Webpage with embedded or access-restricted Vimeo videos

Example:

```bash
python app.py "https://example.com/private-event-replay/"
```

For embedded or access-restricted Vimeo pages, the script uses your browser cookies and the embedding page context to find and process the underlying player URLs.

## Output structure

Each processed source creates a folder like:

```text
/Users/<your-username>/Documents/Transcripts/2026-03-12_future-of-local-journalism_nrtXap6h2Dw/
```

Inside that folder, the script saves:

```text
source_audio.m4a
whisper_transcript.txt
diarized_transcript.txt
whisperx_diarized_raw.json
metadata.json
```

For local files, `source_audio` keeps the original extension, such as `.mp3`, `.wav`, or `.mp4`.

## Transcript format

The diarized transcript looks like this:

```text
SPEAKER A
Thanks everyone for joining us today.

SPEAKER B
Happy to be here. Let’s get started.
```

Speaker labels are generic by design. The script identifies speaker turns, not speaker names.

## Requirements

* macOS
* Python 3.12
* Homebrew
* `ffmpeg`
* `yt-dlp`
* `whisperx`
* `browser-cookie3`
* `requests`
* `python-dotenv`
* A Hugging Face account
* Access to the gated `pyannote/speaker-diarization-community-1` model
* A Hugging Face read token stored in `env.local` or `.env`

## Installation

### 1. Go to your project directory

```bash
cd /path/to/your/project
```

### 2. Create a fresh virtual environment with Python 3.12

```bash
rm -rf .venv
python3.12 -m venv .venv
source .venv/bin/activate
python --version
```

If `python3.12` is not on your path, find it with:

```bash
which python3.12
```

Then use the full path returned by that command.

### 3. Install system dependencies

```bash
brew install ffmpeg yt-dlp
```

### 4. Install Python dependencies

```bash
python -m pip install --upgrade pip
python -m pip install whisperx yt-dlp browser-cookie3 requests python-dotenv
```

## Secret management

Use a local env file for secrets.

### Recommended: `env.local`

Create a file named `env.local` in the project root:

```text
HF_TOKEN=your_hugging_face_token_here
```

The app loads `env.local` first and then `.env` if present.

### Add it to `.gitignore`

```gitignore
env.local
.env
```

### Optional example file

You can commit a placeholder file like `.env.example` containing:

```text
HF_TOKEN=your_token_here
```

## Hugging Face setup

Speaker diarization requires access to a gated pyannote model.

### 5. Create a Hugging Face token

Use the minimum permissions:

* token type: **Fine-grained**
* permission: **Read**

### 6. Accept access to the diarization model

Visit the model page in your browser and accept the access conditions for:

* `pyannote/speaker-diarization-community-1`

Make sure you do this with the same Hugging Face account that created your token.

## Usage

### Local file

```bash
python app.py "/Users/<your-username>/Downloads/interview.mp3"
```

### YouTube

```bash
python app.py "https://www.youtube.com/watch?v=nrtXap6h2Dw"
```

### Embedded or restricted Vimeo page

```bash
python app.py "https://example.com/private-event-replay/"
```

## How the script decides what to do

The input flow is:

1. If the input is an existing local file path, process it directly.
2. Else if the input is a YouTube URL, download and process it directly.
3. Else if the input is another URL, treat it as a webpage and scan for embedded Vimeo player URLs.

## What the script does

For each source, the script:

1. copies or downloads the source media
2. creates a transcript folder under `~/Documents/Transcripts`
3. saves the source file into that folder
4. converts the source to a WAV file with `ffmpeg`
5. generates a plain transcript with WhisperX
6. generates a diarized transcript with WhisperX + pyannote
7. saves the raw diarization JSON
8. writes metadata for traceability
9. renames the folder to a readable date + headline + id format

## Metadata

Each transcript folder includes a `metadata.json` file with information such as:

* original input
* source type
* original URL
* local file path, if applicable
* download URL, if applicable
* referer page, if applicable
* folder identifier
* source label/title
* model used
* language
* browser used for cookie loading

## Notes on naming

Folder names use:

* the current date
* a short readable slug derived from transcript content
* a stable identifier

This keeps folders readable while still making them easy to trace back to the source.

## Troubleshooting

### `HF_TOKEN is not set`

Create `env.local` or `.env` in the project root and add:

```text
HF_TOKEN=your_hugging_face_token_here
```

### `No module named 'dotenv'`

Install the dotenv package inside the active virtual environment:

```bash
python -m pip install python-dotenv
```

### Hugging Face 403 or gated model error

Usually one of these is true:

* you did not accept the model’s access conditions
* your token belongs to a different Hugging Face account
* your token does not have read access
* your shell is still using an old token

### `whisperx` not found

Reinstall it inside the active virtual environment:

```bash
python -m pip install whisperx
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

Or install it in the virtual environment:

```bash
python -m pip install yt-dlp
```

### YouTube downloads fail with challenge or reload errors

If YouTube returns challenge-solver or "The page needs to be reloaded" errors, your `yt-dlp` install may need the EJS remote challenge solver. A common fix is to use:

```bash
yt-dlp --remote-components ejs:github --cookies-from-browser chrome -f bestaudio/best "YOUTUBE_URL"
```

If that works manually, add the same `--remote-components ejs:github` flag to the `yt-dlp` command used by the app.

### Embedded Vimeo page finds no videos

This usually means one of these:

* the page content is not accessible with your current browser session
* the embeds are loaded in a more dynamic way than expected
* the page is not using Vimeo embeds in the format the script currently scans for

In that case, confirm you can view the page in the same browser whose cookies you are using.

## Notes on quality

Speaker diarization works best when:

* speakers do not talk over one another too much
* the audio is reasonably clean
* there is limited background noise
* speakers have distinct voices

Interviews, stage conversations, and panel discussions usually work better than noisy recordings or highly edited audio.

## Security note

Do not paste Hugging Face tokens into chat logs, screenshots, issue threads, or commits. If a token is exposed, revoke it and generate a new one.

Browser cookies are used transiently when needed for restricted or embedded video access, but they should not be exported or committed as project files.

## Future improvements

Possible next steps:

* optional timestamps in a second output file
* export to Markdown or DOCX
* manual speaker renaming
* better embedded-video detection beyond Vimeo
* optional local LLM-based folder naming
* a small web UI for pasting links

## License

Add your preferred license here.

## Acknowledgments

This workflow depends on:

* WhisperX for local transcription and diarization
* pyannote for speaker diarization
* yt-dlp for media download
* ffmpeg for audio conversion
* browser-cookie3 for browser session cookie access
* python-dotenv for local secret loading
