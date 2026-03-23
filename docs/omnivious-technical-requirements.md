# Omnivious Voice Studio Technical Requirements

This document is a lighter, earlier-style technical framing for Omnivious Voice Studio. For the main engineering reference, use [omnivious-trd.md](omnivious-trd.md).

## Summary

Omnivious Voice Studio is a local-first voice persona platform that lets a user:
- train a reusable voice persona from an upload or YouTube source
- generate expressive speech with style controls
- preserve speaker identity while layering emotion and delivery changes
- manage generated assets without leaving the app

In plain terms: same voice, many moods, minimal operational pain.

## Scope

### In Scope
- persona training from local upload or YouTube
- source consumption capped to 5 minutes
- reference audio normalization
- anchor and conditioning extraction
- speaker embedding persistence
- style-driven TTS generation
- generation history and playback
- local single-machine deployment on Apple Silicon

### Out of Scope
- distributed workers
- multi-user auth
- cloud object storage
- fine-tuning model weights
- enterprise collaboration features

## Functional Requirements

### Persona Creation
The system shall:
1. Accept `persona_name` and `source_type`.
2. Normalize audio to mono WAV.
3. Limit source consumption to a bounded duration.
4. Persist progress and persona metadata.

### Persona Lifecycle
The system shall:
1. List personas.
2. Rename personas.
3. Retrain personas.
4. Recertify personas where needed.
5. Delete personas and associated assets.

### Generation
The system shall:
1. Accept persona, text, style, speed, and render mode.
2. Compile style-aware text for safe rendering.
3. Render speech locally.
4. Persist output metadata and artifacts.
5. Surface warnings and advisories.

## High-Level Architecture

```mermaid
flowchart TD
    web["Next Web App"] --> api["FastAPI API"]
    api --> jobs["Job Manager"]
    api --> db["SQLite"]
    api --> data["Local Data"]
    jobs --> persona["Persona Service"]
    jobs --> style["Style Compiler"]
    jobs --> tts["TTS Service"]
    jobs --> identity["Identity Scorer"]
    tts --> preview["Preview Engine"]
    tts --> final["Final Engine"]
    persona --> data
    tts --> data
```

## Core Technical Choices

### Next.js Frontend
Why:
- simple local UI surface
- works well for polling-driven workflows
- easy to extend

### FastAPI Backend
Why:
- explicit API contracts
- good fit for orchestration-heavy local apps
- straightforward file and form handling

### SQLite
Why:
- zero-service local persistence
- easy setup for a single-user local-first product

### MLX-Based Rendering
Why:
- strong Apple Silicon story
- local inference without cloud spend
- good fit for the product promise

### Certification Before Generation
Why:
- rejects weak personas before users waste generation time
- keeps the product honest about quality

## Orchestration Notes

The application flow is:
1. API records a persona or generation request.
2. A job is created and tracked.
3. Backend services perform ingest, certification, or rendering.
4. Metadata is written to SQLite.
5. Artifacts are written to local storage.
6. The frontend polls for progress and updates the UI.

## Data and Artifacts

Runtime state lives under `data/`:
- `omnivious.db`
- `personas/`
- `outputs/`
- `jobs/`
- `models/`

These are runtime artifacts and are intentionally not treated as source files.

## Related Docs

- [omnivious-trd.md](omnivious-trd.md)
- [omnivious-prd.md](omnivious-prd.md)
- [how-to-use-omnivious.md](how-to-use-omnivious.md)

