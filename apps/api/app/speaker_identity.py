from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import librosa
import numpy as np
import soundfile as sf


@dataclass
class IdentityScoreResult:
    score: float
    backend: str


class SpeakerIdentityError(Exception):
    pass


class AcousticIdentityScorer:
    def __init__(self) -> None:
        self._backend = 'acoustic_mfcc'

    def backend_name(self) -> str:
        return self._backend

    def embedding_from_audio_path(self, audio_path: str | Path) -> np.ndarray:
        wav = _load_mono_16k(audio_path)
        if wav.size == 0:
            raise SpeakerIdentityError('Audio is empty for speaker embedding')
        return _l2_normalize(_extract_features(wav, 16000))

    def similarity(self, reference_embedding: np.ndarray, audio_path: str | Path) -> IdentityScoreResult:
        cand = self.embedding_from_audio_path(audio_path)
        ref = _l2_normalize(reference_embedding.astype(np.float32))
        score = float(np.dot(ref, cand))
        return IdentityScoreResult(score=score, backend=self._backend)

    def compare_embeddings(self, reference_embedding: np.ndarray, candidate_embedding: np.ndarray) -> float:
        ref = _l2_normalize(reference_embedding.astype(np.float32))
        cand = _l2_normalize(candidate_embedding.astype(np.float32))
        return float(np.dot(ref, cand))

    def speech_quality(self, audio_path: str | Path) -> dict[str, float]:
        wav = _load_mono_16k(audio_path)
        if wav.size == 0:
            return {'speech_ratio': 0.0, 'clipping_ratio': 1.0, 'rms_db': -120.0}
        frame_len = int(16000 * 0.032)
        hop_len = int(16000 * 0.016)
        rms = librosa.feature.rms(y=wav, frame_length=frame_len, hop_length=hop_len)[0]
        max_rms = float(np.max(rms) + 1e-9)
        speech_ratio = float(np.mean(rms > (max_rms * 0.12)))
        clipping_ratio = float(np.mean(np.abs(wav) > 0.98))
        rms_db = float(20 * np.log10(np.sqrt(np.mean(np.square(wav)) + 1e-9) + 1e-9))
        return {
            'speech_ratio': round(speech_ratio, 4),
            'clipping_ratio': round(clipping_ratio, 6),
            'rms_db': round(rms_db, 3),
        }

    def save_embedding(self, embedding: np.ndarray, out_path: str | Path) -> str:
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.save(path, embedding.astype(np.float32))
        return str(path)

    def load_embedding(self, path: str | Path) -> np.ndarray:
        p = Path(path)
        if not p.exists():
            raise SpeakerIdentityError(f'Speaker embedding file not found: {p}')
        emb = np.load(p)
        return _l2_normalize(emb.astype(np.float32))

    def advisory_intelligibility(self, reference_text: str | None, hypothesis_text: str | None) -> float | None:
        if not reference_text or not hypothesis_text:
            return None
        ref_tokens = _normalize_text(reference_text).split()
        hyp_tokens = _normalize_text(hypothesis_text).split()
        if not ref_tokens or not hyp_tokens:
            return None
        ref_set = set(ref_tokens)
        hyp_set = set(hyp_tokens)
        overlap = len(ref_set & hyp_set)
        union = len(ref_set | hyp_set)
        if union == 0:
            return None
        return round(overlap / union, 4)


def _normalize_text(text: str) -> str:
    return ' '.join((text or '').lower().split())


def _load_mono_16k(path: str | Path) -> np.ndarray:
    wav, sr = sf.read(str(path), always_2d=False)
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    if sr != 16000:
        wav = librosa.resample(wav.astype(np.float32), orig_sr=sr, target_sr=16000)
    return wav.astype(np.float32)


def _extract_features(wav: np.ndarray, sample_rate: int) -> np.ndarray:
    mfcc = librosa.feature.mfcc(y=wav, sr=sample_rate, n_mfcc=24)
    delta = librosa.feature.delta(mfcc)
    delta2 = librosa.feature.delta(mfcc, order=2)
    chroma = librosa.feature.chroma_stft(y=wav, sr=sample_rate)
    contrast = librosa.feature.spectral_contrast(y=wav, sr=sample_rate)
    centroid = librosa.feature.spectral_centroid(y=wav, sr=sample_rate)
    bandwidth = librosa.feature.spectral_bandwidth(y=wav, sr=sample_rate)
    rms = librosa.feature.rms(y=wav)
    zcr = librosa.feature.zero_crossing_rate(y=wav)
    feat = np.concatenate(
        [
            mfcc.mean(axis=1),
            mfcc.std(axis=1),
            delta.mean(axis=1),
            delta.std(axis=1),
            delta2.mean(axis=1),
            delta2.std(axis=1),
            chroma.mean(axis=1),
            contrast.mean(axis=1),
            np.array([
                float(np.mean(centroid)),
                float(np.std(centroid)),
                float(np.mean(bandwidth)),
                float(np.std(bandwidth)),
                float(np.mean(rms)),
                float(np.std(rms)),
                float(np.mean(zcr)),
                float(np.std(zcr)),
            ], dtype=np.float32),
        ]
    ).astype(np.float32)
    return feat


def _l2_normalize(v: np.ndarray) -> np.ndarray:
    denom = float(np.linalg.norm(v) + 1e-9)
    return (v / denom).astype(np.float32)


identity_scorer = AcousticIdentityScorer()
