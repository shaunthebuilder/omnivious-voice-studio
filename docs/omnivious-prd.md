# Omnivious Voice Studio PRD

## Document Intent
This product requirements document describes what Omnivious Voice Studio is, who it is for, which problems it solves, how the experience is structured, and why the current feature set exists in its present form.

It is written for:
- product managers
- founders and operators
- design collaborators
- engineers who want the product context behind the implementation
- open source contributors evaluating the direction of the project

---

## 1. Product Overview

### 1.1 One-line Summary
Omnivious Voice Studio is a local-first, open source voice persona studio that lets a user train a reusable voice persona from an upload or YouTube source, certify that persona, and generate expressive speech in multiple styles with zero recurring API or token cost.

### 1.2 Product Vision
The product aims to make high-agency voice creation feel like using a creative workstation instead of a black-box cloud service.

The intended experience is:
- local and private by default
- expressive rather than robotic
- operationally simple for a solo creator
- quality-aware instead of careless
- transparent enough for power users to understand what the system is doing

### 1.3 Product Thesis
Most voice-cloning products force users into one of two bad tradeoffs:
- convenience, but with cloud dependence, token costs, and weak control
- raw local power, but with fragmented tooling and poor UX

Omnivious Voice Studio is designed to close that gap. It combines:
- a guided training flow
- explicit certification before use
- dual-engine generation modes
- visible progress and warnings
- history and lifecycle management
- a completely local, open source runtime

The result is a system that can be credible as a daily creative tool, not just a demo.

---

## 2. Product Principles

### 2.1 Local First
All critical operations run on the user's machine:
- persona ingestion
- audio normalization
- voice conditioning
- certification
- generation
- storage
- cleanup

Benefits:
- zero recurring API/token cost
- no dependency on remote uptime
- stronger privacy posture
- easier offline or studio-only use
- better user trust for sensitive or proprietary material

### 2.2 Open Source by Default
The product is intended to be understandable, auditable, extensible, and forkable.

Benefits:
- contributors can inspect how identity and certification decisions are made
- teams can adapt the system to niche domains
- the community can add models, evaluators, and workflows over time
- users are not trapped in a hosted vendor dependency

### 2.3 Responsible AI Is Shared Responsibility
Because this product deals with synthetic voices and identity-like characteristics, it must be framed with explicit responsibility.

> Given the nature of the product, it is the user's responsibility to make use of it in a responsible way, because responsible AI is a universal need and responsibility.

The product must warn against:
- impersonation without consent
- fraud, deception, scams, or social engineering
- misuse of a person's likeness or recognizable voice
- copyright, publicity-right, privacy, labor, or consent violations
- illegal or abusive uses of synthetic media

The product should clearly communicate that:
- users must have the right to use the source voice material
- local execution does not remove legal obligations
- misuse of AI-generated media can have serious civil, contractual, employment, and criminal implications depending on jurisdiction and context

### 2.4 Quality Before Convenience
The system intentionally blocks generation for uncertified personas.

This is a product choice, not just a technical one.

Why:
- it prevents users from wasting time on obviously unstable personas
- it increases trust in the output library
- it protects the core promise of "same voice, many moods"
- it reduces the need for generation-time surprise failures

### 2.5 Creative Control Without Prompt Chaos
The system exposes a constrained set of expressive controls:
- a style choice
- a speed slider
- a render mode

This is deliberate.

Why:
- it keeps the experience understandable
- it reduces trial-and-error overhead
- it gives users meaningful control without turning the app into an advanced prompt-programming surface

---

## 3. Who This Product Is For

### 3.1 Primary Users
| User | Need | Why Omnivious Fits |
| --- | --- | --- |
| Solo creators | Need fast voice iteration without paying per render | Local inference and reusable personas remove recurring cost pressure |
| Indie studios | Need multiple expressive takes from one consistent voice | Style modes plus persona certification support repeatable workflows |
| Product builders | Need voice prototyping inside a local app stack | Open source and local runtime make integration easier |
| Researchers and hobbyists | Need transparent, modifiable pipelines | The full stack is inspectable and extensible |
| Educators and demo builders | Need explainable voice AI without cloud procurement | Local-first setup lowers organizational friction |

### 3.2 Secondary Users
| User | Use Case |
| --- | --- |
| Internal tooling teams | Build domain-specific voice utilities on top of the stack |
| Creative technologists | Experiment with style orchestration and evaluation loops |
| Accessibility and assistive-tech builders | Prototype custom voice personas with a local toolchain |

