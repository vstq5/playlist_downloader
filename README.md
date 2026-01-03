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

### 1. Setup Environment
Copy the example environment file:
```bash
cp .env.example .env
```
Fill in your `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, and `SECRET_KEY`.

### 2. Run Backend
```bash
pip install -r requirements.txt
uvicorn src.playlist_downloader.server:app --reload --port 8000
```

### 3. Run Frontend
```bash
cd web
npm install
npm run dev
```
Open `http://localhost:5173`.

## Deployment

### Backend (Render)
1.  Push to GitHub.
2.  Login to [Render.com](https://render.com).
3.  New > **Blueprint** > Select Repo.
4.  Render will auto-deploy the Backend + Database using `render.yaml`.
5.  Set your Environment Variables in Dashboard.

### Frontend (Vercel)
1.  Login to [Vercel](https://vercel.com).
2.  New Project > Select Repo.
3.  **Root Directory**: `web`.
4.  Deploy!

## Security
This project follows strict security practices:
*   **Secrets**: Never commit `.env` files.
*   **CORS**: Configure `CORS_ORIGINS` in production to match your frontend domain.
*   **Rate Limits**: API is limited to 5 concurrent large requests per minute.

## License
MIT License.
