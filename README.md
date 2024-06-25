# MetaAudio

MetaAudio is a Python program that recognizes songs using the Shazam API, fetches song metadata, and applies this metadata to the song file.

## Features

- Recognize songs using the Shazam API
- Fetch song metadata (title, artist, album, track number)
- Apply metadata to audio files

## Prerequisites

- Python 3.6+
- FFmpeg (required for audio processing)

## Installation

1. **Install FFmpeg**:

   - **Windows**: 
   ```bash
   winget install "FFmpeg (Essentials Build)"
   ```
   - **macOS**: Use Homebrew:
     ```bash
     brew install ffmpeg
     ```
   - **Linux**: Use your distribution's package manager, for example:
     ```bash
     sudo apt install ffmpeg
     ```

2. **Clone this repo**
3. **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```