---

## 4. High-Value Use Cases

### 4.1 Creator Use Cases
- Produce short-form narration in multiple emotional styles from one trained persona
- Test different readings of the same script quickly
- Build recurring branded voices for content series
- Generate preview and final renders without leaving the app

### 4.2 Studio and Prototype Use Cases
- Explore character voice options before production lock
- Run local creative reviews without buying cloud credits
- Build quick internal demos for games, products, or educational content
- Create voice mockups for storyboards, animatics, or scripted demos

### 4.3 Open Source and Research Use Cases
- Benchmark local voice approaches
- Swap in other render engines
- experiment with alternative identity scorers
- compare certification thresholds
- inspect the tradeoffs between speed, style strength, and identity retention

### 4.4 Why These Use Cases Matter
The product's strongest value is not just "voice cloning." It is repeatable expressive voice iteration with clear state management:
- training is explicit
- certification is explicit
- generation is explicit
- history is persistent
- advisories are visible

This creates a tool that feels reliable enough to reuse.

---

## 5. Product Goals and Non-Goals

### 5.1 Goals
- Deliver a polished local voice persona workflow
- Preserve voice identity while adding expressive range
- Eliminate recurring API/token spend
- Give users transparent progress and diagnostics
- Keep the system open source and extensible
- Make failure states understandable, not mysterious

### 5.2 Non-Goals
- Multi-tenant SaaS hosting
- cloud-first orchestration
- user auth and permissions
- enterprise admin tooling
- fine-tuning model weights in product v1
- arbitrary free-form prosody programming UI
- distributed queue or cluster execution

---

## 6. End-to-End Experience

```mermaid
flowchart LR
    source["Source Audio"] --> train["Persona Training"]
    train --> prep["Normalization And Anchor Extraction"]
    prep --> certify["Certification Suite"]
    certify --> ready["Certified Persona Ready"]
    certify --> blocked["Persona Blocked"]
    ready --> studio["Generation Studio"]
    studio --> plan["Segment Planning And Style Compilation"]
    plan --> render["Preview Or Final Rendering"]
    render --> advisory["Identity Advisory Check"]
    advisory --> library["Generated Voices Library"]
```

This flow matters product-wise because it creates a strong mental model:
- first create a persona
- then certify it
- then render with confidence
- then manage outputs over time

---

## 7. Functional Feature Set

## 7.1 Persona Training

### User Problem
Users need a way to turn raw source material into a reusable voice persona without doing manual preprocessing, anchor selection, or technical setup.

### User Benefit
The app converts messy source input into a structured reusable asset with certification and render metadata.

### UI Elements
- `Persona Name` text input
- `Source Type` dropdown with:
  - `Local Upload`
  - `YouTube Link`
- `Training Audio` file picker
- `YouTube URL` text input
- `Train + Certify Persona (max 5 mins)` primary CTA
- training progress bar
- live phase label and status text

### Functional Behavior
- accepts persona name and source type
- supports upload or YouTube URL input
- caps source consumption to 5 minutes
- normalizes input audio
- extracts conditioning material and anchor candidates
- runs certification immediately as part of training
- either marks the persona ready or rejects it before generation

### Product Rationale
- combining training and certification reduces "false ready" states
- source-type choice supports both creator-owned files and reference discovery workflows
- a 5-minute cap protects runtime and prevents accidental over-processing
- visible progress reduces anxiety during slow local ML operations

---

## 7.2 Persona Manager

### User Problem
Once personas exist, users need lifecycle controls for maintaining a clean, trustworthy workspace.

### User Benefit
The user can manage personas as durable creative assets rather than temporary one-off jobs.

### UI Elements
- persona cards
- certification status tag
- source metadata line
- conditioning/profile metadata line
- per-persona progress bar
- action buttons:
  - `Select`
  - `Rename`
  - `Retrain`
  - `Recertify` when needed
  - `Delete`
- inline rename controls
- inline retrain controls

### Functional Behavior
- lists all personas
- shows certification state and training progress
- allows re-selection for generation
- supports rename
- supports retrain from upload or YouTube
- supports recertification for rejected or legacy personas
- supports deletion and asset cleanup

### Product Rationale
- persona cards keep the working set visible and comparable
- certification state is prominent because it directly determines generation eligibility
- retrain and recertify are separate ideas:
  - retrain changes source material
  - recertify re-validates an existing persona path
- deletion matters because local-first apps need storage discipline

---

## 7.3 Style Controls and Generation Studio

