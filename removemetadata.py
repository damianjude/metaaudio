#!/usr/bin/python3

import os
import sys
import argparse
from pathlib import Path
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, ID3NoHeaderError
from mutagen.flac import FLAC
from mutagen.wave import WAVE
from mutagen.aiff import AIFF
from mutagen import MutagenError

SUPPORTED_FORMATS = {'.mp3', '.flac', '.wav', '.aiff'}


def _is_within_directory(path: Path, base_dir: Path) -> bool:
    try:
        path.resolve().relative_to(base_dir)
        return True
    except (ValueError, OSError):
        return False

def remove_metadata(filepath, file_ext):
    try:
        if file_ext == ".mp3":
            audio = MP3(filepath, ID3=ID3)
            if audio.tags:
                audio.delete()
                audio.save()
                print(f"Metadata removed from: {filepath}")
            else:
                print(f"No metadata found in: {filepath}")

        elif file_ext == ".flac":
            audio = FLAC(filepath)
            if audio.tags:
                audio.clear()
                audio.save()
                print(f"Metadata removed from: {filepath}")
            else:
                print(f"No metadata found in: {filepath}")

        elif file_ext == ".wav":
            audio = WAVE(filepath)
            if hasattr(audio, 'tags') and audio.tags:
                audio.clear()
                audio.save()
                print(f"Metadata removed from: {filepath}")
            else:
                print(f"No metadata found in: {filepath}")

        elif file_ext == ".aiff":
            audio = AIFF(filepath)
            if hasattr(audio, 'tags') and audio.tags:
                audio.clear()
                audio.save()
                print(f"Metadata removed from: {filepath}")
            else:
                print(f"No metadata found in: {filepath}")

    except (ID3NoHeaderError, MutagenError) as e:
        print(f"Error removing metadata from {filepath}: {e}")

def process_directory(directory):
    base_dir = Path(directory).resolve()

    for root, _, files in os.walk(directory):
        for file in files:
            filepath = Path(root) / file
            file_ext = filepath.suffix.lower()

            if filepath.is_symlink():
                sys.stderr.write(f"Skipping symlinked file: {filepath}\n")
                continue

            if not _is_within_directory(filepath, base_dir):
                sys.stderr.write(f"Skipping file outside target directory: {filepath}\n")
                continue

            if file_ext in SUPPORTED_FORMATS:
                remove_metadata(str(filepath), file_ext)
            else:
                print(f"Skipped unsupported file: {filepath}")  # Optional if you want to see skipped files

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Remove metadata from all music files in a directory (.MP3, .FLAC, .WAV and .AIFF are supported)"
    )
    parser.add_argument("input_dir", help="The directory containing music files to process")
    args = parser.parse_args()

    if os.path.isdir(args.input_dir):
        process_directory(args.input_dir)
    else:
        sys.stderr.write(f"Directory not found: {args.input_dir}\n")