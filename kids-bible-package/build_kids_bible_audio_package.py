#!/usr/bin/env python3
"""Build the kids Bible narration bundle for the Long Road iOS app.

Both voices, all 66 books, and stories 1-50. A non-empty file under
kids-bible-audio/overrides/ replaces the lab-audio file for that item
(prefer_override.story_source for stories). The override's sha256 must match
overrides/manifest.json, and the lab-audio blob it names must still match.
A mismatch is a stale override and the build stops. The chosen file then
follows the peak rule: at or below -1.0 dBTP is copied with ffmpeg (-c copy);
above -1.0 dBTP is decoded, true-peak limited, and re-encoded as AAC-LC mono
at that file's sample rate and stream bitrate.

The PCM limiter is ffmpeg alimiter at 4x oversampling (24 kHz -> 96 kHz),
level=false so it does not raise quiet audio. The ceiling starts at -2.7 dB,
which is the -1.5 dBTP master target plus the overshoot libfdk-aac adds at
this bitrate. The encoded file is measured, and if its true peak is still
above -1.5 dBTP the ceiling is lowered and the file is encoded again.
ffmpeg's built-in AAC encoder was measured separately: at ~32 kbps it pushes
a -1.5 dBTP PCM file back to about 0 dBTP, so the re-encode uses fdkaac
(libfdk-aac AAC-LC). Stream copies do not need fdkaac.

Manifests match longroad-ios PR #3 (scripts/check_kids_audio.py): one object
per voice with an entries array, book codes such as GEN, chapter files
GEN/001.m4a, story files stories/1.m4a. sha256 is the output file. Extra
fields record the source hash, true peak, and LUFS before and after.

Source audio is never modified or deleted. The script refuses to write inside
the source trees.

Budget: 4 GiB minus 300 MiB for the rest of the app minus a 400 MiB margin.
A full build that would exceed that audio budget exits non-zero.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

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
# KidsBible/index.json codes. The iOS checker resolves folder names with these.
BOOK_CODE = {
    "Genesis": "GEN", "Exodus": "EXO", "Leviticus": "LEV", "Numbers": "NUM",
    "Deuteronomy": "DEU", "Joshua": "JOS", "Judges": "JDG", "Ruth": "RUT",
    "1 Samuel": "1SA", "2 Samuel": "2SA", "1 Kings": "1KI", "2 Kings": "2KI",
    "1 Chronicles": "1CH", "2 Chronicles": "2CH", "Ezra": "EZR", "Nehemiah": "NEH",
    "Esther": "EST", "Job": "JOB", "Psalms": "PSA", "Proverbs": "PRO",
    "Ecclesiastes": "ECC", "Song of Solomon": "SNG", "Isaiah": "ISA", "Jeremiah": "JER",
    "Lamentations": "LAM", "Ezekiel": "EZK", "Daniel": "DAN", "Hosea": "HOS",
    "Joel": "JOL", "Amos": "AMO", "Obadiah": "OBA", "Jonah": "JON",
    "Micah": "MIC", "Nahum": "NAM", "Habakkuk": "HAB", "Zephaniah": "ZEP",
    "Haggai": "HAG", "Zechariah": "ZEC", "Malachi": "MAL", "Matthew": "MAT",
    "Mark": "MRK", "Luke": "LUK", "John": "JHN", "Acts": "ACT", "Romans": "ROM",
    "1 Corinthians": "1CO", "2 Corinthians": "2CO", "Galatians": "GAL",
    "Ephesians": "EPH", "Philippians": "PHP", "Colossians": "COL",
    "1 Thessalonians": "1TH", "2 Thessalonians": "2TH", "1 Timothy": "1TI",
    "2 Timothy": "2TI", "Titus": "TIT", "Philemon": "PHM", "Hebrews": "HEB",
    "James": "JAS", "1 Peter": "1PE", "2 Peter": "2PE", "1 John": "1JN",
    "2 John": "2JN", "3 John": "3JN", "Jude": "JUD", "Revelation": "REV",
}
STORY_COUNT = 50

VOICES = (
    {"voice": "girl", "source_dir": "sample1"},
    {"voice": "boy", "source_dir": "boy"},
)

APP_LIMIT_BYTES = 4 * 1024 ** 3
NON_AUDIO_BYTES = 300 * 1024 ** 2
MARGIN_BYTES = 400 * 1024 ** 2
AUDIO_BUDGET_BYTES = APP_LIMIT_BYTES - NON_AUDIO_BYTES - MARGIN_BYTES

# Fix files hotter than this. The delivered master target is stricter.
TRIGGER_TRUE_PEAK_DBTP = -1.0
TARGET_TRUE_PEAK_DBTP = -1.5
# First PCM ceiling. libfdk-aac at ~32 kbps overshoots a -1.5 dBTP PCM file
# by about 0.6 to 1.1 dB; -2.7 dB lands the worst source peak (+5.3) at -1.7.
INITIAL_PCM_CEILING_DB = -2.7
MAX_LIMIT_ATTEMPTS = 5

PLAN_ID = "both-voices-aac-lc-true-peak"
ENCODING = "copy-or-peak-limited-aac-lc"

I_RE = re.compile(r"I:\s+(-?\d+(?:\.\d+)?)\s+LUFS")
PEAK_RE = re.compile(r"Peak:\s+(-?inf|-?\d+(?:\.\d+)?)\s+dBFS")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def probe_audio(path: Path) -> dict:
    proc = run([
        "ffprobe", "-v", "error",
        "-show_entries", "stream=codec_name,profile,sample_rate,channels,bit_rate,codec_type",
        "-show_entries", "format=duration,bit_rate",
        "-of", "json", str(path),
    ])
    if proc.returncode != 0 or not proc.stdout.strip():
        raise RuntimeError(f"ffprobe failed for {path}: {proc.stderr.strip()[-300:]}")
    data = json.loads(proc.stdout)
    streams = [s for s in data.get("streams", []) if s.get("codec_type") == "audio"]
    if len(streams) != 1:
        raise RuntimeError(f"{path} has {len(streams)} audio streams")
    stream = streams[0]
    fmt = data.get("format") or {}
    bitrate = stream.get("bit_rate") or fmt.get("bit_rate")
    return {
        "codec": stream.get("codec_name"),
        "profile": stream.get("profile"),
        "sample_rate": int(stream["sample_rate"]),
        "channels": int(stream["channels"]),
        "bitrate": int(bitrate) if bitrate else None,
        "duration_sec": float(fmt["duration"]),
    }


def measure_loudness(path: Path) -> tuple[float, float]:
    proc = run([
        "ffmpeg", "-hide_banner", "-nostdin", "-nostats", "-loglevel", "info",
        "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-",
    ])
    if proc.returncode != 0:
        raise RuntimeError(f"loudness failed for {path}: {proc.stderr[-300:]}")
    block = proc.stderr[proc.stderr.rfind("Summary:"):]
    integrated = I_RE.search(block)
    peak = PEAK_RE.search(block)
    if not integrated or not peak or peak.group(1) in ("-inf", "inf"):
        raise RuntimeError(f"loudness summary missing for {path}")
    return round(float(integrated.group(1)), 1), round(float(peak.group(1)), 1)


def stream_copy(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src), "-map", "0:a:0", "-c:a", "copy",
        "-movflags", "+faststart", str(dest),
    ])
    if proc.returncode != 0 or not dest.exists() or dest.stat().st_size == 0:
        raise RuntimeError(f"ffmpeg copy failed for {src}: {proc.stderr.strip()[-400:]}")


def limiter_filter(ceiling_db: float) -> str:
    limit = 10 ** (ceiling_db / 20.0)
    return (
        "aresample=96000,"
        f"alimiter=limit={limit:.8f}:level=false:latency=true:attack=1:release=80,"
        "aresample=24000"
    )


def peak_limit_encode(src: Path, dest: Path, bitrate: int, ceiling_db: float, fdkaac: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = dest.with_suffix(".tmp.m4a")
    err_path = dest.with_suffix(".ffmpeg.err")
    if temp.exists():
        temp.unlink()
    with err_path.open("wb") as err_handle:
        ffmpeg = subprocess.Popen(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(src),
                "-af", limiter_filter(ceiling_db),
                "-f", "wav", "-ac", "1", "-ar", "24000", "-",
            ],
            stdout=subprocess.PIPE, stderr=err_handle,
        )
        encoded = subprocess.Popen(
            [fdkaac, "-p", "2", "-b", str(bitrate), "-m", "0", "-o", str(temp), "-"],
            stdin=ffmpeg.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if ffmpeg.stdout:
            ffmpeg.stdout.close()
        _, enc_err = encoded.communicate()
        ffmpeg.wait()
    ffmpeg_err = err_path.read_text(errors="replace") if err_path.exists() else ""
    err_path.unlink(missing_ok=True)
    if ffmpeg.returncode != 0 or encoded.returncode != 0 or not temp.exists() or temp.stat().st_size == 0:
        if temp.exists():
            temp.unlink()
        err = (enc_err.decode("utf-8", "replace") if isinstance(enc_err, bytes) else str(enc_err)) + ffmpeg_err
        raise RuntimeError(f"peak-limit encode failed for {src}: {err[-400:]}")
    proc = run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(temp), "-c", "copy", "-movflags", "+faststart", str(dest),
    ])
    temp.unlink(missing_ok=True)
    if proc.returncode != 0 or not dest.exists() or dest.stat().st_size == 0:
        raise RuntimeError(f"faststart remux failed for {src}: {proc.stderr.strip()[-300:]}")


def discover(repo: Path) -> tuple[list[dict], list[str]]:
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
            code = BOOK_CODE[book]
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
                file_name = f"{code}/{chapter:03d}.m4a"
                rel_out = f"KidsChapterAudio/{voice['voice']}/{file_name}"
                if not src.is_file():
                    items.append(_missing_item(voice["voice"], "chapter", book, chapter, rel_out))
                    continue
                items.append({
                    "kind": "chapter",
                    "voice": voice["voice"],
                    "book": book,
                    "book_code": code,
                    "chapter": chapter,
                    "file": file_name,
                    "source": str(src),
                    "dest_rel": rel_out,
                })
        stories_dir = story_root / "stories"
        for story in range(1, STORY_COUNT + 1):
            src = stories_dir / f"{story}.m4a"
            file_name = f"stories/{story}.m4a"
            rel_out = f"KidsStoryAudio/{voice['voice']}/{file_name}"
            if not src.is_file():
                items.append(_missing_item(voice["voice"], "story", "Stories", story, rel_out))
                continue
            items.append({
                "kind": "story",
                "voice": voice["voice"],
                "book": "Stories",
                "book_code": None,
                "chapter": story,
                "file": file_name,
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
        "kind": kind, "voice": voice, "book": book, "chapter": chapter,
        "file": None, "source": None, "dest_rel": dest_rel, "missing": True,
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
        missing = ", ".join(f"{v}:{b}:{c}" for v, b, c in sorted(wanted, key=lambda row: (row[0], row[1], row[2])))
        raise SystemExit(f"--only did not match: {missing}")
    return chosen


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def source_rel(repo: Path, source: str) -> str:
    return str(Path(source).resolve().relative_to(repo.resolve()))


def git_head(repo: Path) -> str | None:
    proc = run(["git", "-C", str(repo), "rev-parse", "HEAD"])
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def assert_safe_output(repo: Path, output: Path) -> Path:
    output = output.resolve()
    repo = repo.resolve()
    for root in (repo / "kids-bible-audio", repo / "long-road-kids-audio"):
        if output == root or root in output.parents:
            raise SystemExit(f"refusing to write inside source audio tree: {output}")
    if output == repo:
        raise SystemExit("refusing to use the repo root as the output folder")
    return output


def load_override_index(repo: Path) -> dict[tuple, dict]:
    path = repo / "kids-bible-audio" / "overrides" / "manifest.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text())
    index = {}
    for row in data.get("overrides", []):
        index[(row["kind"], row["source_dir"], int(row["id"]))] = row
    return index


def override_helpers(repo: Path):
    folder = repo / "kids-bible-audio" / "overrides"
    if not (folder / "prefer_override.py").is_file():
        return None
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
    import prefer_override
    return prefer_override


def apply_overrides(repo: Path, items: list[dict]) -> None:
    """Prefer kids-bible-audio/overrides when a non-empty file is present.

    The override file's sha256 must match overrides/manifest.json. The lab-audio
    file it claims to replace must still have that manifest's replaced sha256.
    A mismatch means the override is stale, and the build stops.
    """
    helpers = override_helpers(repo)
    index = load_override_index(repo)
    if helpers is None:
        if index:
            raise SystemExit("overrides/manifest.json exists but prefer_override.py is missing")
        for item in items:
            item["audio_source"] = "lab-audio"
        return
    claimed = set()
    for item in items:
        if item.get("missing"):
            continue
        source_dir = "sample1" if item["voice"] == "girl" else "boy"
        default = Path(item["source"])
        if item["kind"] == "story":
            chosen = helpers.story_source(repo, source_dir, item["chapter"])
        else:
            override = (
                repo / "kids-bible-audio" / "overrides" / "chapters"
                / source_dir / item["book"] / f"{item['chapter']}.m4a"
            )
            chosen = helpers.prefer_override(repo, default, override)
        item["audio_source"] = "lab-audio"
        if chosen.resolve() == default.resolve():
            continue
        key = (item["kind"], source_dir, item["chapter"])
        row = index.get(key)
        if row is None:
            raise SystemExit(f"override {chosen} has no row in overrides/manifest.json")
        claimed.add(key)
        file_hash = sha256_file(chosen)
        if file_hash != row["sha256"]:
            raise SystemExit(
                f"override sha256 mismatch for {chosen}: file {file_hash}, manifest {row['sha256']}"
            )
        replaced = repo / row["replaces"]["path"]
        if replaced.resolve() != default.resolve():
            raise SystemExit(
                f"override {chosen} replaces {row['replaces']['path']}, not {default}"
            )
        if not replaced.is_file():
            raise SystemExit(f"stale override {chosen}: lab-audio file missing at {replaced}")
        replaced_hash = sha256_file(replaced)
        expected = row["replaces"]["sha256"]
        if replaced_hash != expected:
            raise SystemExit(
                "stale override: "
                f"{replaced} sha256 {replaced_hash} does not match "
                f"overrides/manifest.json replaced sha256 {expected}. "
                "The lab-audio file changed after this override was cut."
            )
        item["source"] = str(chosen)
        item["audio_source"] = "override"
        item["replaced_path"] = row["replaces"]["path"]
        item["replaced_sha256"] = expected
    for key, row in index.items():
        if key not in claimed:
            override = repo / row["override_path"]
            if not override.is_file() or override.stat().st_size == 0:
                raise SystemExit(f"override manifest lists a missing file: {row['override_path']}")
            raise SystemExit(
                f"override manifest row {row['override_path']} did not match a package item"
            )


def manifest_entry(item: dict, built: dict) -> dict:
    """Row shape check_kids_audio.py accepts, plus the peak measurements."""
    row = {
        "voice": item["voice"],
        "file": item["file"],
        "duration": round(built["duration_sec"], 3),
        "size": built["size_bytes"],
        "sha256": built["sha256"],
        "sha256_source": built["sha256_source"],
        "true_peak_dbtp_before": built["true_peak_dbtp_before"],
        "true_peak_dbtp_after": built["true_peak_dbtp_after"],
        "lufs_before": built["lufs_before"],
        "lufs_after": built["lufs_after"],
        "treatment": built["treatment"],
        "source": item.get("audio_source", "lab-audio"),
        "source_path": built["source_path"],
    }
    if item.get("replaced_sha256"):
        row["replaced_path"] = item["replaced_path"]
        row["replaced_sha256"] = item["replaced_sha256"]
    if item["kind"] == "chapter":
        row["book"] = item["book_code"]
        row["chapter"] = item["chapter"]
    else:
        row["storyId"] = item["chapter"]
    if built.get("pcm_ceiling_db") is not None:
        row["pcm_ceiling_db"] = built["pcm_ceiling_db"]
        row["encode_attempts"] = built["encode_attempts"]
    return row


def process_item(job: dict) -> dict:
    """Measure one source file and either copy it or peak-limit it."""
    item = job["item"]
    repo = Path(job["repo"])
    dest = Path(job["dest"])
    try:
        src = Path(item["source"])
        info = probe_audio(src)
        if info["codec"] != "aac" or info["profile"] != "LC" or info["channels"] != 1 or info["sample_rate"] != 24000:
            raise RuntimeError(
                f"unexpected source format {info['codec']} {info['profile']} "
                f"{info['sample_rate']} Hz {info['channels']} ch"
            )
        if info["duration_sec"] <= 0.05 or src.stat().st_size == 0:
            raise RuntimeError("zero-length source")
        lufs_before, peak_before = measure_loudness(src)
        source_hash = sha256_file(src)
        bitrate = info["bitrate"] or 32000
        treatment = "copy"
        ceiling = None
        attempts = 0
        lufs_after, peak_after = lufs_before, peak_before
        if peak_before > TRIGGER_TRUE_PEAK_DBTP:
            treatment = "peak-limit"
            ceiling = INITIAL_PCM_CEILING_DB
            if not job["dry_run"]:
                if not job["fdkaac"]:
                    raise RuntimeError("fdkaac is required to peak-limit this file")
                last_peak = None
                for attempt in range(1, MAX_LIMIT_ATTEMPTS + 1):
                    attempts = attempt
                    peak_limit_encode(src, dest, bitrate, ceiling, job["fdkaac"])
                    lufs_after, peak_after = measure_loudness(dest)
                    last_peak = peak_after
                    if peak_after <= TARGET_TRUE_PEAK_DBTP:
                        break
                    overshoot = peak_after - TARGET_TRUE_PEAK_DBTP
                    # Some files overshoot by about 2 dB at the first ceiling
                    # (boy Psalms 31). Step down by at least 1.5 dB so the
                    # next encode is not a repeat of the same peak.
                    ceiling = round(ceiling - max(overshoot + 0.2, 1.5), 2)
                else:
                    raise RuntimeError(
                        f"true peak still {last_peak} dBTP after {MAX_LIMIT_ATTEMPTS} encodes"
                    )
        elif not job["dry_run"]:
            stream_copy(src, dest)
        if job["dry_run"]:
            size = src.stat().st_size
            output_hash = None
            duration = info["duration_sec"]
            lufs_after, peak_after = lufs_before, peak_before
        else:
            if not dest.exists():
                raise RuntimeError("output missing")
            size = dest.stat().st_size
            output_hash = sha256_file(dest)
            duration = probe_audio(dest)["duration_sec"]
            # Container duration can differ by a few hundred milliseconds because
            # AAC priming and the limiter lookahead are edited out of the m4a.
            # A decoded-length check on the hottest chapter showed the samples
            # still line up; this only rejects a real cut of half a second or more.
            if abs(duration - info["duration_sec"]) > 0.5:
                raise RuntimeError(
                    f"duration changed {info['duration_sec']:.3f} -> {duration:.3f}"
                )
        built = {
            "duration_sec": duration,
            "size_bytes": size,
            "sha256": output_hash,
            "sha256_source": source_hash,
            "true_peak_dbtp_before": peak_before,
            "true_peak_dbtp_after": peak_after,
            "lufs_before": lufs_before,
            "lufs_after": lufs_after,
            "treatment": treatment,
            "source_path": source_rel(repo, item["source"]),
            "pcm_ceiling_db": ceiling,
            "encode_attempts": attempts,
            "key": f"{item['voice']}:{item['kind']}:{item['book']}:{item['chapter']}",
        }
        return {"ok": True, "entry": manifest_entry(item, built), "item_key": built["key"]}
    except Exception as exc:  # noqa: BLE001 — one file must not kill the pool
        return {
            "ok": False,
            "item_key": f"{item['voice']}:{item['kind']}:{item['book']}:{item['chapter']}",
            "error": str(exc),
            "source": item.get("source"),
        }


def load_progress(path: Path) -> dict[str, dict]:
    done = {}
    if not path.exists():
        return done
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("ok"):
            entry = row.get("entry") or {}
            entry.setdefault("source", "lab-audio")
            row["entry"] = entry
            done[row["item_key"]] = row
    return done


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--source", type=Path, default=None)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only", default=None, help="comma-separated voice:book:chapter")
    parser.add_argument("--workers", type=int, default=max(1, min(4, os.cpu_count() or 1)))
    parser.add_argument("--fdkaac", default=None, help="path to fdkaac (default: on PATH)")
    parser.add_argument("--resume", action="store_true", help="skip items already in progress.jsonl")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    repo = (args.source or script_dir.parent).resolve()
    output = assert_safe_output(repo, args.output)
    output.mkdir(parents=True, exist_ok=True)
    if not shutil.which("ffprobe") or not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg and ffprobe must be on PATH")
    fdkaac = args.fdkaac or shutil.which("fdkaac")
    if not args.dry_run and not fdkaac:
        raise SystemExit(
            "fdkaac (libfdk-aac) is required for the peak-limit encode. "
            "ffmpeg's built-in AAC encoder does not hold -1.5 dBTP at this bitrate."
        )

    items, excluded = discover(repo)
    apply_overrides(repo, items)
    items = select_items(items, args.only)
    missing = [item for item in items if item.get("missing")]
    present = [item for item in items if not item.get("missing")]
    progress_path = output / "progress.jsonl"
    done = load_progress(progress_path) if args.resume else {}
    pending = []
    for item in present:
        key = f"{item['voice']}:{item['kind']}:{item['book']}:{item['chapter']}"
        if key in done and (args.dry_run or (output / item["dest_rel"]).exists()):
            continue
        pending.append(item)
    print(f"files {len(present)} pending {len(pending)} resumed {len(present) - len(pending)}", flush=True)

    results = dict(done)
    with progress_path.open("a") as sink, ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {}
        for item in pending:
            job = {
                "item": item,
                "repo": str(repo),
                "dest": str(output / item["dest_rel"]),
                "fdkaac": fdkaac,
                "dry_run": args.dry_run,
            }
            futures[pool.submit(process_item, job)] = item
        finished = 0
        for fut in as_completed(futures):
            result = fut.result()
            sink.write(json.dumps(result) + "\n")
            sink.flush()
            finished += 1
            if result["ok"]:
                results[result["item_key"]] = result
            else:
                results[result["item_key"]] = result
            if finished % 25 == 0 or finished == len(pending):
                print(f"built {finished}/{len(pending)} last {result['item_key']} ok {result['ok']}", flush=True)

    failures = [row for row in results.values() if not row.get("ok")]
    entries_by_key = {key: row["entry"] for key, row in results.items() if row.get("ok")}

    grouped: dict[tuple[str, str], list] = {}
    ordered_entries = []
    for item in present:
        key = f"{item['voice']}:{item['kind']}:{item['book']}:{item['chapter']}"
        entry = entries_by_key.get(key)
        if entry is None:
            continue
        grouped.setdefault((item["kind"], item["voice"]), []).append(entry)
        ordered_entries.append(entry)

    for (kind, voice), entries in grouped.items():
        folder = "KidsChapterAudio" if kind == "chapter" else "KidsStoryAudio"
        write_json(output / folder / voice / "manifest.json", {"voice": voice, "entries": entries})

    audio_bytes = sum(entry["size"] for entry in ordered_entries)
    limited = [entry for entry in ordered_entries if entry["treatment"] == "peak-limit"]
    copied = [entry for entry in ordered_entries if entry["treatment"] == "copy"]
    hot_after = [
        {"file": entry["source_path"], "true_peak_dbtp_after": entry["true_peak_dbtp_after"], "treatment": entry["treatment"]}
        for entry in ordered_entries
        if entry["treatment"] == "peak-limit" and entry["true_peak_dbtp_after"] > TARGET_TRUE_PEAK_DBTP
    ]
    # Copies are only the files that were already at or below -1.0 dBTP.
    # Some of those still sit above the -1.5 master target. They are reported,
    # and they are not treated as a failed encode.
    above_target_copied = [
        {"file": entry["source_path"], "true_peak_dbtp_after": entry["true_peak_dbtp_after"]}
        for entry in ordered_entries
        if entry["treatment"] == "copy" and entry["true_peak_dbtp_after"] > TARGET_TRUE_PEAK_DBTP
    ]
    lufs_deltas = [round(entry["lufs_after"] - entry["lufs_before"], 1) for entry in limited]
    full_package = args.only is None and not failures and not missing
    projected = audio_bytes + NON_AUDIO_BYTES if full_package else None
    over_budget = bool(full_package and audio_bytes > AUDIO_BUDGET_BYTES)
    summary = {
        "plan": PLAN_ID,
        "encoding": ENCODING,
        "description": (
            "All 66 books, both voices, plus stories 1-50. Files at or below "
            "-1.0 dBTP are stream-copied. Files above -1.0 dBTP are true-peak "
            "limited and re-encoded as AAC-LC mono 24 kHz at the source bitrate. "
            "The encoded master target is -1.5 dBTP."
        ),
        "dry_run": args.dry_run,
        "subset": args.only,
        "source_commit": git_head(repo),
        "trigger_true_peak_dbtp": TRIGGER_TRUE_PEAK_DBTP,
        "target_true_peak_dbtp": TARGET_TRUE_PEAK_DBTP,
        "initial_pcm_ceiling_db": INITIAL_PCM_CEILING_DB,
        "counts": {
            "files": len(ordered_entries),
            "missing": len(missing),
            "failures": len(failures),
            "peak_limited": len(limited),
            "stream_copied": len(copied),
            "chapters_per_voice": sum(1 for item in present if item["kind"] == "chapter" and item["voice"] == "girl" and f"girl:chapter:{item['book']}:{item['chapter']}" in entries_by_key),
            "stories_per_voice": sum(1 for item in present if item["kind"] == "story" and item["voice"] == "girl" and f"girl:story:{item['book']}:{item['chapter']}" in entries_by_key),
        },
        "audio_bytes": audio_bytes,
        "audio_budget_bytes": AUDIO_BUDGET_BYTES,
        "app_limit_bytes": APP_LIMIT_BYTES,
        "non_audio_allowance_bytes": NON_AUDIO_BYTES,
        "margin_bytes": MARGIN_BYTES,
        "projected_bundle_bytes": projected,
        "headroom_under_4gib_bytes": (APP_LIMIT_BYTES - projected) if projected is not None else None,
        "within_audio_budget": (not over_budget) if full_package else None,
        "true_peak_after_max": max((entry["true_peak_dbtp_after"] for entry in ordered_entries), default=None),
        "peak_limited_still_above_target": hot_after,
        "copied_above_target": above_target_copied,
        "lufs_delta_limited": {
            "min": min(lufs_deltas) if lufs_deltas else None,
            "max": max(lufs_deltas) if lufs_deltas else None,
            "mean": round(sum(lufs_deltas) / len(lufs_deltas), 3) if lufs_deltas else None,
        },
        "excluded_extra_audio": excluded if args.only is None else [],
        "missing": [
            {"voice": item["voice"], "kind": item["kind"], "book": item["book"], "chapter": item["chapter"]}
            for item in missing
        ],
        "failures": [{"item": row["item_key"], "error": row["error"]} for row in failures],
    }
    write_json(output / "package-summary.json", summary)
    print(json.dumps({
        "audio_bytes": audio_bytes,
        "files": len(ordered_entries),
        "peak_limited": len(limited),
        "stream_copied": len(copied),
        "failures": len(failures),
        "true_peak_after_max": summary["true_peak_after_max"],
        "within_audio_budget": summary["within_audio_budget"],
        "output": str(output),
    }, indent=2))
    if missing or failures or over_budget or hot_after:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
