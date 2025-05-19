# yt-dlp version
auto download yt-dlp if not installed

# tiktok-downloader-bot
A Telegram bot to download videos or images from tiktok without watermark.
Bot translated into these languagess: ru, en, cn, hi, es, fr, ar, pt, id, pl, cs, de, it, tr, he, uk

## Configure and launch bot
  - `sudo apt update`
  - `sudo apt install python3.10 python3.10-venv python3.10-dev -y`
  - `git clone https://github.com/Justieku/tiktok-downloader-bot_justieku`
  - `python3.10 -m venv tiktok-downloader-bot`
  - `cd tiktok-downloader-bot && source bin/activate`
  - Edit settings.py - add your `API_TOKEN` from @BotFather
  - `pip install -r requirements.txt`
  - `python3 tt_download_bot.py`

## Features
### Inline mode
  In inline mode you can pick one(statisctic, music or video)

### Default mode
  Just send link of tiktok video or image to get video or media group of images
  
