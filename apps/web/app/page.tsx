"use client";

import { useEffect, useMemo, useState } from "react";
import {
  createPersonaFromUpload,
  createPersonaFromYoutube,
  deleteGeneration,
  deletePersona,
  fetchGeneration,
  fetchGenerations,
  fetchJob,
  fetchPersonas,
  generateSpeech,
  mediaUrl,
  recertifyPersona,
  renamePersona,
  retrainPersonaFromUpload,
  retrainPersonaFromYoutube,
} from "../lib/api";
import type { Generation, GenerationStyle, Job, Persona, RenderMode } from "../lib/types";

const STYLE_OPTIONS: Array<{ id: GenerationStyle; label: string; description: string }> = [
  { id: "natural", label: "Natural", description: "Closest to the trained base voice, punctuation-first." },
  { id: "news", label: "News", description: "Dominant, politician-anchor confidence and control." },
  { id: "drama_movie", label: "Drama", description: "Hyper-cinematic contrast with whispers, peaks, and pressure." },
  { id: "sad", label: "Sad", description: "Breaking, grief-heavy, crying-adjacent delivery." },
  { id: "happy", label: "Happy", description: "Bubbly, elevated, playful, and giggly." },
  { id: "charming_attractive", label: "Charming", description: "Slow, teasing, sensual, and magnetically playful." },
];

function toPercent(progress: number | null): number {
  if (progress == null || Number.isNaN(progress)) return 0;
  return Math.max(0, Math.min(100, Math.round(progress * 100)));
}

function formatSeconds(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "n/a";
  return `${Math.round(value)}s`;
}

function styleLabel(style: string | null | undefined): string {
  if (!style) return "Natural";
  const option = STYLE_OPTIONS.find((item) => item.id === style);
  return option?.label ?? "Natural";
}

function trainingPhase(progress: number, status: Job["status"]): string {
  if (status === "failed") return "Training failed";
  if (status === "completed") return "Training completed";
  if (progress < 0.18) return "Queued";
  if (progress < 0.42) return "Fetching source audio";
  if (progress < 0.58) return "Normalizing to studio reference";
  if (progress < 0.72) return "Extracting conditioning and anchors";
  if (progress < 0.9) return "Certification renders";
  return "Finalizing persona profile";
}

function generationPhase(progress: number, status: Job["status"]): string {
  if (status === "failed") return "Generation failed";
  if (status === "completed") return "Generation completed";
  if (progress < 0.12) return "Queued";
  if (progress < 0.28) return "Planning humane speech beats";
  if (progress < 0.92) return "Rendering speech segments";
  return "Stitching final audio";
}

function userFacingError(err: unknown, fallback: string): string {
  const raw = err instanceof Error ? err.message : fallback;
  const line = raw
    .split("\n")
    .map((entry) => entry.trim())
    .find((entry) => entry.length > 0 && !entry.startsWith("Traceback"));
  return line || fallback;
}

function certificationTone(persona: Persona): string {
  switch (persona.certification_status) {
    case "certified":
      return "Certified";
    case "uncertified_legacy":
      return "Legacy persona: needs recertification";
    case "rejected":
      return "Certification rejected";
    case "certifying":
      return "Certifying";
    default:
      return "Pending";
  }
}

function sourceLabel(sourceType: string): string {
  return sourceType === "youtube" ? "YouTube" : "Upload";
}

function prettyIssue(raw: string | null | undefined): string {
  if (!raw) return "";
  if (raw === "legacy_reference_certification_timeout") {
    return "Legacy reference stalled during certification. Retrain with a cleaner sample.";
  }
  return raw.replaceAll("_", " ");
}

function clampText(text: string, max = 140): string {
  const clean = text.trim();
  if (clean.length <= max) return clean;
  return `${clean.slice(0, max - 1).trimEnd()}...`;
}

