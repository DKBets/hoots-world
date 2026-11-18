"""Return an override path when a non-empty override file is present."""

from __future__ import annotations

from pathlib import Path


def prefer_override(repo: Path, default: Path, override: Path) -> Path:
    """Use *override* when it exists and has bytes; otherwise *default*.

    *repo* is accepted so callers can pass the repo root uniformly. Paths may
    be absolute or relative to *repo*.
    """
    override_path = override if override.is_absolute() else repo / override
    default_path = default if default.is_absolute() else repo / default
    if override_path.is_file() and override_path.stat().st_size > 0:
        return override_path
    return default_path


def story_source(repo: Path, source_dir: str, story: int) -> Path:
    default = repo / "long-road-kids-audio" / source_dir / "stories" / f"{story}.m4a"
    override = repo / "kids-bible-audio" / "overrides" / "stories" / source_dir / f"{story}.m4a"
    return prefer_override(repo, default, override)
