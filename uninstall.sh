#!/usr/bin/env bash
# Removes only what install.sh created: the ~/.local/bin/xmusic launcher.
#   ./uninstall.sh           remove the launcher
#   ./uninstall.sh --purge   also remove ./venv and the XMusic config/data folders (settings, playlists)
# Your music files and this source folder are never touched (delete the folder yourself to finish).
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="${XDG_BIN_HOME:-$HOME/.local/bin}"
if [ -f "$BIN/xmusic" ] && grep -q "XMusic launcher" "$BIN/xmusic"; then
  rm -f "$BIN/xmusic"; echo "• removed $BIN/xmusic"
else
  echo "• no XMusic launcher found in $BIN"
fi
if [ "${1:-}" = "--purge" ]; then
  rm -rf "$DIR/venv" && echo "• removed $DIR/venv"
  for d in "${XDG_CONFIG_HOME:-$HOME/.config}/xmusic" "${XDG_DATA_HOME:-$HOME/.local/share}/xmusic" "$HOME/Library/Application Support/XMusic"; do
    [ -d "$d" ] && rm -rf "$d" && echo "• removed $d"
  done
fi