export default function Page() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [selectedPersona, setSelectedPersona] = useState<number | null>(null);

  const [personaName, setPersonaName] = useState("");
  const [sourceType, setSourceType] = useState<"upload" | "youtube">("upload");
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [ingestStatus, setIngestStatus] = useState("Idle");
  const [trainingProgress, setTrainingProgress] = useState<number | null>(null);
  const [trainingPhaseLabel, setTrainingPhaseLabel] = useState("Queued");

  const [renamePersonaId, setRenamePersonaId] = useState<number | null>(null);
  const [renameDraft, setRenameDraft] = useState("");

  const [retrainPersonaId, setRetrainPersonaId] = useState<number | null>(null);
  const [retrainSourceType, setRetrainSourceType] = useState<"upload" | "youtube">("upload");
  const [retrainYoutubeUrl, setRetrainYoutubeUrl] = useState("");
  const [retrainUploadFile, setRetrainUploadFile] = useState<File | null>(null);

  const [text, setText] = useState("The storm has passed. Breathe in. Let your voice carry both relief and resolve.");
  const [style, setStyle] = useState<GenerationStyle>("natural");
  const [speed, setSpeed] = useState(1.0);
  const [renderMode, setRenderMode] = useState<RenderMode>("final");
  const [studioStatus, setStudioStatus] = useState("Ready");
  const [audioSrc, setAudioSrc] = useState<string | null>(null);
  const [lastGeneration, setLastGeneration] = useState<Generation | null>(null);
  const [generations, setGenerations] = useState<Generation[]>([]);
  const [generationProgress, setGenerationProgress] = useState<number | null>(null);
  const [generationPhaseLabel, setGenerationPhaseLabel] = useState("Idle");

  const selected = useMemo(
    () => personas.find((p) => p.id === selectedPersona) ?? null,
    [personas, selectedPersona],
  );
  const selectedStyleMeta = useMemo(
    () => STYLE_OPTIONS.find((option) => option.id === style) ?? STYLE_OPTIONS[0],
    [style],
  );

  async function loadPersonas() {
    try {
      const list = await fetchPersonas();
      setPersonas(list);
      setSelectedPersona((current) => {
        if (!list.length) return null;
        if (current && list.some((p) => p.id === current)) return current;
        const certified = list.find((p) => p.certification_status === "certified");
        return certified?.id ?? list[0].id;
      });
    } catch (err) {
      setIngestStatus(userFacingError(err, "Failed to fetch personas"));
    }
  }

  async function loadGenerations() {
    try {
      setGenerations(await fetchGenerations({ limit: 100 }));
    } catch (err) {
      setStudioStatus(userFacingError(err, "Failed to fetch generations"));
    }
  }

  useEffect(() => {
    void (async () => {
      await Promise.all([loadPersonas(), loadGenerations()]);
    })();
  }, []);

  function mergePersona(persona: Persona) {
    setPersonas((current) => [persona, ...current.filter((item) => item.id !== persona.id)]);
  }

  async function pollJob(
    jobId: number,
    onDone: (job: Job) => Promise<void>,
    onTick?: (job: Job) => void | Promise<void>,
  ) {
    for (;;) {
      const job = await fetchJob(jobId);
      if (onTick) await onTick(job);
      if (job.status === "completed") {
        await onDone(job);
        return;
      }
      if (job.status === "failed") {
        throw new Error(userFacingError(job.error, "Job failed"));
      }
      await new Promise((resolve) => setTimeout(resolve, 1200));
    }
  }

  async function runPersonaJob(
    payload: { persona: Persona; job_id: number },
    successMessage: string,
  ) {
    mergePersona(payload.persona);
    setSelectedPersona(payload.persona.id);
    await pollJob(
      payload.job_id,
      async () => {
        setTrainingProgress(1);
        setTrainingPhaseLabel("Training completed");
        await loadPersonas();
        setSelectedPersona(payload.persona.id);
        setIngestStatus(successMessage);
      },
      (job) => {
        const progress = job.progress ?? 0;
        const phase = trainingPhase(progress, job.status);
        setTrainingProgress(progress);
        setTrainingPhaseLabel(phase);
        setIngestStatus(`${phase} (${toPercent(progress)}%)`);
      },
    );
  }

  async function onCreatePersona() {
    try {
      const requestedName = personaName.trim();
      if (!requestedName) throw new Error("Persona name is required");
      setIngestStatus("Submitting persona training...");
      setTrainingProgress(0.05);
      setTrainingPhaseLabel("Queued");
      const payload =
        sourceType === "youtube"
          ? await createPersonaFromYoutube(requestedName, youtubeUrl.trim())
          : await createPersonaFromUpload(requestedName, uploadFile as File);
      await runPersonaJob(payload, `Persona "${payload.persona.name}" certified and ready.`);
    } catch (err) {
      setIngestStatus(userFacingError(err, "Persona creation failed"));
      setTrainingPhaseLabel("Training failed");
    }
  }

  async function onRetrainPersona(persona: Persona) {
    try {
      setTrainingProgress(0.05);
      setTrainingPhaseLabel("Queued");
      setIngestStatus(`Retraining "${persona.name}"...`);
      const payload =
        retrainSourceType === "youtube"
          ? await retrainPersonaFromYoutube(persona.id, retrainYoutubeUrl.trim())
          : await retrainPersonaFromUpload(persona.id, retrainUploadFile as File);
      await runPersonaJob(payload, `Persona "${persona.name}" retrained and recertified.`);
      setRetrainPersonaId(null);
      setRetrainUploadFile(null);
      setRetrainYoutubeUrl("");
    } catch (err) {
      setIngestStatus(userFacingError(err, "Retraining failed"));
      setTrainingPhaseLabel("Training failed");
    }
  }

  async function onRecertifyPersona(persona: Persona) {
    try {
      setTrainingProgress(0.56);
      setTrainingPhaseLabel("Certification queued");
      setIngestStatus(`Recertifying "${persona.name}"...`);
      const payload = await recertifyPersona(persona.id);
      await runPersonaJob(payload, `Persona "${persona.name}" recertified.`);
    } catch (err) {
      setIngestStatus(userFacingError(err, "Recertification failed"));
      setTrainingPhaseLabel("Training failed");
    }
  }

  async function onRenamePersona(persona: Persona) {
    try {
      const trimmed = renameDraft.trim();
      if (!trimmed) throw new Error("Name is required");
      const updated = await renamePersona(persona.id, trimmed);
      mergePersona(updated);
      setRenamePersonaId(null);
      setRenameDraft("");
    } catch (err) {
      setIngestStatus(userFacingError(err, "Rename failed"));
    }
  }

  async function onDeletePersona(persona: Persona) {
    try {
      await deletePersona(persona.id);
      setPersonas((current) => current.filter((item) => item.id !== persona.id));
      if (selectedPersona === persona.id) setSelectedPersona(null);
    } catch (err) {
      setIngestStatus(userFacingError(err, "Delete failed"));
    }
  }

  async function onGenerate() {
    try {
      if (!selectedPersona) throw new Error("Select a certified persona first");
      setStudioStatus("Submitting generation...");
      setGenerationProgress(0.05);
      setGenerationPhaseLabel("Queued");
      const payload = await generateSpeech({
        persona_id: selectedPersona,
        text,
        style,
        speed,
        render_mode: renderMode,
      });
      await pollJob(
        payload.job_id,
        async () => {
          const generation = await fetchGeneration(payload.generation_id);
          setLastGeneration(generation);
          setAudioSrc(mediaUrl(generation.audio_path));
          setGenerationProgress(1);
          setGenerationPhaseLabel("Generation completed");
          setStudioStatus(
            generation.quality_state === "warning"
              ? "Generation completed with advisories. Output kept."
              : `Generation completed using ${generation.engine_used ?? generation.engine}.`,
          );
          await loadGenerations();
        },
        (job) => {
          const progress = job.progress ?? 0;
          setGenerationProgress(progress);
          setGenerationPhaseLabel(generationPhase(progress, job.status));
          setStudioStatus(`${generationPhase(progress, job.status)} (${toPercent(progress)}%)`);
        },
      );
    } catch (err) {
      setStudioStatus(userFacingError(err, "Generation failed"));
      setGenerationPhaseLabel("Generation failed");
    }
  }

  async function onDeleteGeneration(generationId: number) {
    try {
      await deleteGeneration(generationId);
      setGenerations((current) => current.filter((item) => item.id !== generationId));
      if (lastGeneration?.id === generationId) {
        setLastGeneration(null);
        setAudioSrc(null);
      }
    } catch (err) {
      setStudioStatus(userFacingError(err, "Delete failed"));
    }
  }

  const selectedPersonaReady =
    !!selected?.ref_audio_path && selected?.certification_status === "certified" && selected.training_status !== "queued" && selected.training_status !== "running";

  return (
    <main className="page-shell">
      <section className="hero-panel">
        <h1>Omnivious Voice Studio</h1>
        <p>
          Certified persona cloning with dual-engine MLX rendering. Training either certifies the voice or rejects it up front;
          certified personas render with best-effort segment fallbacks instead of generation-time eval failures.
        </p>
      </section>

      <section className="grid two-up">
        <div className="panel">
          <h2>1) Persona Training</h2>
          <label>Persona Name</label>
          <input value={personaName} onChange={(e) => setPersonaName(e.target.value)} placeholder="Scar Test" />

          <div className="row split">
            <div>
              <label>Source Type</label>
              <select value={sourceType} onChange={(e) => setSourceType(e.target.value as "upload" | "youtube")}>
                <option value="upload">Local Upload</option>
                <option value="youtube">YouTube Link</option>
              </select>
            </div>
            <div key={sourceType === "upload" ? "upload-source-input" : "youtube-source-input"}>
              {sourceType === "youtube" ? (
                <>
                  <label>YouTube URL</label>
                  <input value={youtubeUrl ?? ""} onChange={(e) => setYoutubeUrl(e.target.value)} placeholder="https://www.youtube.com/watch?v=..." />
                </>
              ) : (
                <>
                  <label>Training Audio</label>
                  <input type="file" accept="audio/*,video/*" onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)} />
                </>
              )}
            </div>
          </div>

          <button onClick={onCreatePersona} disabled={sourceType === "upload" ? !uploadFile : !youtubeUrl.trim()}>
            Train + Certify Persona (max 5 mins)
          </button>

          {trainingProgress != null ? (
            <div className="progress-block">
              <label>Training Progress</label>
              <progress value={toPercent(trainingProgress)} max={100} />
              <p>{trainingPhaseLabel} ({toPercent(trainingProgress)}%)</p>
            </div>
          ) : null}
          <p>{ingestStatus}</p>
        </div>

        <div className="panel persona-manager-panel">
          <h2>2) Persona Manager</h2>
          <div className="persona-list">
            {personas.map((persona) => (
              <article className="persona-card" key={persona.id}>
                <div className="persona-header">
                  <h3>{persona.name}</h3>
                  <span className="tag">{certificationTone(persona)}</span>
                </div>
                <p className="meta-line">
                  {sourceLabel(persona.source_type)} • consumed {formatSeconds(persona.training_audio_seconds)} of {formatSeconds(persona.training_source_duration_seconds)}
                </p>
                <p className="meta-line">
                  conditioning {formatSeconds(
                    typeof persona.render_profile?.conditioning_seconds === "number" ? (persona.render_profile.conditioning_seconds as number) : null,
                  )} • profile v{persona.certified_profile_version}
                </p>
                <p className="meta-line">
                  {persona.certification_status === "certified" ? "Ready to render" : "Generation blocked until certification passes"}
                </p>
                {persona.certification_error ? <p className="issue-line">{prettyIssue(persona.certification_error)}</p> : null}
                <progress value={toPercent(persona.training_progress)} max={100} />

                <div className="persona-actions">
                  <button onClick={() => setSelectedPersona(persona.id)} disabled={selectedPersona === persona.id}>
                    {selectedPersona === persona.id ? "Selected" : "Select"}
                  </button>
                  <button onClick={() => { setRenamePersonaId(persona.id); setRenameDraft(persona.name); }}>Rename</button>
                  <button onClick={() => { setRetrainPersonaId(persona.id); setRetrainSourceType(persona.source_type === "youtube" ? "youtube" : "upload"); }}>Retrain</button>
                  {(persona.certification_status === "uncertified_legacy" || persona.certification_status === "rejected") ? (
                    <button onClick={() => void onRecertifyPersona(persona)}>Recertify</button>
                  ) : null}
                  <button onClick={() => void onDeletePersona(persona)}>Delete</button>
                </div>

                {renamePersonaId === persona.id ? (
                  <div className="row wrap gap">
                    <input value={renameDraft} onChange={(e) => setRenameDraft(e.target.value)} />
                    <button onClick={() => void onRenamePersona(persona)}>Save Name</button>
                    <button onClick={() => setRenamePersonaId(null)}>Cancel</button>
                  </div>
                ) : null}

                {retrainPersonaId === persona.id ? (
                  <div className="retrain-box">
                    <div className="row split">
                      <div>
                        <label>Retrain Source</label>
                        <select value={retrainSourceType} onChange={(e) => setRetrainSourceType(e.target.value as "upload" | "youtube")}>
                          <option value="upload">Local Upload</option>
                          <option value="youtube">YouTube Link</option>
                        </select>
                      </div>
                      <div>
                        {retrainSourceType === "youtube" ? (
                          <>
                            <label>YouTube URL</label>
                            <input value={retrainYoutubeUrl ?? ""} onChange={(e) => setRetrainYoutubeUrl(e.target.value)} placeholder="https://..." />
                          </>
                        ) : (
                          <>
                            <label>Audio File</label>
                            <input type="file" accept="audio/*,video/*" onChange={(e) => setRetrainUploadFile(e.target.files?.[0] ?? null)} />
                          </>
                        )}
                      </div>
                    </div>
                    <div className="row wrap gap">
                      <button onClick={() => void onRetrainPersona(persona)}>Start Retrain</button>
                      <button onClick={() => setRetrainPersonaId(null)}>Cancel</button>
                    </div>
                  </div>
                ) : null}
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="panel">
        <h2>3) Style Controls + Generation</h2>
        <label>Input Text</label>
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={8} />

        <label>Style</label>
        <div className="style-grid">
          {STYLE_OPTIONS.map((option) => (
            <button
              key={option.id}
              type="button"
              className={style === option.id ? "style-card selected" : "style-card"}
              onClick={() => setStyle(option.id)}
            >
              <strong>{option.label}</strong>
            </button>
          ))}
        </div>
        <p className="meta-line style-description">{selectedStyleMeta.description}</p>

        <div className="row split">
          <div>
            <label>Speed ({speed.toFixed(2)}x)</label>
            <input type="range" min={0.7} max={1.3} step={0.01} value={speed} onChange={(e) => setSpeed(Number(e.target.value))} />
          </div>
          <div>
            <label>Render Mode</label>
            <select value={renderMode} onChange={(e) => setRenderMode(e.target.value as RenderMode)}>
              <option value="final">Final (full Chatterbox)</option>
              <option value="preview">Preview (turbo)</option>
            </select>
          </div>
        </div>

        <div className="summary-box">
          Style: {styleLabel(style)} | Speed {speed.toFixed(2)}x | Render {renderMode === "final" ? "Final/full engine" : "Preview/turbo"}
          {selected ? ` | Persona ${selected.name}` : " | No persona selected"}
        </div>

        <button onClick={() => void onGenerate()} disabled={!selectedPersonaReady}>
          Generate Audio
        </button>
        {!selectedPersonaReady && selected ? <p>Selected persona is not certified yet. Recertify or retrain before rendering.</p> : null}

        {generationProgress != null ? (
          <div className="progress-block">
            <label>Generation Progress</label>
            <progress value={toPercent(generationProgress)} max={100} />
            <p>{generationPhaseLabel} ({toPercent(generationProgress)}%)</p>
          </div>
        ) : null}
        <p>{studioStatus}</p>

        {lastGeneration ? (
          <div className="result-box">
            <h3>Latest Output</h3>
            <p>
              {styleLabel(lastGeneration.style)} • {lastGeneration.render_mode} • {lastGeneration.engine_used ?? lastGeneration.engine}
              {lastGeneration.fallback_engine_used ? ` • fallback ${lastGeneration.fallback_engine_used}` : ""}
              {lastGeneration.quality_state === "warning" ? " • advisory-only drift/warnings kept" : ""}
            </p>
            <p>
              segments {lastGeneration.segment_count ?? 0} • identity {lastGeneration.identity_score?.toFixed(3) ?? "n/a"}
              • {formatSeconds(lastGeneration.duration_sec)}
            </p>
            {lastGeneration.warning_codes?.length ? <p>Warnings: {lastGeneration.warning_codes.join(", ")}</p> : null}
            {lastGeneration.applied_tags?.length ? <p>Tags: {lastGeneration.applied_tags.join(", ")}</p> : null}
            {audioSrc ? <audio controls src={audioSrc} /> : null}
          </div>
        ) : null}
      </section>

      <section className="panel">
        <h2>4) Generated Voices</h2>
        <div className="generation-list">
          {generations.map((g) => (
            <article className="generation-card" key={g.id}>
              <div className="row between">
                <h3>#{g.id} • {personas.find((p) => p.id === g.persona_id)?.name ?? `Persona ${g.persona_id}`}</h3>
                <span className="tag">{g.render_mode}</span>
              </div>
              <p className="meta-line">
                {new Date(g.created_at).toLocaleString()} • {formatSeconds(g.duration_sec)} • {styleLabel(g.style)}
              </p>
              <p className="meta-line">
                Engine {g.engine_used ?? g.engine} • fallback {g.fallback_engine_used ?? "none"} • {g.segment_count ?? 0} segments
              </p>
              <p className="generation-script">{clampText(g.input_text, 180)}</p>
              {g.quality_state === "warning" ? <p className="issue-line">Advisories: {clampText((g.quality_warnings ?? []).join(", "), 160)}</p> : null}
              {g.applied_tags?.length ? <p className="meta-line">Tags: {g.applied_tags.join(", ")}</p> : null}
              {g.audio_path ? <audio controls src={mediaUrl(g.audio_path) ?? undefined} /> : null}
              <button onClick={() => void onDeleteGeneration(g.id)}>Delete</button>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
