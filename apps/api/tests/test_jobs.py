from __future__ import annotations

import numpy as np

from app.jobs import JobManager
from app.config import SEGMENT_CROSSFADE_MS


def test_stitch_segments_inserts_pause_before_next_segment_without_trailing_silence() -> None:
    sample_rate = 1000
    pause_ms = 100
    pause_samples = int(sample_rate * (pause_ms / 1000.0))
    manager = JobManager()

    first = np.ones(1000, dtype=np.float32)
    second = np.full(1000, 2.0, dtype=np.float32)
    third = np.full(1000, 3.0, dtype=np.float32)

    stitched, stitched_rate = manager._stitch_segments(
        [
            (first, sample_rate, pause_ms),
            (second, sample_rate, pause_ms),
            (third, sample_rate, pause_ms),
        ]
    )

    fade_samples = int(sample_rate * (SEGMENT_CROSSFADE_MS / 1000.0))
    expected_len = (first.size + second.size + third.size) + (2 * pause_samples) - (2 * fade_samples)
    quiet_run_end = first.size + max(0, pause_samples - fade_samples)

    assert stitched_rate == sample_rate
    assert stitched.shape[0] == expected_len
    assert np.allclose(stitched[first.size:quiet_run_end], 0.0)
    assert np.allclose(stitched[-10:], 3.0)


def test_stitch_segments_rejects_mismatched_sample_rates() -> None:
    manager = JobManager()

    try:
        manager._stitch_segments(
            [
                (np.ones(100, dtype=np.float32), 1000, 50),
                (np.ones(100, dtype=np.float32), 2000, 50),
            ]
        )
    except RuntimeError as exc:
        assert str(exc) == "Segment sample rates do not match"
    else:
        raise AssertionError("Expected stitcher to reject mismatched sample rates")
