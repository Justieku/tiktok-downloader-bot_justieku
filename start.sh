#!/bin/bash

if ! command -v tmux &> /dev/null; then
    sudo apt update && sudo apt install -y tmux
fi

tmux new -s tt "python3 tt_download_bot.py"
