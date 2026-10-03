"""Образцы голоса Chatterbox Multilingual (MIT): живая нейросетевая озвучка на русском."""
import subprocess
import time
from pathlib import Path

import torchaudio
from chatterbox.mtl_tts import ChatterboxMultilingualTTS

OUT = Path("media/voice-tests")
OUT.mkdir(parents=True, exist_ok=True)
REF = "ref-ru.flac"  # образец голоса из демо Resemble, только для теста
SAMPLES = {
    # имя: (текст, референс, exaggeration, cfg)
    "cb-1-spokoyno": ("Клиент написал в вотсап в одиннадцать вечера. Вы ответили утром. А он уже купил у соседей. "
                      "Знакомо? Давайте сделаем так, чтобы бот отвечал за вас, даже ночью.", REF, 0.5, 0.5),
    "cb-2-zhivee": ("Клиент написал в вотсап в одиннадцать вечера. Вы ответили утром. А он уже купил у соседей. "
                    "Знакомо? Давайте сделаем так, чтобы бот отвечал за вас, даже ночью.", REF, 0.7, 0.3),
    "cb-3-whatsapp-latin": ("Пишите нам в WhatsApp, номер на экране. Пятнадцать дней работаем бесплатно.", REF, 0.6, 0.4),
    "cb-4-vatsap": ("Пишите нам в ватсап, номер на экране. Пятнадцать дней работаем бесплатно.", REF, 0.6, 0.4),
}

model = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
for name, (text, ref, ex, cfg) in SAMPLES.items():
    t = time.time()
    wav = model.generate(text, language_id="ru", audio_prompt_path=ref, exaggeration=ex, cfg_weight=cfg)
    path = OUT / f"{name}.wav"
    torchaudio.save(str(path), wav, model.sr)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(path), "-af", "loudnorm=I=-16",
                    "-b:a", "128k", str(OUT / f"{name}.mp3")], check=True)
    path.unlink()
    print(f"{name}: {time.time() - t:.0f} сек на синтез")
