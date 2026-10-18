#!/usr/bin/env python3
"""把一支短片拆成可分析的結構：裁黑邊回原比例、鏡頭表、關鍵影格、contact sheet、旁白逐字稿。

用法：
  python3 -I tools/analyze_video.py <video> [<video> ...] [--out data/derived/videos] [--transcribe]

每支片輸出 <out>/<id>/：
  analysis.json   比例、裁切、鏡頭表（in/out/秒數）、hook 段、平均鏡長、逐字稿
  cropped.mp4     去掉 9:16 上下黑邊後的原始畫幅（沒有黑邊就不輸出）
  shots/NNN.jpg   每個鏡頭中點的影格
  contact.jpg     所有鏡頭的縮圖拼板
"""
import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path

HOOK_SECONDS = 3.0


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    info = json.loads(out)
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    has_audio = any(s["codec_type"] == "audio" for s in info["streams"])
    return int(video["width"]), int(video["height"]), float(info["format"]["duration"]), has_audio


def detect_crop(path, duration):
    """用 ffmpeg cropdetect 找出最常見的有效畫面範圍（處理 4:3 被放進 9:16 的上下黑邊）。"""
    start = max(0.0, duration * 0.1)
    err = subprocess.run(
        ["ffmpeg", "-hide_banner", "-ss", f"{start:.2f}", "-i", str(path), "-t", "8",
         "-vf", "cropdetect=limit=24:round=2:reset=0", "-f", "null", "-"],
        capture_output=True, text=True,
    ).stderr
    crops = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", err)
    if not crops:
        return None
    w, h, x, y = map(int, crops[-1])
    return w, h, x, y


def detect_shots(path):
    from scenedetect import ContentDetector, detect

    scenes = detect(str(path), ContentDetector(threshold=27.0))
    return [(s.seconds, e.seconds) for s, e in scenes]


def grab_frame(path, t, dest, crop):
    vf = [f"crop={crop[0]}:{crop[1]}:{crop[2]}:{crop[3]}"] if crop else []
    vf.append("scale=480:-2")
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.3f}", "-i", str(path),
         "-frames:v", "1", "-vf", ",".join(vf), "-q:v", "3", str(dest)],
        check=True,
    )


def contact_sheet(frames, dest, cols=6):
    import cv2
    import numpy as np

    imgs = [cv2.imread(str(f)) for f in frames]
    imgs = [i for i in imgs if i is not None]
    if not imgs:
        return
    h = min(i.shape[0] for i in imgs)
    imgs = [cv2.resize(i, (int(i.shape[1] * h / i.shape[0]), h)) for i in imgs]
    w = max(i.shape[1] for i in imgs)
    rows = math.ceil(len(imgs) / cols)
    sheet = np.zeros((rows * h, cols * w, 3), dtype=np.uint8)
    for n, img in enumerate(imgs):
        r, c = divmod(n, cols)
        sheet[r * h:(r + 1) * h, c * w:c * w + img.shape[1]] = img
    cv2.imwrite(str(dest), sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])


def transcribe(path):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("  faster-whisper 未安裝，略過逐字稿", file=sys.stderr)
        return None
    model = WhisperModel("small", compute_type="int8")
    segments, info = model.transcribe(str(path), vad_filter=True)
    segs = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()} for s in segments]
    return {"language": info.language, "segments": segs}


def analyze(path, out_root, do_transcribe):
    path = Path(path)
    out = out_root / path.stem
    (out / "shots").mkdir(parents=True, exist_ok=True)

    width, height, duration, has_audio = probe(path)
    crop = detect_crop(path, duration)
    if crop and (crop[0], crop[1]) == (width, height):
        crop = None
    eff_w, eff_h = (crop[0], crop[1]) if crop else (width, height)

    if crop:
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(path),
             "-vf", f"crop={crop[0]}:{crop[1]}:{crop[2]}:{crop[3]}", "-c:a", "copy", str(out / "cropped.mp4")],
            check=True,
        )

    shots = detect_shots(path) or [(0.0, duration)]
    frames = []
    shot_rows = []
    for n, (s, e) in enumerate(shots, 1):
        frame = out / "shots" / f"{n:03d}.jpg"
        grab_frame(path, (s + e) / 2, frame, crop)
        frames.append(frame)
        shot_rows.append({"n": n, "in": round(s, 3), "out": round(e, 3), "dur": round(e - s, 3),
                          "frame": f"shots/{frame.name}"})
    contact_sheet(frames, out / "contact.jpg")

    durs = [r["dur"] for r in shot_rows]
    result = {
        "source": path.name,
        "duration": round(duration, 3),
        "frame_size": [width, height],
        "crop": crop,
        "content_size": [eff_w, eff_h],
        "content_aspect": round(eff_w / eff_h, 3),
        "is_4x3": abs(eff_w / eff_h - 4 / 3) < 0.05,
        "has_audio": has_audio,
        "shot_count": len(shot_rows),
        "avg_shot_len": round(sum(durs) / len(durs), 3),
        "hook": {"seconds": HOOK_SECONDS, "shots": [r["n"] for r in shot_rows if r["in"] < HOOK_SECONDS]},
        "shots": shot_rows,
        "transcript": transcribe(path) if (do_transcribe and has_audio) else None,
    }
    (out / "analysis.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"{path.name}: {eff_w}x{eff_h} ({result['content_aspect']}), {len(shot_rows)} shots, "
          f"avg {result['avg_shot_len']}s → {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("videos", nargs="+")
    ap.add_argument("--out", default="data/derived/videos")
    ap.add_argument("--transcribe", action="store_true")
    args = ap.parse_args()
    out_root = Path(args.out)
    for v in args.videos:
        try:
            analyze(v, out_root, args.transcribe)
        except Exception as exc:  # 單支失敗不影響整批
            print(f"{v}: FAILED {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
