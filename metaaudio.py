#!/usr/bin/python3

from curses import meta
import os
from sys import stderr
from argparse import ArgumentParser
from pydub import AudioSegment
from json import dumps, loads
import requests
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from mutagen.id3 import ID3
from mutagen.id3._frames import APIC, TIT2, TPE1, TALB, TCON, TPUB, TYER
from mutagen.id3._util import error
from mutagen.flac import FLAC, Picture

from recognition.communication import recognize_song_from_signature
from recognition.algorithm import SignatureGenerator

def downloadcoverart(url, filepath):
    if not url:
        return None
    # Extract directory and filename without extension
    directory = os.path.dirname(filepath)
    filename_without_ext = os.path.splitext(os.path.basename(filepath))[0]
    
    # Construct the filepath for the cover art
    coverart_filepath = os.path.join(directory, f"{filename_without_ext}.jpeg")
    
    # Download the cover art
    response = requests.get(url)
    with open(coverart_filepath, "wb") as f:
        f.write(response.content)
    
    return coverart_filepath

def extractmetadata(results):
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

def setmp3metadata(filepath, metadata, coverartimage):
    audio = MP3(filepath, ID3=ID3)

    # Check if tags exist, create them if not
    if audio.tags is None:
        audio.tags = ID3()

    # Update or add specific tags
    audio.tags.add(TIT2(encoding=3, text=metadata["title"]))
    audio.tags.add(TPE1(encoding=3, text=metadata["artist"]))
    audio.tags.add(TALB(encoding=3, text=metadata["album"]))
    audio.tags.add(TCON(encoding=3, text=metadata["genre"]))
    audio.tags.add(TPUB(encoding=3, text=metadata["label"]))
    audio.tags.add(TYER(encoding=3, text=metadata["year"]))

    # Add album art if coverartimage exists
    if coverartimage and os.path.exists(coverartimage):
        with open(coverartimage, "rb") as albumart:
            audio.tags.add(
                APIC(
                    encoding=3,  # UTF-8
                    mime="image/jpeg",  # Adjust MIME type if necessary
                    type=3,  # Cover (front) image
                    desc=u"Cover",
                    data=albumart.read()
                )
            )

        os.remove(coverartimage)

    # Save the updated tags to the audio file
    audio.save()

if __name__ == "__main__":
    parser = ArgumentParser(prog="metaaudio", description="Generate a Shazam fingerprint from a sound file, perform song recognition towards Shazam's servers and print obtained information to the standard output")
    
    parser.add_argument("input_dir", help="The directory containing .MP3 files to recognise")
    parser.print_help()
    
    args = parser.parse_args()

    music = []

    if os.path.exists(args.input_dir):
        for filename in os.listdir(args.input_dir):
            file_path = os.path.join(args.input_dir, filename)
            if os.path.isfile(file_path) and file_path.lower().endswith((".mp3")):
                music.append(file_path)
    else:
        stderr.write("Directory not found\n")
    
    for filepath in music:

        audio = AudioSegment.from_file(filepath)
        
        audio = audio.set_sample_width(2)
        audio = audio.set_frame_rate(16000)
        audio = audio.set_channels(1)
        
        signature_generator = SignatureGenerator()
        signature_generator.feed_input(audio.get_array_of_samples())
        
        # Prefer starting at the middle at the song, and with a
        # substantial bit of music to provide.
        
        signature_generator.MAX_TIME_SECONDS = 12
        if audio.duration_seconds > 12 * 3:
            signature_generator.samples_processed += 16000 * (int(audio.duration_seconds / 2) - 6)
        
        results = "(Not enough data)"
        
        while True:
            
            signature = signature_generator.get_next_signature()
            
            if not signature:
                print(dumps(results, indent = 4, ensure_ascii = False))
                break
            
            results = recognize_song_from_signature(signature)
            
            if results["matches"]:
                metadata = extractmetadata(results)
                coverartimage = downloadcoverart(metadata["coverarturl"], filepath)
                setmp3metadata(filepath, metadata, coverartimage)
                print(f"Finished writing metadata for {os.path.splitext(os.path.basename(filepath))[0]}.mp3")
                break
            
            else:
                stderr.write(f"Note: No matching songs for {os.path.splitext(os.path.basename(filepath))[0]} the first {signature_generator.samples_processed / 16000} seconds, trying to recognize more input...\n")
                stderr.flush()