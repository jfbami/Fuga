#!/usr/bin/env python3
"""Generate offline ElevenLabs guidance. Requires Python 3; no dependencies."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--voice-id", default=os.environ.get("ELEVENLABS_VOICE_ID", "3T3dPoABJjGZZAI1eif7"))
    parser.add_argument("--model-id", default="eleven_multilingual_v2")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    # Use the Swift vocabulary as the source of truth for fallback and generated audio.
    source = (ROOT / "Fuga/Guidance/VoiceCue.swift").read_text()
    cues = dict(re.findall(r'case \.(\w+): return "([^"\n]+)"', source))
    if len(cues) != 12:
        parser.error("Expected twelve voice cues in VoiceCue.swift; check the vocabulary parser.")
    if args.dry_run:
        print(json.dumps(cues, indent=2))
        return
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key or not args.voice_id:
        parser.error("Set ELEVENLABS_API_KEY locally before generation.")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.voice_id):
        parser.error("Invalid voice ID")
    output = ROOT / "Fuga/VoiceAudio"
    output.mkdir(exist_ok=True)
    # Fetch all clips before replacing any existing set, avoiding mixed voices on failure.
    clips = {}
    for cue, text in cues.items():
        request = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{args.voice_id}?output_format=mp3_44100_128",
            data=json.dumps({"text": text, "model_id": args.model_id}).encode(),
            headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                audio = response.read()
                if response.headers.get_content_type() != "audio/mpeg" or not audio:
                    raise ValueError("Expected nonempty MP3 audio")
                clips[cue] = audio
        except urllib.error.HTTPError as error:
            sys.exit(f"ElevenLabs returned HTTP {error.code} for {cue}. Check key permissions, voice access, and quota.")
        except (urllib.error.URLError, TimeoutError, ValueError):
            sys.exit(f"Could not generate {cue}; check your connection and retry. Existing clips were preserved.")
    for cue, audio in clips.items():
        path = output / f"fuga_{cue}.mp3"
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(audio)
        temporary.replace(path)
        print(f"Wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
