#!/usr/bin/env python3
"""從 ChatGPT / Grok 匯出檔抽出所有生圖、生影片相關的對話，整理成 prompt 庫。

用法：
  python3 -I tools/parse_chat_exports.py <export.json 或資料夾> [...] [--out data/derived/prompts.jsonl]

ChatGPT 匯出的 conversations.json 依 mapping 樹還原順序；其他格式（Grok 等）退回通用 JSON 走訪，
抓出所有長度夠的文字欄位。只保留含視覺生成關鍵字的對話，每則訊息一行 JSONL。
"""
import argparse
import json
import re
from pathlib import Path

KEYWORDS = re.compile(
    r"prompt|生圖|生成|影片|短片|剪輯|鏡頭|運鏡|旁白|hook|參考圖|臨摹|質感|手機|iphone|底片|film|flash|閃光|"
    r"cinematic|lighting|打光|sora|kling|runway|veo|midjourney|grok imagine|aurora|4:3|蒙太奇|montage",
    re.I,
)


def chatgpt_messages(conv):
    mapping = conv.get("mapping") or {}
    node_id = conv.get("current_node")
    chain = []
    while node_id and node_id in mapping:
        node = mapping[node_id]
        msg = node.get("message")
        if msg and msg.get("content"):
            parts = msg["content"].get("parts") or []
            text = "\n".join(p for p in parts if isinstance(p, str)).strip()
            has_image = any(isinstance(p, dict) and "image" in str(p.get("content_type", "")) for p in parts)
            if text or has_image:
                chain.append({"role": msg["author"]["role"], "text": text, "has_image": has_image,
                              "time": msg.get("create_time")})
        node_id = node.get("parent")
    return list(reversed(chain))


def generic_texts(obj, acc):
    if isinstance(obj, dict):
        role = obj.get("sender") or obj.get("role") or obj.get("author")
        text = obj.get("message") or obj.get("text") or obj.get("content")
        if isinstance(text, str) and len(text) > 8:
            acc.append({"role": role if isinstance(role, str) else None, "text": text.strip(), "has_image": False,
                        "time": obj.get("create_time") or obj.get("createTime") or obj.get("timestamp")})
        for v in obj.values():
            if isinstance(v, (dict, list)):
                generic_texts(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            generic_texts(v, acc)


def conversations(path):
    data = json.loads(path.read_text())
    if isinstance(data, list) and data and isinstance(data[0], dict) and "mapping" in data[0]:
        for conv in data:
            yield "chatgpt", conv.get("title"), chatgpt_messages(conv)
        return
    convs = data.get("conversations", [data]) if isinstance(data, dict) else data
    for conv in convs:
        acc = []
        generic_texts(conv, acc)
        title = conv.get("title") if isinstance(conv, dict) else None
        yield "generic", title, acc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--out", default="data/derived/prompts.jsonl")
    args = ap.parse_args()

    files = []
    for i in map(Path, args.inputs):
        files += sorted(i.rglob("*.json")) if i.is_dir() else [i]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    kept = 0
    with out.open("w") as f:
        for path in files:
            try:
                convs = list(conversations(path))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            for source, title, msgs in convs:
                if not any(KEYWORDS.search(m["text"]) for m in msgs) and not KEYWORDS.search(title or ""):
                    continue
                kept += 1
                for n, m in enumerate(msgs):
                    f.write(json.dumps({"file": path.name, "source": source, "conversation": title, "n": n, **m},
                                       ensure_ascii=False) + "\n")
    print(f"{kept} conversations → {out}")


if __name__ == "__main__":
    main()
