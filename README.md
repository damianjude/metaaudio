# MetaAudio

MetaAudio is a Python program that recognises songs using Shazam's service, fetches song metadata, and applies this metadata to the song file.

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

## Usage

1. **To recognise songs and update metadata:**
  ```bash
  python3 metaaudio.py /path/to/your/music/directory
  ```

2. **To remove metadata from all music files in a given directory:**
  ```bash
  python3 removemetadata.py /path/to/your/music/directory
  ```

## Known Issues
**Misrecognition by Shazam**: Sometimes, Shazam's servers may misrecognise a song, resulting in incorrect metadata such as the song's name or artwork being different from what the song actually is. This is a known issue with the Shazam service and not with the MetaAudio tool itself. This is why I created `removemetadata.py`.