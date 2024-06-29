#!/usr/bin/python3

import os
from sys import stderr
import argparse
from mutagen.mp3 import MP3
from mutagen.id3 import ID3
from mutagen.id3._util import error as ID3Error
from mutagen.flac import FLAC
from mutagen.wave import WAVE
from mutagen.aiff import AIFF

def remove_metadata(filepath):
    file_ext = os.path.splitext(filepath)[1].lower()

    try:
        if file_ext == ".mp3":
            audio = MP3(filepath, ID3=ID3)
            if audio.tags is not None:
                audio.delete()
                audio.save()
                print(f"Metadata removed from: {filepath}")
            else:
                print(f"No metadata found in: {filepath}")
        
        elif file_ext == ".flac":
            audio = FLAC(filepath)
            if audio.tags is not None:
                audio.clear()
                audio.save()
                print(f"Metadata removed from: {filepath}")
            else:
                print(f"No metadata found in: {filepath}")

        elif file_ext == ".wav":
            audio = WAVE(filepath)
            if audio.tags is not None:
                audio.delete()
                audio.save()
                print(f"Metadata removed from: {filepath}")
            else:
                print(f"No metadata found in: {filepath}")

        elif file_ext == ".aiff":
            audio = AIFF(filepath)
            if audio.tags is not None:
                audio.delete()
                audio.save()
                print(f"Metadata removed from: {filepath}")
            else:
                print(f"No metadata found in: {filepath}")

        else:
            print(f"Unsupported file format: {filepath}")

    except ID3Error as e:
        print(f"Error removing metadata from {filepath}: {e}")

def process_directory(directory):
    for root, _, files in os.walk(directory):
        for file in files:
            filepath = os.path.join(root, file)
            remove_metadata(filepath)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Remove metadata from all music files in a directory (.MP3, .FLAC, .WAV and .AIFF are supported)")
    parser.add_argument("input_dir", help="The directory containing music files to process")
    parser.print_help()

    args = parser.parse_args()

    if os.path.isdir(args.input_dir):
        process_directory(args.input_dir)
    else:
        stderr.write(f"Directory not found: {args.input_dir}")