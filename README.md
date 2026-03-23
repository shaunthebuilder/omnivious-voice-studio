# Omnivious Voice Studio

Omnivious Voice Studio is a local-first, open source voice persona app for Apple Silicon Macs. It lets you train a reusable voice persona from an upload or YouTube source, certify that persona, and generate expressive speech in multiple styles without recurring API or token costs.

This repo is both:
- a product: a usable local voice studio with training, certification, generation, and history
- a technical system: a Next.js + FastAPI + SQLite + MLX stack built for transparent local orchestration

## Product Overview

From a product standpoint, Omnivious Voice Studio is designed around a simple idea:

1. Bring in source audio.
2. Turn it into a reusable persona.
3. Certify that the persona is stable enough to use.
4. Generate expressive speech from that certified persona.
5. Keep a local history of outputs and manage them over time.

Key product behaviors:
- local upload or YouTube based persona training
- persona certification before generation is allowed
- expressive style controls instead of free-form prompt chaos
- preview and final render modes
- generated voice history with playback and deletion
- local storage of persona and output assets
- zero recurring inference cost because the system runs locally

## Technical Overview

From a technical standpoint, the app is a local orchestration stack:

- `apps/web` is the Next.js frontend
- `apps/api` is the FastAPI backend
- `data/` holds runtime state such as the SQLite database, persona files, and generated audio
- SQLite stores personas, jobs, and generation metadata
- MLX-backed TTS engines handle preview and final rendering
- the backend manages ingest, certification, generation, cleanup, and watchdog flows

High-level architecture:

```mermaid
flowchart TD
    web["Next Web App"] --> api["FastAPI API Layer"]
    api --> jobs["Job Manager"]
    api --> db["SQLite"]
    api --> files["Local Filesystem Data"]
    jobs --> ingest["Ingest And Normalization"]
    jobs --> persona["Persona Service"]
    jobs --> style["Style Compiler And Segment Planner"]
    jobs --> tts["TTS Service"]
    jobs --> identity["Identity Scorer"]
    tts --> preview["Preview Engine"]
    tts --> final["Final Engine"]
    persona --> files
    tts --> files
    identity --> files
```

## Core Features

- Train personas from local audio or YouTube
- Cap training source consumption to the first 5 minutes
- Normalize and prepare conditioning clips and anchors automatically
- Certify personas before generation is enabled
- Generate in multiple styles:
  - `Natural`
  - `News`
  - `Drama`
  - `Sad`
  - `Happy`
  - `Charming`
- Render in two modes:
  - `Preview` using `mlx-community/chatterbox-turbo-fp16`
  - `Final` using `mlx-community/chatterbox-fp16`
- Generate long-form output segment-by-segment with stitching and crossfades
- Keep local output history with diagnostics, warnings, and playback

## Why This Repo Exists

This project is intentionally:
- local first
- open source
- inspectable
- modifiable
- free from recurring cloud inference spend

It is meant for:
- creators
- indie teams
- researchers
- open source contributors
- builders who want a voice persona workflow they can run and understand themselves

## Documentation Map

Start here, then use the docs below depending on what you need:

- [Installation and first-use guide](docs/how-to-use-omnivious.md)
- [Documentation index](docs/README.md)
- [Product Requirements Document](docs/omnivious-prd.md)
- [Technical Requirements Document](docs/omnivious-trd.md)
- [Earlier technical framing](docs/omnivious-technical-requirements.md)
- [Non-technical product overview](docs/omnivious-nontechnical-fun-edition.md)

Recommended reading order:
- New user: [how-to-use-omnivious.md](docs/how-to-use-omnivious.md)
- Product/design context: [omnivious-prd.md](docs/omnivious-prd.md)
- Engineering context: [omnivious-trd.md](docs/omnivious-trd.md)

## Repository Layout

- `apps/api` - FastAPI backend
- `apps/web` - Next.js frontend
- `data` - local runtime state created by the app
- `docs` - product, technical, and user documentation
- `reports` - evaluation and benchmark notes
- `scripts` - smoke tests and benchmarking helpers
- `benchmarks` - benchmark config inputs

## System Requirements

### Supported Platform
- macOS
- Apple Silicon (`M1`, `M2`, `M3`, or newer)

### Required Software
- Python `3.10+`
- Node.js `20+`
- `ffmpeg`
- `yt-dlp`

