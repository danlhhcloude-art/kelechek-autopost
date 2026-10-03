"""Образцы голосов для сравнения: Vosk TTS (Apache 2.0) по всем дикторам русской модели и текущий Piper."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import media  # noqa: E402

TEXT = ("Клиент написал в ватсап в одиннадцать вечера. Вы ответили утром. "
        "А он уже купил у соседей. Знакомо? Давайте сделаем так, чтобы бот отвечал за вас, даже ночью.")
OUT = Path("media/voice-tests")
OUT.mkdir(parents=True, exist_ok=True)


def to_mp3(wav, name):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-af", "loudnorm=I=-16",
                    "-b:a", "128k", str(OUT / f"{name}.mp3")], check=True)


from vosk_tts import Model, Synth  # noqa: E402

model = Model(lang="ru")
synth = Synth(model)
speakers = model.config.get("num_speakers") or len(model.config.get("speaker_id_map", {})) or 5
print("Модель:", model.config.get("model_name", "?"), "дикторов:", speakers, model.config.get("speaker_id_map"))
for sid in range(int(speakers)):
    wav = OUT / f"vosk-{sid}.wav"
    try:
        synth.synth(TEXT, str(wav), speaker_id=sid)
    except Exception as e:  # noqa: BLE001
        print(f"диктор {sid}: {e}")
        continue
    to_mp3(wav, f"vosk-{sid}")
    wav.unlink()

wav = OUT / "piper-dmitri.wav"
if media.synthesize(TEXT, wav):
    to_mp3(wav, "piper-dmitri")
    wav.unlink()
print(sorted(p.name for p in OUT.iterdir()))
