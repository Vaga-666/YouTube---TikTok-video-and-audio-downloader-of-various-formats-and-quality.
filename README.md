# YouTube / TikTok Video & Audio Downloader

Web app to download video/audio from YouTube and TikTok by URL. Includes job/status flow API (FastAPI).

## Features
- Download video in different formats/quality
- Extract audio (mp3)
- Job-based processing with status endpoint
- Basic error handling and logs

## Tech Stack
Python • FastAPI • yt-dlp • Docker

## Run locally
```bash
cd project
python -m venv venv

# Windows:
venv\Scripts\activate

# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload

## Run with Docker
```bash
docker compose up --build

# Project structure

project/app/ — FastAPI backend

project/app/routes/ — API routes

project/app/services/ — downloader/converter logic

project/app/templates/ — HTML templates

project/static/ — static assets (css/js)

ops/ — deployment/ops configs

# Notes

Do not commit .env, cookies, tokens, or downloaded media files to the repo.

Some YouTube downloads may require cookies/auth depending on rate limits and bot checks.
