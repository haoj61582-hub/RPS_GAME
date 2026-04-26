#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

python3 -m pip install --user pyinstaller

python3 -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "RPSBattlegrounds" \
  --osx-bundle-identifier "com.jiahao.rpsbattlegrounds" \
  --add-data "data:data" \
  --add-data "assets:assets" \
  --icon "assets/icons/app_crest.icns" \
  main.py

echo ""
echo "Build finished:"
echo "$ROOT_DIR/dist/RPSBattlegrounds.app"
