from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from .models import Generation


def prune_expired_generations(db: Session, max_age_hours: int) -> int:
    cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
    stale = db.query(Generation).filter(Generation.created_at < cutoff).all()
    removed = 0

    for gen in stale:
        if gen.audio_path:
            p = Path(gen.audio_path)
            if p.exists() and p.is_file():
                try:
                    p.unlink()
                except OSError:
                    pass
        db.delete(gen)
        removed += 1

    if removed:
        db.commit()
    return removed
