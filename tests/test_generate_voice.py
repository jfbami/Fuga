import importlib.util
from email.message import Message
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("generate_voice", ROOT / "scripts/generate_voice.py")
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


class AudioResponse:
    def __init__(self):
        self.headers = Message()
        self.headers["Content-Type"] = "audio/mpeg"

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        return b"test-audio"


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "Fuga/Guidance").mkdir(parents=True)
        (self.root / "Fuga/Guidance/VoiceCue.swift").write_text(
            (ROOT / "Fuga/Guidance/VoiceCue.swift").read_text())

    def run_generator(self, response):
        with patch.object(generator, "ROOT", self.root), \
             patch("sys.argv", ["generate_voice.py"]), \
             patch.dict("os.environ", {"ELEVENLABS_API_KEY": "test-only"}, clear=True), \
             patch("urllib.request.urlopen", side_effect=response) as request:
            generator.main()
            return request

    def test_generates_all_cues_with_default_voice(self):
        request = self.run_generator([AudioResponse() for _ in range(12)])
        self.assertEqual(len(list((self.root / "Fuga/VoiceAudio").glob("*.mp3"))), 12)
        self.assertEqual(request.call_count, 12)
        self.assertIn("3T3dPoABJjGZZAI1eif7", request.call_args.args[0].full_url)

    def test_failed_request_preserves_existing_audio(self):
        folder = self.root / "Fuga/VoiceAudio"
        folder.mkdir()
        existing = folder / "fuga_ahead.mp3"
        existing.write_bytes(b"previous-voice")
        with self.assertRaises(SystemExit):
            self.run_generator([AudioResponse(), urllib.error.URLError("offline")])
        self.assertEqual(existing.read_bytes(), b"previous-voice")
        self.assertEqual(len(list(folder.glob("*.mp3"))), 1)


if __name__ == "__main__":
    unittest.main()
