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

- **Remove all metadata from music files**:

  ```bash
  python3 removemetadata.py /path/to/your/music/directory
  ```

---

## Known Issues

- **Misrecognition by Shazam**:\
  Occasionally, Shazam may incorrectly identify a song, resulting in wrong metadata (such as title or artwork).\
  This is a limitation of the Shazam service itself, not MetaAudio.\
  For such cases, use the `removemetadata.py` tool to clear incorrect tags.