### User Problem
Users want expressive range without losing identity, and they need a small number of high-confidence controls rather than a sprawling parameter matrix.

### User Benefit
The studio turns one certified persona into many usable readings while keeping the decision surface compact.

### UI Elements
- `Input Text` textarea
- style cards:
  - `Natural`
  - `News`
  - `Drama`
  - `Sad`
  - `Happy`
  - `Charming`
- style description line
- `Speed` slider from `0.7x` to `1.3x`
- `Render Mode` dropdown:
  - `Final (full Chatterbox)`
  - `Preview (turbo)`
- generation summary box
- `Generate Audio` CTA
- generation progress bar
- latest output panel with diagnostics and player

### Functional Behavior
- requires a certified selected persona
- accepts script text
- applies style-specific shaping
- supports preview and final rendering
- supports bounded speed control
- tracks progress through queue, planning, rendering, and stitching
- returns latest output with engine metadata, warning codes, tags, identity score, and playback

### Product Rationale
- the six styles are expressive enough to feel creatively useful without being cognitively noisy
- preview vs final mode supports fast iteration and higher-fidelity completion in one product
- the speed slider offers meaningful control while staying safe and bounded
- the summary strip reduces accidental renders with the wrong persona or mode
- the latest output area closes the loop immediately after generation

---

## 7.4 Style Model and User Choice Architecture

| Style | Product Intent | User Benefit |
| --- | --- | --- |
| Natural | Closest to base voice | Best for safe, utility-first reads |
| News | Controlled, confident delivery | Useful for announcer and formal reads |
| Drama | High-contrast cinematic intensity | Useful for trailers, scenes, and emotional moments |
| Sad | Fragile, grief-adjacent performance | Useful for storytelling and emotional testing |
| Happy | Bright, bubbly delivery | Useful for social, consumer, and playful content |
| Charming | Teasing, intimate energy | Useful for character and persona exploration |

The style system is valuable because it is opinionated. The user does not need to invent a style vocabulary from scratch.

---

## 7.5 Render Mode Choice

| Mode | Product Meaning | Why It Exists |
| --- | --- | --- |
| Preview | Faster turbo path | Lets users iterate cheaply in time, not money |
| Final | Higher-fidelity full path | Gives a more polished output when the user is ready |

This dual-engine model is a major product advantage:
- it shortens iteration loops
- it keeps the workflow local
- it gives users a tangible quality/speed tradeoff without exposing engine internals

---

## 7.6 Generated Voices Library

### User Problem
Users need persistent access to their outputs, not just a last-render scratchpad.

### User Benefit
Generated clips become part of a working library that can be reviewed, compared, replayed, and cleaned up.

### UI Elements
- generation cards
- persona name
- timestamp
- duration
- style label
- engine and fallback metadata
- warning/advisory line when relevant
- audio player
- `Delete` action

### Functional Behavior
- lists generated renders
- shows creation time and duration
- shows style and render metadata
- shows warnings and applied tags when relevant
- provides playback for each clip
- supports per-clip deletion
- supports automatic retention cleanup in the backend

### Product Rationale
- a generation history turns the app into a reusable studio, not a transient render form
- local output management matters because storage is finite in local-first products
- transparent diagnostics help users decide which take to keep

---

## 7.7 Certification and Evaluation as Product Features

This product treats evaluation as part of the experience, not just an internal engineering mechanism.

### Certification
Certification verifies whether a trained persona is production-worthy before the user reaches generation.

Product value:
- reduces user disappointment
- makes persona state legible
- turns quality into a first-class product concept

### Advisory Identity Checks
Post-generation identity scoring is retained as an advisory layer.

Product value:
- keeps useful renders even when quality drift is non-zero
- surfaces diagnostics without making the product frustratingly brittle
- balances creative freedom with quality awareness

### Warning Codes and Attempts
The product stores:
- warning codes
- retry/fallback history
- segment metadata
- tag usage

Product value:
- helps users understand why a render looks the way it does
- supports future analytics and contributor debugging
- makes the system more trustworthy than a black box

---

## 8. Orchestration and Product Management Considerations

## 8.1 Why Orchestration Matters Here
This product is not a single-model call. It is an orchestrated local workflow:
- source ingest
- normalization
- persona preparation
- certification
- job queueing
- segment planning
- synthesis
- stitching
- identity advisory scoring
- cleanup and retention

From a PM perspective, orchestration matters because user trust depends on state coherence.

