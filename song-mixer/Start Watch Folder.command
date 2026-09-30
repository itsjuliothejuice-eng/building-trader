#!/bin/bash
cd "$(dirname "$0")"
INBOX="$HOME/Music/SongMixer/inbox"
echo "Drop Ableton stem folders or bounces into: $INBOX"
python3 -m songmixer watch "$INBOX" --genre pop
