# How To Use Omnivious Voice Studio

This guide walks a new user through installing, launching, and using Omnivious Voice Studio for the first time.

Omnivious Voice Studio is:
- local first
- open source
- designed for Apple Silicon Macs
- built to run without recurring API or token costs

---

## 1. What You Need Before You Start

### Supported Environment
Omnivious Voice Studio is currently intended for:
- macOS
- Apple Silicon (`M1`, `M2`, `M3`, or newer)
- Python `3.10+`
- Node.js `20+`

### Required Tools
Install these first:
- `ffmpeg`
- `yt-dlp`

If you use Homebrew, you can install them with:

```bash
brew install ffmpeg yt-dlp
```

### Recommended Hardware Notes
This app runs locally and performs real ML workloads on your machine. For the smoothest experience:
- use an Apple Silicon Mac
- keep a reasonable amount of free disk space
- expect first-time model setup to take longer than repeat runs

---

## 2. Get the Code

Clone the repository:

```bash
git clone <YOUR_REPO_URL>
cd Omnivious
```

If your folder name is different, just `cd` into the cloned project directory.

---

## 3. Check the Project Structure

You should see these important folders:
- `apps/api` - backend
- `apps/web` - frontend
- `data` - local runtime files created by the app
- `docs` - documentation

The `data/` directory is local runtime state. It is where the app stores:
- the SQLite database
- persona assets
- generated audio
- local model/runtime artifacts

---

## 4. Set Up the Environment

The repository includes an example environment file:

```bash
cp .env.example .env
```

For most first-time local runs, the defaults are fine.

Important notes:
- `.env.example` is the template
- `.env` is your local override file
- you do not need any cloud API keys to run the app

### Default Local URLs
By default:
- frontend runs on `http://localhost:3000`
- backend runs on `http://localhost:8001`

---

## 5. Install and Run the Backend

