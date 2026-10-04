"""Generate short CC0 sine-wave sound effects for the GUI."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path


def main() -> None:
    """Write four small mono PCM WAV files under frontend/gui/assets/sounds."""
    output_dir = Path(__file__).resolve().parents[2] / "frontend" / "gui" / "assets" / "sounds"
    output_dir.mkdir(parents=True, exist_ok=True)
    sample_rate = 22_050
    sample_count = int(sample_rate * 0.12)
    frequencies = {"move": 440, "capture": 330, "check": 660, "game_end": 523}

    for event, frequency in frequencies.items():
        samples = bytearray()
        for sample_index in range(sample_count):
            progress = sample_index / sample_count
            envelope = min(1.0, progress * 30, (1.0 - progress) * 30)
            angle = 2 * math.pi * frequency * sample_index / sample_rate
            samples.extend(struct.pack("<h", int(8000 * envelope * math.sin(angle))))
        output_path = output_dir / f"{event}.wav"
        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(samples)


if __name__ == "__main__":
    main()
