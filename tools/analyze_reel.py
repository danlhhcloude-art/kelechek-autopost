"""Разбор Reels: объективные замеры ролика по секундам.

Склейки (смена кадра), темп монтажа, что происходит в первые 3 секунды (хук),
звук (есть ли, когда начинается, тишина), петля (похож ли последний кадр на первый),
формат. Плюс лист кадров по секундам, чтобы глазами оценить текст хука и призыв.
Хук и CTA по смыслу оценивает человек или Claude по листу кадров, скрипт даёт только цифры.

  python tools/analyze_reel.py video.mp4 out_dir
"""
import json
import re
import subprocess
import sys
from pathlib import Path


def run(args):
    return subprocess.run(args, capture_output=True, text=True)


def probe(path):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height,r_frame_rate",
             "-of", "json", str(path)])
    info = json.loads(r.stdout)
    video = next((s for s in info["streams"] if s["codec_type"] == "video"), {})
    return {"duration": round(float(info["format"]["duration"]), 2), "width": video.get("width"),
            "height": video.get("height"), "has_audio": any(s["codec_type"] == "audio" for s in info["streams"])}


def scene_scores(path):
    """Насколько меняется картинка каждые 0.25 сек (0..1). Плавные переходы тоже ловятся, не только жёсткие склейки."""
    r = run(["ffmpeg", "-nostdin", "-i", str(path), "-vf", "fps=4,select='gte(scene,0)',metadata=print", "-an", "-f", "null", "-"])
    times = [float(t) for t in re.findall(r"pts_time:([\d.]+)", r.stderr)]
    vals = [float(v) for v in re.findall(r"lavfi\.scene_score=([\d.]+)", r.stderr)]
    return list(zip(times, vals))


def cuts(scores, threshold=0.1):
    out = []
    for t, v in scores:
        if v > threshold and (not out or t - out[-1] > 0.6):
            out.append(round(t, 2))
    return out


def motion_per_second(scores, duration):
    """Живость кадра по секундам 0..100: сумма изменений картинки за секунду."""
    sec = [0.0] * (int(duration) + 1)
    for t, v in scores:
        sec[min(int(t), len(sec) - 1)] += v
    return [min(100, round(x * 250)) for x in sec]


def silences(path):
    r = run(["ffmpeg", "-nostdin", "-i", str(path), "-af", "silencedetect=n=-40dB:d=0.4", "-vn", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    return [(round(a, 2), round(b, 2)) for a, b in zip(starts, ends + [None] * (len(starts) - len(ends))) if b is not None]


def loudness(path):
    r = run(["ffmpeg", "-nostdin", "-i", str(path), "-af", "volumedetect", "-vn", "-f", "null", "-"])
    m = re.search(r"mean_volume: (-?[\d.]+) dB", r.stderr)
    return float(m.group(1)) if m else None


def loop_similarity(path, duration):
    """SSIM первого и последнего кадра: близко к 1, значит ролик замыкается в петлю."""
    r = run(["ffmpeg", "-nostdin", "-i", str(path), "-ss", f"{max(0, duration - 0.15):.2f}", "-i", str(path),
             "-filter_complex", "[0:v]trim=end_frame=1,scale=320:-2[a];[1:v]trim=end_frame=1,scale=320:-2[b];[a][b]ssim",
             "-f", "null", "-"])
    m = re.search(r"All:([\d.]+)", r.stderr)
    return round(float(m.group(1)), 3) if m else None


def contact_sheet(path, duration, out):
    cols = 6
    n = min(int(duration) + 1, 60)
    rows = (n + cols - 1) // cols
    run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(path), "-vf",
         f"fps=1,scale=240:-2,drawtext=text='%{{pts\\:hms}}':x=6:y=6:fontsize=18:fontcolor=yellow:box=1:boxcolor=black@0.6,tile={cols}x{rows}",
         "-frames:v", "1", str(out)])


def clamp(x):
    return max(0, min(100, round(x)))


def score(m):
    """Грубые баллы по цифрам. Это подсказка, а не приговор."""
    d, c = m["duration"], m["cuts"]
    shots = len(c) + 1
    avg = d / shots
    first3 = sum(1 for t in c if t <= 3)
    # монтаж: средний кадр 1.5–3.5 сек считаем живым темпом, дальше штраф
    montage = 100 - max(0, avg - 3.5) * 18 - max(0, 1.2 - avg) * 40
    # хук: смена картинки в первые 3 секунды и звук с первой секунды
    hook = 40 + min(first3, 3) * 15 + (15 if m["sound_starts_at"] is not None and m["sound_starts_at"] <= 0.5 else 0)
    # удержание: нет «мёртвых» секунд, где картинка почти не меняется
    gaps = [b - a for a, b in zip([0] + c, c + [d])]
    dead = sum(1 for x in m["motion_per_second"] if x < 5)
    retention = 100 - dead / max(1, len(m["motion_per_second"])) * 160
    # звук: есть, не тихо, без длинных пауз
    silent = sum(b - a for a, b in m["silences"])
    sound = 0 if not m["has_audio"] else 100 - silent / d * 150 - (20 if (m["mean_db"] or -99) < -30 else 0)
    loop = (m["loop_ssim"] or 0) * 100
    vertical = 100 if (m["height"] or 0) > (m["width"] or 0) else 40
    return {"Хук": clamp(hook), "Удержание": clamp(retention), "Монтаж": clamp(montage), "Звук": clamp(sound),
            "Петля": clamp(loop), "Формат 9:16": vertical, "longest_static": round(max(gaps), 2), "avg_shot": round(avg, 2)}


def main():
    path, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    m = probe(path)
    sc = scene_scores(path)
    m["cuts"] = cuts(sc)
    m["motion_per_second"] = motion_per_second(sc, m["duration"])
    m["silences"] = silences(path) if m["has_audio"] else []
    first_silence = next((s for s in m["silences"] if s[0] <= 0.05), None)
    m["sound_starts_at"] = (first_silence[1] if first_silence else 0.0) if m["has_audio"] else None
    m["mean_db"] = loudness(path) if m["has_audio"] else None
    m["loop_ssim"] = loop_similarity(path, m["duration"])
    m["scores"] = score(m)
    per_second = {}
    for t in m["cuts"]:
        per_second[int(t)] = per_second.get(int(t), 0) + 1
    m["cuts_per_second"] = [per_second.get(s, 0) for s in range(int(m["duration"]) + 1)]
    contact_sheet(path, m["duration"], out / "frames.png")
    (out / "metrics.json").write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: m[k] for k in ("duration", "width", "height", "sound_starts_at", "mean_db", "loop_ssim", "scores")},
                     ensure_ascii=False, indent=1))
    print("склейки:", m["cuts"])
    print("живость по секундам:", m["motion_per_second"])


if __name__ == "__main__":
    main()
