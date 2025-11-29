# youtube-tiktok-downloader.
Topics: python, fastapi, yt-dlp, downloader, api, async

Web app to download video/audio from YouTube and TikTok by URL. Includes job/status flow API (FastAPI).

## Features
- Download video in different formats/quality
- Extract audio (mp3)
- Job-based processing with status endpoint
- Basic error handling and logs

## Tech Stack
Python • FastAPI • yt-dlp • (add: Redis/Celery/Docker if you use)

## Run locally
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload
