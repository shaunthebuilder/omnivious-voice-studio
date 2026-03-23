import type {
  DeleteGenerationResult,
  DeletePersonaResult,
  Generation,
  GenerationStyle,
  Job,
  Persona,
  RenderMode,
} from "./types";

function getApiBase(): string {
  if (process.env.NEXT_PUBLIC_API_BASE) return process.env.NEXT_PUBLIC_API_BASE;
  if (typeof window !== "undefined") {
    const host = window.location.hostname || "localhost";
    return `${window.location.protocol}//${host}:8001`;
  }
  return "http://localhost:8001";
}

async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function fetchPersonas(): Promise<Persona[]> {
  const res = await fetch(`${getApiBase()}/api/personas`, { cache: "no-store" });
  return asJson<Persona[]>(res);
}

export async function createPersonaFromUpload(personaName: string, file: File): Promise<{ persona: Persona; job_id: number }> {
  const fd = new FormData();
  fd.set("persona_name", personaName);
  fd.set("source_type", "upload");
  fd.set("file", file);
  const res = await fetch(`${getApiBase()}/api/personas`, { method: "POST", body: fd });
  return asJson<{ persona: Persona; job_id: number }>(res);
}

export async function createPersonaFromYoutube(personaName: string, url: string): Promise<{ persona: Persona; job_id: number }> {
  const fd = new FormData();
  fd.set("persona_name", personaName);
  fd.set("source_type", "youtube");
  fd.set("youtube_url", url);
  const res = await fetch(`${getApiBase()}/api/personas`, { method: "POST", body: fd });
  return asJson<{ persona: Persona; job_id: number }>(res);
}

export async function renamePersona(personaId: number, name: string): Promise<Persona> {
  const res = await fetch(`${getApiBase()}/api/personas/${personaId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  return asJson<Persona>(res);
}

export async function deletePersona(personaId: number): Promise<DeletePersonaResult> {
  const res = await fetch(`${getApiBase()}/api/personas/${personaId}`, { method: "DELETE" });
  return asJson<DeletePersonaResult>(res);
}

export async function retrainPersonaFromUpload(personaId: number, file: File): Promise<{ persona: Persona; job_id: number }> {
  const fd = new FormData();
  fd.set("source_type", "upload");
  fd.set("file", file);
  const res = await fetch(`${getApiBase()}/api/personas/${personaId}/retrain`, { method: "POST", body: fd });
  return asJson<{ persona: Persona; job_id: number }>(res);
}

export async function retrainPersonaFromYoutube(personaId: number, url: string): Promise<{ persona: Persona; job_id: number }> {
  const fd = new FormData();
  fd.set("source_type", "youtube");
  fd.set("youtube_url", url);
  const res = await fetch(`${getApiBase()}/api/personas/${personaId}/retrain`, { method: "POST", body: fd });
  return asJson<{ persona: Persona; job_id: number }>(res);
}

export async function recertifyPersona(personaId: number): Promise<{ persona: Persona; job_id: number }> {
  const res = await fetch(`${getApiBase()}/api/personas/${personaId}/recertify`, { method: "POST" });
  return asJson<{ persona: Persona; job_id: number }>(res);
}

export async function fetchJob(jobId: number): Promise<Job> {
  const res = await fetch(`${getApiBase()}/api/jobs/${jobId}`, { cache: "no-store" });
  return asJson<Job>(res);
}

export async function generateSpeech(payload: {
  persona_id: number;
  text: string;
  style: GenerationStyle;
  speed: number;
  render_mode: RenderMode;
  model_id?: string | null;
}): Promise<{ generation_id: number; job_id: number }> {
  const res = await fetch(`${getApiBase()}/api/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return asJson<{ generation_id: number; job_id: number }>(res);
}

export async function fetchGeneration(generationId: number): Promise<Generation> {
  const res = await fetch(`${getApiBase()}/api/generations/${generationId}`, { cache: "no-store" });
  return asJson<Generation>(res);
}

export async function fetchGenerations(params?: { persona_id?: number; limit?: number }): Promise<Generation[]> {
  const usp = new URLSearchParams();
  if (params?.persona_id != null) usp.set("persona_id", String(params.persona_id));
  if (params?.limit != null) usp.set("limit", String(params.limit));
  const suffix = usp.toString() ? `?${usp.toString()}` : "";
  const res = await fetch(`${getApiBase()}/api/generations${suffix}`, { cache: "no-store" });
  return asJson<Generation[]>(res);
}

export async function deleteGeneration(generationId: number): Promise<DeleteGenerationResult> {
  const res = await fetch(`${getApiBase()}/api/generations/${generationId}`, { method: "DELETE" });
  return asJson<DeleteGenerationResult>(res);
}

export function mediaUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  if (path.startsWith("http")) return path;
  return `${getApiBase()}${path}`;
}
