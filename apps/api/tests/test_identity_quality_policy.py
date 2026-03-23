from app import config
from app.main import _compute_quality_state


def test_compute_quality_state_bands() -> None:
    assert _compute_quality_state("completed", 0.81) == "pass"
    assert _compute_quality_state("completed", config.IDENTITY_STRICT_PASS_THRESHOLD) == "pass"
    assert _compute_quality_state("completed", 0.55) == "warning"
    assert _compute_quality_state("completed", 0.30) == "hard_fail"
    assert _compute_quality_state("failed", 0.95) == "hard_fail"
    assert _compute_quality_state("completed", None) == "pass"


def test_threshold_validation_rejects_invalid_ordering() -> None:
    old = (
        config.IDENTITY_HARD_FAIL_FLOOR,
        config.IDENTITY_WARNING_FLOOR,
        config.IDENTITY_STRICT_PASS_THRESHOLD,
    )
    try:
        config.IDENTITY_HARD_FAIL_FLOOR = 0.7
        config.IDENTITY_WARNING_FLOOR = 0.5
        config.IDENTITY_STRICT_PASS_THRESHOLD = 0.6
        try:
            config.validate_identity_thresholds()
            assert False, "Expected validate_identity_thresholds() to fail on invalid ordering"
        except ValueError:
            pass
    finally:
        (
            config.IDENTITY_HARD_FAIL_FLOOR,
            config.IDENTITY_WARNING_FLOOR,
            config.IDENTITY_STRICT_PASS_THRESHOLD,
        ) = old