The product must always answer:
- What is happening?
- Is this persona actually usable?
- Why was this output accepted or warned?
- What should the user do next?

## 8.2 Product-State Clarity
The app explicitly models:
- persona training state
- certification state
- generation job state
- generation quality state

This is a strong PM choice because local ML workloads are slower and noisier than standard CRUD operations. Visibility is part of the product.

## 8.3 Evals and Product Readiness
The system already includes meaningful evaluation concepts:
- certification similarity thresholds
- operational success ratio thresholds
- advisory identity warnings
- smoke checks
- benchmark utilities and reports

These matter because a voice product without evals quickly becomes anecdotal and fragile.

---

## 9. High-Level Technical Overview

At a high level, the product consists of:
- a Next.js frontend for workflow orchestration and playback
- a FastAPI backend for training, certification, and generation APIs
- SQLite for durable metadata
- local filesystem storage for personas, outputs, and runtime artifacts
- local ML inference through MLX-compatible models
- local job execution inside the backend process

This architecture supports the core product promise:
- open source
- local first
- zero recurring API/token cost
- inspectable end-to-end behavior

---

## 10. User Problems Solved

| User Problem | Product Response | User Benefit |
| --- | --- | --- |
| "I want a reusable local voice persona." | Persona training + certification | Reliable reusable assets |
| "I do not want to pay per generation." | Local inference | Zero recurring API/token cost |
| "I need different emotional reads from one voice." | Six style modes + speed + dual render modes | Fast creative iteration |
| "I need to know whether a persona is good enough." | Certification gate + visible status | Less wasted time |
| "I need to compare and manage outputs." | Generated voices library | Better workflow continuity |
| "I need a system I can trust and modify." | Open source local stack | Transparency and extensibility |

---

## 11. Success Criteria

### Product Success Signals
- users can complete training and render flows without external services
- certified personas consistently feel usable in the generation UI
- preview mode shortens iteration loops
- output history improves repeat usage
- warnings are understandable instead of alarming

### Quality Signals
- certification rejects weak personas before generation
- renders preserve recognizable identity often enough to feel trustworthy
- fallbacks recover useful outputs instead of creating dead ends
- local setup remains stable on the intended Apple Silicon target

### Community Signals
- contributors can understand the architecture
- docs make local setup and extension approachable
- the repo feels publishable, coherent, and forkable

---

## 12. Risks and Mitigations

| Risk | Why It Matters | Mitigation |
| --- | --- | --- |
| Misuse for impersonation or deception | Legal and ethical harm | Explicit responsible-AI language and local-user accountability warnings |
| Poor source audio | Weak clones and user disappointment | Certification gate and actionable rejection messaging |
| Slow local inference | Perceived product sluggishness | Visible progress, preview mode, and job states |
| Quality drift under heavy style | Loss of trust in persona identity | Style defaults, certification, advisory identity checks, and fallback paths |
| Hardware specificity | Limits who can run it easily | Explicit Apple Silicon positioning and local setup docs |

---

## 13. Responsible AI, Consent, and Legal Use

This product must be presented with unambiguous responsibility guidance.

### Core Statement
Users are responsible for using Omnivious Voice Studio lawfully, ethically, and with appropriate consent.

### The Product Must Warn Against
- cloning or simulating a voice without permission
- impersonation of real people
- misleading or fraudulent uses of synthetic media
- harassment, abuse, or reputational harm
- using content in violation of copyright, labor obligations, terms of service, or publicity/privacy rights

### Why This Matters
The product is powerful precisely because it lowers the cost and friction of voice synthesis. That makes responsible use more important, not less.

Local-first architecture is a privacy and autonomy feature. It is not a license to ignore ethics, consent, or the law.

---

## 14. Product Direction and Extensibility

The current product is a strong foundation for future work such as:
- additional local render backends
- richer certification reports
- multi-persona comparison workflows
- more granular style presets
- export flows and batch jobs
- contributor-added evaluation plugins
- optional self-hosted collaborative modes without losing local-first roots

The key is that the system already has the right product primitives:
- personas
- certification
- jobs
- generations
- diagnostics
- local storage

That makes the roadmap additive rather than a rewrite.

---

## 15. Final Product Positioning

Omnivious Voice Studio is not just "another voice cloning app."

It is:
- a local-first creative workstation
- a zero recurring API/token cost voice tool
- an open source orchestration system
- a product that treats evaluation and responsibility as first-class concerns

Its product strength comes from combining expressive generation with explicit certification, visible state, and durable local asset management.
