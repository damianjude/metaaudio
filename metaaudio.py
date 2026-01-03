#!/usr/bin/env python3

import sys
import requests
import numpy as np
import resampy
import soundfile as sf
import time

from pathlib import Path
from argparse import ArgumentParser
from mutagen.mp3 import MP3
from mutagen.id3 import ID3
from mutagen.id3._frames import APIC, TIT2, TPE1, TALB, TCON, TPUB, TYER

from recognition.communication import recognise_song_from_signature
from recognition.algorithm import SignatureGenerator


def download_cover_art(url, filepath):
    if not url:
        return None

    coverart_path = filepath.with_suffix('.jpeg')

    response = requests.get(url)
    coverart_path.write_bytes(response.content)

    return coverart_path


def extract_metadata(results):
    track_info = results.get("track", {})

    metadata = {
        "title": track_info.get("title", ""),
        "artist": track_info.get("subtitle", ""),
        "album": next((meta["text"] for meta in track_info.get("sections", [])[0].get("metadata", []) if meta["title"] == "Album"), ""),
        "genre": track_info.get("genres", {}).get("primary", ""),
        "label": next((meta["text"] for meta in track_info.get("sections", [])[0].get("metadata", []) if meta["title"] == "Label"), ""),
        "coverarturl": track_info.get("images", {}).get("coverarthq", ""),
        "year": next((meta["text"] for meta in track_info.get("sections", [])[0].get("metadata", []) if meta["title"] == "Released"), ""),
    }

    return metadata


def set_mp3_metadata(filepath, metadata, coverart_path):
    audio = MP3(filepath, ID3=ID3)

    if audio.tags is None:
        audio.tags = ID3()

    audio.tags.add(TIT2(encoding=3, text=metadata["title"]))
    audio.tags.add(TPE1(encoding=3, text=metadata["artist"]))
    audio.tags.add(TALB(encoding=3, text=metadata["album"]))
    audio.tags.add(TCON(encoding=3, text=metadata["genre"]))
    audio.tags.add(TPUB(encoding=3, text=metadata["label"]))
    audio.tags.add(TYER(encoding=3, text=metadata["year"]))

    if coverart_path and coverart_path.exists():
        audio.tags.add(
            APIC(
                encoding=3,
                mime="image/jpeg",
                type=3,
                desc="Cover",
                data=coverart_path.read_bytes()
            )
        )
        coverart_path.unlink()

    audio.save()


def load_audio(filepath):
    try:
        samples, samplerate = sf.read(filepath, always_2d=False)
    except RuntimeError as e:
        raise RuntimeError(f"Failed to read audio file '{filepath}': {e}")

    if samples.ndim > 1:
        samples = np.mean(samples, axis=1)

    if samplerate != 16000:
        samples = resampy.resample(samples.astype('float32'), samplerate, 16000)

    if samples.dtype.kind == 'f':
        samples = np.clip(samples, -1.0, 1.0)
        samples = (samples * 32767).astype(np.int16)
    else:
        samples = samples.astype(np.int16)

    return samples


def main():
    parser = ArgumentParser(
        prog="metaaudio",
        description="Generate a Shazam fingerprint from a sound file, perform song recognition towards Shazam's servers and append the metadata to the audio file (only .MP3 files are supported)"
    )
    parser.add_argument("input_dir", help="The directory containing .MP3 files to recognise")
    parser.add_argument("--rename", action="store_true", help="Rename MP3 files to '<artist> - <title>.mp3' format")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files when renaming (requires --rename)")
    parser.add_argument("--delay", type=float, default=0, help="Delay in seconds between processing files (default: 0)")
    args = parser.parse_args()

    if args.overwrite and not args.rename:
        print("--overwrite requires --rename; please specify both or remove --overwrite.", file=sys.stderr)
        sys.exit(1)
    input_dir = Path(args.input_dir)

    if not input_dir.is_dir():
        print(f"Directory not found: {input_dir}", file=sys.stderr)
        sys.exit(1)

    mp3_files = list(input_dir.glob("*.mp3"))

    if not mp3_files:
        print("No MP3 files found in the specified directory.", file=sys.stderr)
        sys.exit(1)

    for filepath in mp3_files:

        # Skip files that already have artist metadata not equal to 'Unknown'
        try:
            audio = MP3(filepath)
            artist = None
            if audio.tags is not None:
                id3 = ID3(filepath)
                if 'TPE1' in id3:
                    artist = id3['TPE1'].text[0]
            if artist and artist.strip().lower() != 'unknown':
                print(f"Skipping {filepath.name}: artist metadata already set to '{artist}'")
                continue
        except Exception as e:
            print(f"Warning: Could not read metadata from {filepath.name}: {e}", file=sys.stderr)

        samples = load_audio(filepath)
        time.sleep(args.delay)  # Sleep to avoid sending requests too quickly

        signature_generator = SignatureGenerator()
        signature_generator.feed_input(samples)

        signature_generator.MAX_TIME_SECONDS = 12
        duration_seconds = len(samples) / 16000

        if duration_seconds > 36:
            skip_samples = 16000 * (int(duration_seconds / 2) - 6)
            signature_generator.samples_processed += int(skip_samples)

        results = "(Not enough data)"

        while True:
            signature = signature_generator.get_next_signature()
            if not signature:
                print(f"No signature generated for {filepath.stem}", file=sys.stderr)
                break

            results = recognise_song_from_signature(signature)

            if results["matches"]:
                metadata = extract_metadata(results)
                coverart_path = download_cover_art(metadata["coverarturl"], filepath)
                set_mp3_metadata(filepath, metadata, coverart_path)
                
                # Rename file to '<artist> - <title>.mp3' if --rename flag is set
                if args.rename:
                    artist = metadata.get("artist", "Unknown Artist").strip().replace("/", "-")
                    title = metadata.get("title", "Unknown Title").strip().replace("/", "-")
                    new_name = f"{artist} - {title}.mp3"
                    new_path = filepath.with_name(new_name)
                    
                    if new_path != filepath:
                        if new_path.exists():
                            if args.overwrite:
                                new_path.unlink()
                                filepath.rename(new_path)
                                filepath = new_path
                                print(f"Renamed file to {new_name}")
                            else:
                                print(f"File {new_name} already exists, not renaming. Use --overwrite to replace existing files.", file=sys.stderr)
                        else:
                            filepath.rename(new_path)
                            filepath = new_path
                            print(f"Renamed file to {new_name}")
                    else:
                        print(f"File already has the correct name: {new_name}")
                
                print(f"Finished writing metadata for {filepath.stem}.mp3")
                break
            else:
                print(
                    f"Note: No matching songs for {filepath.stem} the first {signature_generator.samples_processed / 16000:.3f} seconds, trying to recognise more input...",
                    file=sys.stderr
                )


if __name__ == "__main__":
    main()