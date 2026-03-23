# Omnivious Voice Studio

Local-first voice persona studio for Apple Silicon. Train a reusable persona from an upload or YouTube source, certify it, and generate expressive speech with a dual-engine MLX Chatterbox pipeline.

## What It Does
- Train personas from local audio files or YouTube URLs.
- Certify personas before generation is allowed.
- Render previews with `mlx-community/chatterbox-turbo-fp16`.
- Render finals with `mlx-community/chatterbox-fp16`.
- Generate long-form output segment-by-segment with stitching and crossfades.
- Keep generation history with playback, deletion, and retention cleanup.

## Project Layout
- `apps/api` - FastAPI backend
- `apps/web` - Next.js frontend
- `data` - local runtime state for SQLite, persona assets, generated audio, and model caches
- `docs` - product and technical notes
- `reports` - benchmarking and evaluation notes
- `scripts` - smoke tests and benchmarking utilities

## Prerequisites
- macOS on Apple Silicon
- Python 3.10+
- Node.js 20+
- `ffmpeg`
- `yt-dlp`

## Environment
Copy `.env.example` to a local `.env` file if you want to override defaults.

Important notes:
- `.env.example` is the only environment file that belongs in version control.
- `data/` is local runtime state and is intentionally not committed.
- `apps/api/uv.lock` is kept to preserve a reproducible backend dependency snapshot for `uv` users, but the documented install path below uses `pip`.

## Backend Setup
```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload --port 8001
```

Optional `uv` workflow:
```bash
cd apps/api
uv sync --frozen --extra dev
uv run uvicorn app.main:app --reload --port 8001
```

## Frontend Setup
```bash
npm ci
npm run dev:web
```

Open [http://localhost:3000](http://localhost:3000).

## Verification
Backend tests:
```bash
python -m pytest apps/api/tests -q
```

Frontend production build:
```bash
npm run build:web
```

V3 smoke check:
```bash
python scripts/smoke_v3_recovery.py
```

## API Endpoints
- `GET /api/health`
- `POST /api/personas`
- `GET /api/personas`
- `GET /api/personas/{id}`
- `PATCH /api/personas/{id}`
- `DELETE /api/personas/{id}`
- `POST /api/personas/{id}/retrain`
- `POST /api/personas/{id}/recertify`
- `GET /api/jobs/{id}`
- `POST /api/generate`
- `GET /api/generations`
- `GET /api/generations/{id}`
- `DELETE /api/generations/{id}`

## Runtime Data
The application creates and manages local state under `data/`:
- `data/omnivious.db`
- `data/jobs/`
- `data/models/`
- `data/outputs/`
- `data/personas/`

Those paths are runtime artifacts, not source files. The repository keeps only placeholder directories so a fresh clone has the expected structure without leaking local audio, embeddings, or generated outputs.

## Publishing Notes
- User-facing branding is `Omnivious Voice Studio`.
- Internal package identifiers remain `omnivious-*`.
- This repository ships under the MIT license.