### Install Required Tools
If you use Homebrew:

```bash
brew install ffmpeg yt-dlp
```

## Installation

### 1. Clone the repository

```bash
git clone <YOUR_REPO_URL>
cd Omnivious
```

### 2. Create your local environment file

```bash
cp .env.example .env
```

For most local setups, the defaults in `.env.example` are enough.

Important notes:
- `.env.example` is the only environment file that belongs in version control
- `.env` is your local override file
- no cloud API keys are required for the standard local flow

### 3. Start the backend

Open a terminal in the repo root:

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload --port 8001
```

This will:
- create a virtual environment
- install backend dependencies
- start the API on `http://localhost:8001`

Leave this terminal open.

### 4. Start the frontend

Open a second terminal in the repo root:

```bash
npm ci
npm run dev:web
```

Then open:

[http://localhost:3000](http://localhost:3000)

Leave this terminal open too.

### 5. Confirm the app is running

You should now have:
- backend running on `http://localhost:8001`
- frontend running on `http://localhost:3000`
- the Omnivious Voice Studio UI visible in your browser

## Optional `uv` Backend Workflow

If you prefer `uv`:

```bash
cd apps/api
uv sync --frozen --extra dev
uv run uvicorn app.main:app --reload --port 8001
```

The repo keeps [`apps/api/uv.lock`](apps/api/uv.lock) for reproducible dependency pinning in that workflow.

## How To Use The App

### Train a persona
In the UI:
- enter a persona name
- choose `Local Upload` or `YouTube Link`
- provide a file or URL
- click `Train + Certify Persona`

The backend will:
- ingest the source
- normalize and trim it
- build conditioning and anchor assets
- run certification

Only certified personas can be used for generation.

### Generate audio
After a persona is certified:
- select the persona in Persona Manager
- enter text
- choose a style
- adjust speed if needed
- choose preview or final render mode
- click `Generate Audio`

### Review outputs
The app stores generated clips locally and shows them in the generated voices library with:
- persona name
- render mode
- duration
- warnings and advisories
- playback

For a more detailed walkthrough, see [docs/how-to-use-omnivious.md](docs/how-to-use-omnivious.md).

## Verification Commands

### Run backend tests

```bash
python -m pytest apps/api/tests -q
```

### Build the frontend for production

```bash
npm run build:web
```

### Run the smoke script

```bash
python scripts/smoke_v3_recovery.py
```

## Runtime Data

The app writes local runtime state under `data/`:

- `data/omnivious.db`
- `data/jobs/`
- `data/models/`
- `data/outputs/`
- `data/personas/`

These are runtime artifacts, not source files.

What that means:
- generated audio is stored locally
- persona audio, anchors, and embeddings are stored locally
- your local runtime state is intentionally not committed to the repo

## API Overview

Primary API routes:
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

The API contracts and design rationale are described in [docs/omnivious-trd.md](docs/omnivious-trd.md).

## Responsible Use and Legal Notice

Omnivious Voice Studio is a powerful synthetic voice system. You are responsible for how you use it.

You must use this software lawfully, ethically, and with appropriate consent.

Do not use it for:
- impersonation without permission
- fraud or deception
- scams or social engineering
- harassment or abuse
- misleading synthetic media
- violating copyright, privacy, publicity, employment, labor, or platform rights

Important principles:
- you are responsible for obtaining the right to use source audio
- local execution does not remove your legal obligations
- responsible AI is a universal responsibility, not a vendor-only responsibility
- misuse of AI-generated voices may create serious civil, contractual, employment, regulatory, or criminal consequences depending on jurisdiction and context

If you are unsure whether a use case is lawful or ethical, do not proceed until you have clarified consent, ownership, and applicable legal boundaries.

## Safety and Product Positioning

The app intentionally includes product choices that encourage more responsible operation:
- persona certification before generation
- explicit warnings and advisories
- visible job and quality state
- local storage rather than silent cloud processing

These choices help users understand what the system is doing, but they do not replace user judgment or legal compliance.

## License

This repository is licensed under the [MIT License](LICENSE).

## Related Docs

- [User guide](docs/how-to-use-omnivious.md)
- [Docs index](docs/README.md)
- [PRD](docs/omnivious-prd.md)
- [TRD](docs/omnivious-trd.md)
