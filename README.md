# MetaAudio

**MetaAudio** is a lightweight Python tool that recognises songs using Shazam’s service, fetches accurate song metadata, and applies it directly to your music files.

---

## Features

- Recognises songs via Shazam
- Retrieves metadata including title, artist, album, genre, and cover art
- Writes metadata directly to music files
- Provides a tool to remove all metadata if needed

---

## Installation

1. **Clone this repository**:

2. **Install Python dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

---

## Usage

- **Recognise songs and update metadata**:

  ```bash
  python3 metaaudio.py /path/to/your/music/directory
  ```

- **Rename files with optional overwrite**:
  Use the `--rename` argument to automatically rename mp3 files to `<artist> - <title>.mp3`:
  ```bash
  python3 metaaudio.py /path/to/your/music/directory --rename
  ```

  And `--overwrite` to overwrite `<artist> - <title>.mp3` if it already exists:

  ```bash
  python3 metaaudio.py /path/to/your/music/directory --rename --overwrite
  ```

- **Configure delay between processing files**:
  By default, there is no delay (i.e., 0 seconds) between processing files, but a delay (in seconds) can be added using `--delay`. This can help avoid Shazham API rate limiting issues.
  ```bash
  python3 metaaudio.py /path/to/your/music/directory --delay 0.5
  ```

- **Remove all metadata from music files**:

  ```bash
  python3 removemetadata.py /path/to/your/music/directory
  ```

### Command-line Options

- `--rename`: Rename MP3 files to `<artist> - <title>.mp3` format
- `--overwrite`: Overwrite existing files when renaming (requires `--rename`)
- `--delay`: Delay in seconds between processing files (default: 0.5)

---

## Known Issues

- **Misrecognition by Shazam**:\
  Occasionally, Shazam may incorrectly identify a song, resulting in wrong metadata (such as title or artwork).\
  This is a limitation of the Shazam service itself, not MetaAudio.\
  For such cases, use the `removemetadata.py` tool to clear incorrect tags.