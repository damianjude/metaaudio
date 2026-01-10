#!/usr/bin/env python3

import sys
import requests
import numpy as np
import resampy
import soundfile as sf
import time
import socket
import ipaddress
from urllib.parse import urlparse

from pathlib import Path
from argparse import ArgumentParser
from mutagen.mp3 import MP3
from mutagen.id3 import ID3
from mutagen.id3._frames import APIC, TIT2, TPE1, TALB, TCON, TPUB, TYER, TDRC

from recognition.communication import recognise_song_from_signature
from recognition.algorithm import SignatureGenerator
from utils import _is_within_directory

MAX_COVERART_BYTES = 5 * 1024 * 1024


def _is_public_host(host: str) -> bool:
    try:
        ip_obj = ipaddress.ip_address(host)
        return not (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_reserved
            or ip_obj.is_multicast
            or ip_obj.is_unspecified
        )
    except ValueError:
        pass

    try:
        addr_info = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror:
        return False

    if not addr_info:
        return False

    seen_addresses = set()
    public_found = False

    for _, _, _, _, sockaddr in addr_info:
        ip_str = sockaddr[0]
        if ip_str in seen_addresses:
            continue
        seen_addresses.add(ip_str)

        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            continue

        if (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_reserved
            or ip_obj.is_multicast
            or ip_obj.is_unspecified
        ):
            continue

        public_found = True

    return public_found


def download_cover_art(url, filepath):
    if not url:
        return None

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        print(f"Skipping cover art: unsupported URL {url}", file=sys.stderr)
        return None

    hostname = parsed.hostname
    if not hostname or not _is_public_host(hostname):
        print(f"Skipping cover art: non-public host {hostname or '[missing]'}", file=sys.stderr)
        return None

    coverart_path = filepath.with_suffix('.jpeg')

    try:
        with requests.get(url, timeout=10, stream=True) as response:
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "").lower()
            content_base = content_type.split(";", 1)[0].strip()
            if not (content_base.startswith("image/jpeg") or content_base.startswith("image/jpg")):
                print(f"Skipping cover art: unsupported content type {content_type or '[missing]'}", file=sys.stderr)
                return None

            total_bytes = 0
            with coverart_path.open("wb") as buffer:
                for chunk in response.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    total_bytes += len(chunk)
                    if total_bytes > MAX_COVERART_BYTES:
                        print(f"Skipping cover art: exceeds {MAX_COVERART_BYTES} bytes limit", file=sys.stderr)
                        coverart_path.unlink(missing_ok=True)
                        return None
                    buffer.write(chunk)
    except (requests.RequestException, OSError):
        print("Skipping cover art: download error", file=sys.stderr)
        coverart_path.unlink(missing_ok=True)
        return None

    return coverart_path


def extract_metadata(results):
    matches = results.get("matches") or []
    match = matches[0] if matches else {}
    track_info = match.get("track") or match.get("item") or results.get("track") or match or {}

    sections = track_info.get("sections", []) if isinstance(track_info, dict) else []
    section_metadata = []
    for section in sections:
        metadata_block = section.get("metadata") or []
        if metadata_block:
            section_metadata = metadata_block
            break

    def find_meta(title):
        return next((meta.get("text", "") for meta in section_metadata if meta.get("title") == title), "")

    images = track_info.get("images", {}) if isinstance(track_info, dict) else {}
    genres = track_info.get("genres", {}) if isinstance(track_info, dict) else {}

    return {
        "title": track_info.get("title", "") if isinstance(track_info, dict) else "",
        "artist": track_info.get("subtitle", "") if isinstance(track_info, dict) else "",
        "album": find_meta("Album"),
        "genre": genres.get("primary", ""),
        "label": find_meta("Label"),
        "coverarturl": images.get("coverarthq", "") or images.get("coverart", ""),
        "year": find_meta("Released") or find_meta("Year"),
    }


