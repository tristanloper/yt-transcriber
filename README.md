# YouTube Transcriber with Local Speaker Diarization

This project downloads audio from a YouTube video, transcribes it locally, and formats the result into simple speaker blocks like:

```text
SPEAKER A
Lorem ipsum dolor sit amet...

SPEAKER B
Lorem ipsum dolor sit amet...
```

It is designed for a local workflow on macOS using WhisperX, so it does **not** require OpenAI API credits.

## What it does

* Downloads audio from a YouTube video
* Converts the audio into a format suitable for transcription
* Transcribes speech locally with WhisperX
* Uses speaker diarization to distinguish between speakers
* Saves a clean text transcript in `SPEAKER A / SPEAKER B` block format

## What it does not do

* It does not identify speakers by their real names automatically
* It does not guarantee perfect speaker separation in noisy or overlapping audio
* It does not require or use the OpenAI API for transcription

Speaker diarization labels who spoke when, not who the speakers are by name. You can rename speakers manually after the transcript is generated.

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

Run the script with a real YouTube URL:

```bash
python app.py "https://www.youtube.com/watch?v=nrtXap6h2Dw"
```

If your script supports an explicit output path:

```bash
python app.py "https://www.youtube.com/watch?v=nrtXap6h2Dw" --output transcript.txt
```

## Expected workflow

When the script runs successfully, it should:

1. Download the audio from YouTube
2. Convert the audio with `ffmpeg`
3. Transcribe the audio with WhisperX
4. Align the transcript
5. Run speaker diarization with pyannote
6. Save the final `.txt` transcript in speaker-block format

## Output format

The final transcript should look like this:

```text
SPEAKER A
Lorem ipsum dolor sit amet, consectetur adipiscing elit.

SPEAKER B
Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.

SPEAKER C
Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris.
```

The speaker labels are generic by design.

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

* Speakers do not talk over one another too much
* The audio is reasonably clean
* The speakers have distinct voices
* There is not excessive background noise or music

Interviews, panels, and stage conversations usually work better than noisy recordings or heavily edited audio.

## Security note

Do not paste API keys or Hugging Face tokens into issue threads, chat logs, or screenshots. If a token is exposed, revoke it and create a new one.

## Future improvements

Potential upgrades for this project:

* Automatic cleanup of filler words
* Optional timestamps in a second output file
* Export to `.md` or `.docx`
* A simple web interface for pasting YouTube URLs
* Manual speaker renaming after transcription

## License

Add your preferred license here.

## Acknowledgments

This workflow depends on:

* WhisperX for local transcription and diarization
* pyannote for speaker diarization
* yt-dlp for audio download
* ffmpeg for audio conversion
