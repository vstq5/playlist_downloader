# Playlist Downloader

Open-source web app and API to search Spotify/YouTube playlists and download tracks.

## Features
*   **Universal Search**: Supports Spotify Playlists, Albums, Tracks, and YouTube links.
*   **No-Wait Downloads**: In-process background tasks with per-device limits.
*   **Smart Metadata**: Auto-fetches cover art, titles, and artists.
*   **Cloud Architecture**: Designed for containerized deployment (Stateless Backend).
*   **Security First**: Rate limiting, CORS protection, and secure env management.

## Tech Stack
*   **Frontend**: React, Vite, TailwindCSS (Hosted on Vercel).
*   **Backend**: Python, FastAPI, SpotDL, yt-dlp (Hosted on Render).
*   **Database**: PostgreSQL (Store tasks & history).
*   **Storage**: Ephemeral container filesystem storage.

## Project Structure
```
/
├── src/                # Backend Application Code
│   ├── playlist_downloader/
│   │   ├── server.py   # FastAPI Entrypoint
│   │   ├── database.py # SQLAlchemy Models
│   │   └── config.py   # Environment Settings
├── web/                # Frontend React Application
│   ├── src/            # React Components
│   └── vite.config.ts  # Build Config
├── Dockerfile          # Multi-stage build for Prod
├── docker-compose.yml  # Local Dev using Docker
└── render.yaml         # Render Deployment Config
```

## Quick Start (Local)

### Prerequisites
*   Node.js 18+
*   Python 3.11+
*   SpotDL / FFmpeg (installed in system PATH)