def set_mp3_metadata(filepath, metadata, coverart_path):
    audio = MP3(filepath, ID3=ID3)

    if audio.tags is None:
        audio.tags = ID3()

    for frame in ("TIT2", "TPE1", "TALB", "TCON", "TPUB", "TYER", "TDRC", "APIC"):
        audio.tags.delall(frame)

    audio.tags.add(TIT2(encoding=3, text=metadata["title"]))
    audio.tags.add(TPE1(encoding=3, text=metadata["artist"]))
    audio.tags.add(TALB(encoding=3, text=metadata["album"]))
    audio.tags.add(TCON(encoding=3, text=metadata["genre"]))
    audio.tags.add(TPUB(encoding=3, text=metadata["label"]))
    audio.tags.add(TYER(encoding=3, text=metadata["year"]))
    audio.tags.add(TDRC(encoding=3, text=metadata["year"]))

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

    orig_kind = samples.dtype.kind
    orig_dtype = samples.dtype

    if samplerate != 16000:
        samples = resampy.resample(samples.astype('float32'), samplerate, 16000)

    # Normalize integer PCM to float in [-1, 1] to avoid wraparound
    if orig_kind in {'i', 'u'}:
        info = np.iinfo(orig_dtype)
        samples = samples.astype('float32')
        if orig_kind == 'u':
            midpoint = info.max / 2.0
            samples = (samples - midpoint) / midpoint
        else:
            max_int = max(abs(info.min), info.max) or 1
            samples = samples / max_int

    samples = np.clip(samples, -1.0, 1.0)
    samples = (samples * 32767).astype(np.int16)

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

    base_dir = input_dir.resolve()

    for filepath in mp3_files:

        if filepath.is_symlink():
            print(f"Skipping {filepath.name}: symlinked files are not processed", file=sys.stderr)
            continue

        try:
            resolved_path = filepath.resolve()
        except OSError as exc:
            print(f"Skipping {filepath.name}: could not resolve path ({exc})", file=sys.stderr)
            continue

        if not _is_within_directory(resolved_path, base_dir):
            print(f"Skipping {filepath.name}: file is outside the target directory", file=sys.stderr)
            continue

        filepath = resolved_path

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
        signature_generator.MAX_TIME_SECONDS = 12
        duration_seconds = len(samples) / 16000

        # Use a centered 12-second window on long files to skip lengthy intros/outros
        if duration_seconds > 36:
            start = max(0, int((duration_seconds / 2 - 6) * 16000))
            end = start + 12 * 16000
            samples_slice = samples[start:end]
        else:
            samples_slice = samples

        signature_generator.feed_input(samples_slice)

        results = "(Not enough data)"

        backoff_base = max(args.delay, 0.5)
        max_retries = 3
        retry = 0

        while True:
            signature = signature_generator.get_next_signature()
            if not signature:
                print(f"No signature generated for {filepath.stem}", file=sys.stderr)
                break

            results = recognise_song_from_signature(signature)

            if results.get("error"):
                retry += 1
                if retry > max_retries:
                    print(f"Recognition failed for {filepath.stem} after {max_retries} retries: {results['error']}", file=sys.stderr)
                    break

                backoff = max(backoff_base, backoff_base * (2 ** (retry - 1)))
                print(f"Recognition error for {filepath.stem}: {results['error']}. Retrying in {backoff:.2f}s...", file=sys.stderr)
                time.sleep(backoff)
                continue

            if results.get("matches"):
                metadata = extract_metadata(results)
                coverart_path = download_cover_art(metadata["coverarturl"], filepath)
                set_mp3_metadata(filepath, metadata, coverart_path)
                
                # Rename file to '<artist> - <title>.mp3' if --rename flag is set
                if args.rename:
                    unsafe = '\\/:*?"<>|'

                    def sanitize(text, fallback):
                        cleaned = ''.join('-' if (c in unsafe or ord(c) < 32) else c for c in (text or fallback))
                        cleaned = cleaned.strip().lstrip('.')
                        return cleaned or fallback

                    artist = sanitize(metadata.get("artist", "Unknown Artist"), "Unknown Artist")
                    title = sanitize(metadata.get("title", "Unknown Title"), "Unknown Title")

                    ext = filepath.suffix or ".mp3"
                    base_name = f"{artist} - {title}"
                    max_filename_length = 128
                    max_base_length = max(1, max_filename_length - len(ext))
                    if len(base_name) > max_base_length:
                        base_name = base_name[:max_base_length].rstrip()

                    new_name = f"{base_name}{ext}"
                    new_path = filepath.with_name(new_name)

                    if new_path.exists() and new_path != filepath:
                        if args.overwrite:
                            new_path.unlink()
                        else:
                            print(f"File {new_name} already exists, not renaming. Use --overwrite to replace existing files.", file=sys.stderr)
                            print(f"Finished writing metadata for {filepath.stem}.mp3")
                            break

                    if new_path != filepath:
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