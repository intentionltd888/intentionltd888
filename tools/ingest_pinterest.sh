#!/usr/bin/env bash
# 一次性抓取 Pinterest 使用者所有公開圖板的 pin 圖與 metadata 到 data/raw/pinterest/<board>/
# 用法：tools/ingest_pinterest.sh <使用者名稱>
# 需要網路可連 pinterest.com / pinimg.com。
set -euo pipefail
user="${1:?usage: ingest_pinterest.sh <user>}"
root="$(cd "$(dirname "$0")/.." && pwd)"
out="$root/data/raw/pinterest"
mkdir -p "$out"

# --write-metadata 留下 pin 標題、描述、來源連結、所屬圖板，之後消化時用
gallery-dl --write-metadata -d "$out" \
  -o 'directory=["{board[name]}"]' \
  -f '{id}.{extension}' \
  "https://www.pinterest.com/${user}/"

echo "done → $out"
