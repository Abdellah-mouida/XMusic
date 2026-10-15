#!/usr/bin/env bash
# Generates a small tagged MP3 library (+ corrupt/empty/garbage files) in $1 (default /tmp/Music). Needs ffmpeg.
set -e
R="${1:-/tmp/Music}"; mkdir -p "$R/Rock" "$R/Jazz/Live"; cd "$R"
mk(){ ffmpeg -loglevel error -y -f lavfi -i "sine=frequency=$2:duration=$3" -metadata title="$4" -metadata artist="$5" -metadata album="$6" -b:a 64k "$1"; }
mk "Rock/01 Alpha.mp3" 440 12 "Alpha Wave" "The Sines" "Pure Tones"
mk "Rock/02 Beta.mp3" 523 9 "Beta Burst" "The Sines" "Pure Tones"
mk "Jazz/Gamma.mp3" 330 7 "Gamma Ray" "Blue Cats" "Midnight"
mk "Jazz/Live/Delta.mp3" 660 5 "Delta Force" "Blue Cats" "Live at Test"
mk "No Tags.mp3" 392 4 "" "" ""
ffmpeg -loglevel error -y -f lavfi -i sine=frequency=300:duration=3 -map_metadata -1 -b:a 64k Notags2.mp3
head -c 3000 "Rock/01 Alpha.mp3" > Corrupt.mp3; echo "not an mp3" > Garbage.mp3; : > Empty.mp3
echo "created $(find . -name '*.mp3' | wc -l) files in $R"
