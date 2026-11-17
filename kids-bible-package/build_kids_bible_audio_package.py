#!/usr/bin/env python3
"""Build the kids Bible narration bundle recommended for the Long Road iOS app.

The recommended plan copies every Protestant canon chapter and every numbered
story, for the girl voice and the boy voice, with ffmpeg stream copy. Nothing
is re-encoded. Source files are never modified or deleted.

Output layout (what the app bundles):

    <out>/KidsChapterAudio/<voice>/<Book>/<chapter>.m4a
    <out>/KidsChapterAudio/<voice>/manifest.json
    <out>/KidsStoryAudio/<voice>/<story>.m4a
    <out>/KidsStoryAudio/<voice>/manifest.json
    <out>/package-summary.json

``--dry-run`` writes the manifests and the summary only. Encoded hashes are
null until a real build. Dry-run sizes are the source file sizes. A real build
records the size and sha256 of each ffmpeg stream-copy output.

Budget: Apple's 4 GiB bundle cap, minus 300 MiB for the rest of the app, minus
a 400 MiB margin. The script exits non-zero if a full package would exceed
that audio budget.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

# Protestant canon, Bible order. 66 books, 1,189 chapters.
CANON = [
    ("Genesis", 50), ("Exodus", 40), ("Leviticus", 27), ("Numbers", 36),
    ("Deuteronomy", 34), ("Joshua", 24), ("Judges", 21), ("Ruth", 4),
    ("1 Samuel", 31), ("2 Samuel", 24), ("1 Kings", 22), ("2 Kings", 25),
    ("1 Chronicles", 29), ("2 Chronicles", 36), ("Ezra", 10), ("Nehemiah", 13),
    ("Esther", 10), ("Job", 42), ("Psalms", 150), ("Proverbs", 31),
    ("Ecclesiastes", 12), ("Song of Solomon", 8), ("Isaiah", 66), ("Jeremiah", 52),
    ("Lamentations", 5), ("Ezekiel", 48), ("Daniel", 12), ("Hosea", 14),
    ("Joel", 3), ("Amos", 9), ("Obadiah", 1), ("Jonah", 4), ("Micah", 7),
    ("Nahum", 3), ("Habakkuk", 3), ("Zephaniah", 3), ("Haggai", 2),
    ("Zechariah", 14), ("Malachi", 4), ("Matthew", 28), ("Mark", 16),
    ("Luke", 24), ("John", 21), ("Acts", 28), ("Romans", 16),
    ("1 Corinthians", 16), ("2 Corinthians", 13), ("Galatians", 6),
    ("Ephesians", 6), ("Philippians", 4), ("Colossians", 4),
    ("1 Thessalonians", 5), ("2 Thessalonians", 3), ("1 Timothy", 6),
    ("2 Timothy", 4), ("Titus", 3), ("Philemon", 1), ("Hebrews", 13),
    ("James", 5), ("1 Peter", 5), ("2 Peter", 3), ("1 John", 5),
    ("2 John", 1), ("3 John", 1), ("Jude", 1), ("Revelation", 22),
]
STORY_COUNT = 50

# sample1 is the girl voice directory in this snapshot. boy is the boy voice.
VOICES = (
    {"voice": "girl", "source_dir": "sample1"},
    {"voice": "boy", "source_dir": "boy"},
)

APP_LIMIT_BYTES = 4 * 1024 ** 3
NON_AUDIO_BYTES = 300 * 1024 ** 2
MARGIN_BYTES = 400 * 1024 ** 2
AUDIO_BUDGET_BYTES = APP_LIMIT_BYTES - NON_AUDIO_BYTES - MARGIN_BYTES

PLAN_ID = "both-voices-source-aac-lc"
ENCODING = "aac-lc-source-copy"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe_duration(path: Path) -> float:
    proc = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1",
            str(path),
        ],
        capture_output=True, text=True,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        raise RuntimeError(f"ffprobe failed for {path}: {proc.stderr.strip()[-300:]}")
    return float(proc.stdout.strip())


def probe_audio(path: Path) -> dict:
    proc = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=codec_name,profile,sample_rate,channels,codec_type",
            "-show_entries", "format=duration,size",
            "-of", "json",
            str(path),
        ],
        capture_output=True, text=True,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        raise RuntimeError(f"ffprobe failed for {path}: {proc.stderr.strip()[-300:]}")
    data = json.loads(proc.stdout)
    streams = [s for s in data.get("streams", []) if s.get("codec_type") == "audio"]
    if len(streams) != 1:
        raise RuntimeError(f"{path} has {len(streams)} audio streams")
    stream = streams[0]
    fmt = data.get("format") or {}
    duration = float(fmt["duration"])
    return {
        "codec": stream.get("codec_name"),
        "profile": stream.get("profile"),
        "sample_rate": int(stream["sample_rate"]),
        "channels": int(stream["channels"]),
        "duration_sec": duration,
    }


def inspect_source(path_str: str) -> dict:
    path = Path(path_str)
    info = probe_audio(path)
    info["sha256_source"] = sha256_file(path)
    info["size_bytes"] = path.stat().st_size
    info["source"] = path_str
    return info


def stream_copy(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(src),
            "-map", "0:a:0",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(dest),
        ],
        capture_output=True, text=True,
    )
    if proc.returncode != 0 or not dest.exists() or dest.stat().st_size == 0:
        raise RuntimeError(f"ffmpeg copy failed for {src}: {proc.stderr.strip()[-400:]}")


def discover(repo: Path) -> tuple[list[dict], list[str]]:
    """Return package items in Bible order, and excluded extra audio paths."""
    items: list[dict] = []
    excluded: list[str] = []
    for voice in VOICES:
        chapter_root = repo / "kids-bible-audio" / voice["source_dir"]
        story_root = repo / "long-road-kids-audio" / voice["source_dir"]
        if not chapter_root.is_dir():
            raise SystemExit(f"missing voice directory {chapter_root}")
        if not story_root.is_dir():
            raise SystemExit(f"missing story directory {story_root}")
        for book, count in CANON:
            book_dir = chapter_root / book
            if not book_dir.is_dir():
                for chapter in range(1, count + 1):
                    items.append(_missing_item(voice["voice"], "chapter", book, chapter))
                continue
            for extra in sorted(book_dir.rglob("*.m4a")):
                if extra.parent != book_dir:
                    excluded.append(str(extra.relative_to(repo)))
            for chapter in range(1, count + 1):
                src = book_dir / f"{chapter}.m4a"
                rel_out = f"KidsChapterAudio/{voice['voice']}/{book}/{chapter}.m4a"
                if not src.is_file():
                    items.append(_missing_item(voice["voice"], "chapter", book, chapter, rel_out))
                    continue
                items.append({
                    "kind": "chapter",
                    "voice": voice["voice"],
                    "book": book,
                    "chapter": chapter,
                    "file": f"{book}/{chapter}.m4a",
                    "source": str(src),
                    "dest_rel": rel_out,
                })
        stories_dir = story_root / "stories"
        for story in range(1, STORY_COUNT + 1):
            src = stories_dir / f"{story}.m4a"
            rel_out = f"KidsStoryAudio/{voice['voice']}/{story}.m4a"
            if not src.is_file():
                items.append(_missing_item(voice["voice"], "story", "Stories", story, rel_out))
                continue
            items.append({
                "kind": "story",
                "voice": voice["voice"],
                "book": "Stories",
                "chapter": story,
                "file": f"{story}.m4a",
                "source": str(src),
                "dest_rel": rel_out,
            })
        if stories_dir.is_dir():
            for extra in sorted(stories_dir.glob("*.m4a")):
                if not extra.stem.isdigit() or not (1 <= int(extra.stem) <= STORY_COUNT):
                    excluded.append(str(extra.relative_to(repo)))
    return items, excluded


def _missing_item(voice: str, kind: str, book: str, chapter: int, dest_rel: str | None = None) -> dict:
    return {
        "kind": kind,
        "voice": voice,
        "book": book,
        "chapter": chapter,
        "file": None,
        "source": None,
        "dest_rel": dest_rel,
        "missing": True,
    }


def select_items(items: list[dict], only: str | None) -> list[dict]:
    if not only:
        return items
    wanted = set()
    for token in only.split(","):
        token = token.strip()
        if not token:
            continue
        parts = token.split(":")
        if len(parts) != 3:
            raise SystemExit(f"--only entry must be voice:book:chapter, got {token}")
        voice, book, chapter = parts
        wanted.add((voice, book, int(chapter)))
    chosen = []
    for item in items:
        key = (item["voice"], item["book"], item["chapter"])
        if key in wanted:
            chosen.append(item)
            wanted.remove(key)
    if wanted:
        missing = ", ".join(f"{v}:{b}:{c}" for v, b, c in sorted(wanted))
        raise SystemExit(f"--only did not match: {missing}")
    return chosen


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def source_rel(repo: Path, source: str) -> str:
    return str(Path(source).resolve().relative_to(repo.resolve()))


def git_head(repo: Path) -> str | None:
    proc = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def assert_safe_output(repo: Path, output: Path) -> Path:
    output = output.resolve()
    repo = repo.resolve()
    protected = [repo / "kids-bible-audio", repo / "long-road-kids-audio"]
    for root in protected:
        if output == root or root in output.parents:
            raise SystemExit(f"refusing to write inside source audio tree: {output}")
    if output == repo:
        raise SystemExit("refusing to use the repo root as the output folder")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--source", type=Path, default=None, help="repo root (default: parent of this script)")
    parser.add_argument("--output", type=Path, required=True, help="package output folder")
    parser.add_argument("--dry-run", action="store_true", help="write manifests only, no audio files")
    parser.add_argument("--only", default=None, help="comma-separated voice:book:chapter to build a subset")
    parser.add_argument("--workers", type=int, default=max(1, min(4, os.cpu_count() or 1)))
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    repo = (args.source or script_dir.parent).resolve()
    output = assert_safe_output(repo, args.output)
    if not shutil.which("ffprobe") or not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg and ffprobe must be on PATH")

    items, excluded = discover(repo)
    items = select_items(items, args.only)
    missing = [item for item in items if item.get("missing")]
    present = [item for item in items if not item.get("missing")]

    print(f"inspecting {len(present)} files with {args.workers} workers", flush=True)
    infos: dict[str, dict] = {}
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(inspect_source, item["source"]): item for item in present}
        done = 0
        for fut in as_completed(futures):
            item = futures[fut]
            infos[item["source"]] = fut.result()
            done += 1
            if done % 100 == 0 or done == len(present):
                print(f"inspected {done}/{len(present)}", flush=True)

    codec_problems = []
    rejected: set[str] = set()
    for item in present:
        info = infos[item["source"]]
        bad_codec = (
            info["codec"] != "aac"
            or info["profile"] != "LC"
            or info["channels"] != 1
            or info["sample_rate"] != 24000
        )
        if bad_codec:
            codec_problems.append({
                "source": source_rel(repo, item["source"]),
                "codec": info["codec"],
                "profile": info["profile"],
                "sample_rate": info["sample_rate"],
                "channels": info["channels"],
            })
        if info["duration_sec"] <= 0.05 or info["size_bytes"] == 0:
            rejected.add(item["source"])
            missing.append({
                "voice": item["voice"], "kind": item["kind"], "book": item["book"],
                "chapter": item["chapter"], "reason": "zero-length",
            })
    present = [item for item in present if item["source"] not in rejected]

    audio_bytes = 0
    for item in present:
        info = infos[item["source"]]
        encoded_size = None
        encoded_hash = None
        if not args.dry_run:
            dest = output / item["dest_rel"]
            stream_copy(Path(item["source"]), dest)
            encoded_size = dest.stat().st_size
            encoded_hash = sha256_file(dest)
            # Confirm the copy still decodes and keeps the duration.
            copied = probe_duration(dest)
            if abs(copied - info["duration_sec"]) > 0.05:
                raise SystemExit(
                    f"duration changed on copy {item['dest_rel']}: {info['duration_sec']} -> {copied}"
                )
        entry = {
            "kind": item["kind"],
            "book": item["book"],
            "chapter": item["chapter"],
            "voice": item["voice"],
            "file": item["file"],
            "duration_sec": round(info["duration_sec"], 3),
            "size_bytes": encoded_size if encoded_size is not None else info["size_bytes"],
            "sha256_source": info["sha256_source"],
            "sha256_encoded": encoded_hash,
            "source_path": source_rel(repo, item["source"]),
        }
        item["entry"] = entry
        audio_bytes += entry["size_bytes"]

    grouped: dict[tuple[str, str], list] = {}
    for item in present:
        grouped.setdefault((item["kind"], item["voice"]), []).append(item["entry"])

    for (kind, voice), entries in grouped.items():
        if kind == "chapter":
            path = output / "KidsChapterAudio" / voice / "manifest.json"
        else:
            path = output / "KidsStoryAudio" / voice / "manifest.json"
        write_json(path, entries)

    # Full-library budget uses every present file when --only is omitted.
    # A subset build reports its own byte count and does not pretend to be the bundle.
    full_package = args.only is None
    projected_bundle = audio_bytes + NON_AUDIO_BYTES if full_package else None
    over_budget = bool(full_package and audio_bytes > AUDIO_BUDGET_BYTES)
    summary = {
        "plan": PLAN_ID,
        "encoding": ENCODING,
        "description": (
            "All 66 books in Bible order, girl and boy together, plus stories 1-50 "
            "for both voices. Audio is the source AAC-LC mono 24 kHz stream, "
            "copied with ffmpeg and faststart. No re-encode."
        ),
        "dry_run": args.dry_run,
        "subset": args.only,
        "source_commit": git_head(repo),
        "counts": {
            "files": len(present),
            "missing": len(missing),
            "chapters_per_voice": sum(1 for item in present if item["kind"] == "chapter" and item["voice"] == "girl"),
            "stories_per_voice": sum(1 for item in present if item["kind"] == "story" and item["voice"] == "girl"),
        },
        "audio_bytes": audio_bytes,
        "audio_budget_bytes": AUDIO_BUDGET_BYTES,
        "app_limit_bytes": APP_LIMIT_BYTES,
        "non_audio_allowance_bytes": NON_AUDIO_BYTES,
        "margin_bytes": MARGIN_BYTES,
        "projected_bundle_bytes": projected_bundle,
        "headroom_under_4gib_bytes": (APP_LIMIT_BYTES - projected_bundle) if projected_bundle is not None else None,
        "within_audio_budget": (not over_budget) if full_package else None,
        "excluded_extra_audio": excluded if args.only is None else [],
        "missing": [
            {"voice": item["voice"], "kind": item["kind"], "book": item["book"], "chapter": item["chapter"]}
            for item in missing
        ],
        "codec_problems": codec_problems,
        "size_note": (
            "Dry-run size_bytes and sha256_encoded: size is the source file, encoded hash is null. "
            "A real build fills size_bytes and sha256_encoded from the faststart stream copy."
            if args.dry_run else
            "size_bytes and sha256_encoded describe the ffmpeg stream-copy output."
        ),
    }
    write_json(output / "package-summary.json", summary)
    print(json.dumps({
        "audio_bytes": audio_bytes,
        "files": len(present),
        "missing": len(missing),
        "within_audio_budget": summary["within_audio_budget"],
        "dry_run": args.dry_run,
        "output": str(output),
    }, indent=2))
    if missing or codec_problems or over_budget:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
