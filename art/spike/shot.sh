#!/bin/zsh
# shot.sh <path?query> <out.png> [w] [h]: headless Chrome screenshot of the spike served on :8765.
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu-sandbox \
  --use-angle=swiftshader --enable-unsafe-swiftshader --hide-scrollbars \
  --window-size=${3:-1280},${4:-720} --virtual-time-budget=${5:-8000} \
  --screenshot="$2" "http://localhost:8765/$1" >/dev/null 2>&1