Open a terminal in the project root and run:

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload --port 8001
```

What this does:
- creates a Python virtual environment
- installs backend dependencies
- starts the API server on port `8001`

Leave this terminal running.

### Optional `uv` Workflow
If you prefer `uv`, you can use:

```bash
cd apps/api
uv sync --frozen --extra dev
uv run uvicorn app.main:app --reload --port 8001
```

---

## 6. Install and Run the Frontend

Open a second terminal in the project root and run:

```bash
npm ci
npm run dev:web
```

Then open:

[http://localhost:3000](http://localhost:3000)

Leave this terminal running too.

---

## 7. Confirm the App Is Running

When everything is working:
- the backend terminal should show Uvicorn running on port `8001`
- the frontend terminal should show the Next.js dev server
- the browser should load the Omnivious Voice Studio interface

At the top of the app you should see:
- the product title
- a short summary of certified persona cloning and dual-engine MLX rendering

---

## 8. Understand the Main Areas of the App

The UI is organized into four sections:

### 1) Persona Training
Use this to:
- name a persona
- choose a source type
- upload training media or paste a YouTube URL
- start training and certification

### 2) Persona Manager
Use this to:
- view all personas
- see certification status
- select a persona
- rename a persona
- retrain a persona
- recertify a persona when needed
- delete a persona

### 3) Style Controls + Generation
Use this to:
- enter text
- choose a style
- adjust speed
- choose preview or final render mode
- generate audio

### 4) Generated Voices
Use this to:
- browse generated clips
- play outputs
- inspect warnings and tags
- delete old renders

---

## 9. Train Your First Persona

### Option A: Train from a Local File
In the `Persona Training` section:
1. Enter a persona name.
2. Set `Source Type` to `Local Upload`.
3. Choose an audio or video file.
4. Click `Train + Certify Persona (max 5 mins)`.

### Option B: Train from YouTube
In the `Persona Training` section:
1. Enter a persona name.
2. Set `Source Type` to `YouTube Link`.
3. Paste a YouTube URL.
4. Click `Train + Certify Persona (max 5 mins)`.

### What Happens During Training
The app will:
- fetch or receive the source audio
- normalize it
- trim the usable portion
- build conditioning and anchor assets
- run persona certification

### Why Certification Matters
A persona must pass certification before generation is allowed.

This protects you from spending time generating from a poor-quality persona that is unlikely to hold identity well.

### Expected Outcome
After training:
- a good persona will show `Certified`
- a weak persona may be `Rejected`

If rejected:
- try cleaner audio
- use a more isolated single-speaker source
- retrain with a better sample

---

## 10. Select and Manage a Persona

In `Persona Manager`, each persona card shows:
- its name
- certification status
- source type
- consumed training duration
- conditioning length
- profile version
- current training progress

Available actions include:
- `Select`
- `Rename`
- `Retrain`
- `Recertify` when applicable
- `Delete`

### Best Practice
Select a persona that is clearly marked `Certified` before trying to render speech.

---

## 11. Generate Your First Audio Clip

Go to `Style Controls + Generation`.

### Step-by-step
1. Make sure a certified persona is selected.
2. Enter text into the `Input Text` box.
3. Choose a style.
4. Adjust speed if needed.
5. Choose a render mode.
6. Click `Generate Audio`.

### Available Styles
The app currently includes:
- `Natural`
- `News`
- `Drama`
- `Sad`
- `Happy`
- `Charming`

Each style is opinionated and designed to give a different emotional or delivery profile.

### Speed Control
You can adjust speed from:
- `0.7x`
- up to `1.3x`

### Render Modes
Choose between:
- `Preview (turbo)` for faster iteration
- `Final (full Chatterbox)` for higher-fidelity output

### What Happens During Generation
The app will:
- validate that the persona is certified
- segment the text
- compile style-aware text for rendering
- render segments
- apply fallbacks if needed
- stitch the segments together
- apply speed transformation
- score identity advisories
- save the final audio

---

## 12. Review the Output

After generation, the `Latest Output` panel will show:
- style
- render mode
- engine used
- fallback engine if any
- segment count
- identity score
- duration
- warning codes
- applied tags
- an audio player

This gives you immediate feedback on both the creative result and the technical quality signals.

---

## 13. Browse and Manage Generated Voices

The `Generated Voices` section keeps a history of your renders.

Each generation card shows:
- generation id
- persona name
- timestamp
- duration
- style
- engine metadata
- fallback information
- advisories or warnings
- audio playback

You can delete any generation directly from this section.

---

## 14. Runtime Files and Where Things Are Stored

The app stores local runtime artifacts under `data/`:

- `data/omnivious.db` - local SQLite database
- `data/personas/` - persona reference audio, anchors, embeddings
- `data/outputs/` - generated WAV files
- `data/jobs/` - runtime job-related files if created
- `data/models/` - local model/runtime assets if created

This data stays on your machine unless you choose to move it.

---

## 15. Useful Verification Commands

### Run Backend Tests
From the project root:

```bash
python -m pytest apps/api/tests -q
```

### Build the Frontend for Production
From the project root:

```bash
npm run build:web
```

### Run the Smoke Script
From the project root:

```bash
python scripts/smoke_v3_recovery.py
```

---

## 16. Troubleshooting

### The frontend loads, but generation or persona actions fail
Check that the backend is running on `http://localhost:8001`.

### The backend fails to start
Check:
- Python version is `3.10+`
- you activated the virtual environment
- dependencies installed successfully
- `ffmpeg` is installed
- `yt-dlp` is installed

### A YouTube-based persona fails
Check:
- the URL is valid
- `yt-dlp` is installed and available in your shell
- the video is accessible

### A persona is rejected during certification
Usually this means the source audio was not stable enough for reliable cloning.

Try:
- cleaner single-speaker audio
- less background noise
- less overlap with music or other voices
- retraining with a better clip

### Generate button is disabled
That usually means:
- no persona is selected, or
- the selected persona is not certified yet

### First run feels slow
That is normal for a local ML app, especially when models are warming and assets are being created for the first time.

---

## 17. Responsible Use

Omnivious Voice Studio is a powerful local voice generation tool. Use it responsibly.

You are responsible for:
- obtaining the right to use the source audio
- using synthetic voice generation lawfully
- avoiding impersonation, fraud, or misleading content
- respecting privacy, consent, copyright, and publicity rights

Local execution does not remove your legal or ethical responsibilities.

Do not misuse AI-generated voice technology.

---

## 18. Quick Start Summary

If you want the shortest path:

1. Install `ffmpeg` and `yt-dlp`.
2. Clone the repo.
3. Copy `.env.example` to `.env`.
4. Start the backend:

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload --port 8001
```

5. Start the frontend in another terminal:

```bash
npm ci
npm run dev:web
```

6. Open [http://localhost:3000](http://localhost:3000)
7. Train and certify a persona
8. Select the persona
9. Enter text, choose a style, and generate audio

