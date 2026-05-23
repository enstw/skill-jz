---
name: yt2sub
description: Download and transcribe YouTube videos or local audio files. Uses yt-dlp and faster-whisper.
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Write
---

# /yt2sub - Transcribe and Summarize Media

This skill enables you to download audio from a YouTube video (or process a local audio file) and transcribe it using `faster-whisper`. 

## When to invoke

Invoke this skill whenever the user provides a YouTube URL or a local audio file and asks for a transcript, a summary, or wants to add the source to their research repository.

## Usage

The transcription is handled by the `scripts/yt2sub` script bundled with this skill.

```bash
# General format
<SKILL_DIR>/scripts/yt2sub <youtube-url|audio-file> [output-dir]
```

### Model Selection
By default, the script uses the `large-v3-turbo` model which provides an excellent balance of speed and accuracy. 
You can switch the model by setting the `WHISPER_MODEL` environment variable before running the script:

```bash
# Recommended default (fast and accurate)
WHISPER_MODEL=large-v3-turbo <SKILL_DIR>/scripts/yt2sub "https://youtube.com/..." ./work/refs

# For maximum accuracy (slower)
WHISPER_MODEL=large-v3 <SKILL_DIR>/scripts/yt2sub "https://youtube.com/..." ./work/refs

# For fastest transcription (lower accuracy)
WHISPER_MODEL=base <SKILL_DIR>/scripts/yt2sub "https://youtube.com/..." ./work/refs
```

## Post-Processing Workflow

1. **Wait for completion**: The script will download the audio (if a URL is provided) and run `faster-whisper`. The output will be saved as a `.txt` file in the specified `[output-dir]` (or the current directory if omitted), with the filename matching the video or audio title.
2. **Read the transcript**: Read the resulting `.txt` file.
3. **Format and Summarize**: 
   - Convert the transcript into a well-structured Markdown document.
   - Extract key points, quotes, and the overarching thesis.
   - If working within a research repository (e.g., academic templates), conform to its citation protocols (e.g., saving the summary in a specific `refs/` directory and updating bibliography files).
4. **Citation (if applicable)**: Proactively add the source metadata to the project's bibliography file if the user intends to cite it.
