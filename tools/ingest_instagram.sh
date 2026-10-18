#!/usr/bin/env bash
# 抓取 IG 個人頁所有貼文（影片 + 圖 + caption metadata）到 data/raw/ig/
# 用法：tools/ingest_instagram.sh <帳號> [cookies.txt]
# 需要網路可連 instagram.com / cdninstagram.com / fbcdn.net；完整個人頁通常需要登入 cookie。
set -euo pipefail
account="${1:?usage: ingest_instagram.sh <account> [cookies.txt]}"
cookies="${2:-${IG_COOKIES:-}}"
root="$(cd "$(dirname "$0")/.." && pwd)"
out="$root/data/raw/ig"
mkdir -p "$out"

args=(--write-metadata --write-info-json -d "$out" -f "{post_shortcode}_{num}.{extension}")
[[ -n "$cookies" ]] && args+=(--cookies "$cookies")

# gallery-dl 依貼文 shortcode 分檔，--write-metadata 會留下 caption / 日期 / 互動數
gallery-dl "${args[@]}" -o "directory=[\"{post_shortcode}\"]" \
  "https://www.instagram.com/${account}/posts/" \
  "https://www.instagram.com/${account}/reels/"

echo "done → $out"
