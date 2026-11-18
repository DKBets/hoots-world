#!/usr/bin/env python3
"""Dual-model machine QA for girl kids-Bible Old Testament chapter audio.

Copied from qa/boy_machine_qa.py on cursor/boy-machine-qa-7af7 (PR #4, ee470c9).
Compares each kids-bible-audio/sample1/<Book>/<chapter>.m4a to the retold kids
text in longroad-ios (branch release-1.2-build9, BibleApp/Resources/KidsBible).
Two faster-whisper models (small.en and medium.en, int8, CPU) each get a
normalized word alignment. A chapter can PASS only when both models agree
there is no missing, invented, or repeated passage. One model is never enough.

Where the two models disagree, both transcribe that span of the audio again.
The slice is the tie-break: both hearing the defect fails the chapter; both
hearing the source words clears that span. A still-split slice stays uncertain.

Reproduce:
  pip install faster-whisper
  # source text, read-only clone (this script does not modify it):
  git clone --depth 1 --branch release-1.2-build9 \\
      https://github.com/DKBets/longroad-ios.git /tmp/longroad-ios
  python3 qa/girl_ot_machine_qa.py \\
      --source-root /tmp/longroad-ios/BibleApp/Resources/KidsBible \\
      --max-chapters 10 --commit-every 10

Needs ffmpeg on PATH. Resumes from the jsonl. Does not write or rewrite audio.
Chapters already PASS in qa/*.jsonl on origin/lab-audio are skipped.

Decision rules (also written into the summary):
  * Content spans: more than 4 inserted, missing, or repeated words.
    A run of substitutions that are only proper names is name noise, not a
    span defect, unless both models heard the same wrong words.
  * Coverage: fraction of source words the model matched. PASS needs both
    models at or above 0.96. Both under 0.90 fails (they agree the reading
    does not cover the chapter). Anything between, or a split, is UNSURE
    because coverage is unclear.
  * Paraphrase drift: both models substitute more than 8% of non-name words.
    Raw WER is recorded but is not the pass line. Biblical names move WER
    a lot and the two models miss different names, so a WER ceiling would
    either false-fail genealogies or hide a real rewording.
  * Waveform (not a model vote): interior silence longer than 3 seconds, and
    a sample-level loop (3 seconds at correlation >= 0.97).
  * Production / non-story phrases ("take two", "thanks for watching", ...)
    fail only when both transcripts contain the phrase and the source does
    not. One model alone is UNSURE (a known hallucination pattern).
  * Truncation: both models drop the last 8 or more source words, or both
    report coverage under 0.90 and the file is shorter than 0.70 of the
    expected reading time.
  * Expected duration is source words / 2.5 words per second (Matthew 3
    reads at about 2.6). The ratio is always recorded. A slow or fast
    reading with the words intact is not, by itself, a content defect.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
AUDIO_ROOT_DEFAULT = REPO / "kids-bible-audio" / "sample1"
OUT_DEFAULT = REPO / "qa" / "girl-ot-machine-qa-2026-11-17.jsonl"
SUMMARY_DEFAULT = REPO / "qa" / "girl-ot-machine-qa-summary.md"

SOURCE_REF = "longroad-ios release-1.2-build9 BibleApp/Resources/KidsBible"
WORDS_PER_SEC = 2.5
SPAN_MIN = 5  # "over 4 words"
COVERAGE_PASS = 0.96
COVERAGE_FAIL = 0.90
NONNAME_SUB_PARAPHRASE = 0.08
WER_BACKSTOP = 0.35
SILENCE_SEC = 3.0
LOOP_CORR = 0.97
LOOP_WIN_SEC = 3.0
TAIL_WORDS = 8
DURATION_SHORT = 0.70
DURATION_LONG = 1.45

SMALL = "small.en"
MEDIUM = "medium.en"
SLICE_CONFIRM = 0.75
SLICE_REFUTE = 0.50
MAX_SLICE_CHECKS = 3

# Girl OT has no re-record exclusion. Pass rows on origin/lab-audio are skipped at runtime.
SKIP = set()
PRIORITY_ADD = []
SUSPECTS = []
LAB_PASS: set[tuple[str, int]] = set()

CANON = [
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua", "Judges",
    "Ruth", "1 Samuel", "2 Samuel", "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles",
    "Ezra", "Nehemiah", "Esther", "Job", "Psalms", "Proverbs", "Ecclesiastes",
    "Song of Solomon", "Isaiah", "Jeremiah", "Lamentations", "Ezekiel", "Daniel",
    "Hosea", "Joel", "Amos", "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk",
    "Zephaniah", "Haggai", "Zechariah", "Malachi", "Matthew", "Mark", "Luke", "John",
    "Acts", "Romans", "1 Corinthians", "2 Corinthians", "Galatians", "Ephesians",
    "Philippians", "Colossians", "1 Thessalonians", "2 Thessalonians", "1 Timothy",
    "2 Timothy", "Titus", "Philemon", "Hebrews", "James", "1 Peter", "2 Peter",
    "1 John", "2 John", "3 John", "Jude", "Revelation",
]
CANON_INDEX = {name: i for i, name in enumerate(CANON)}
NT_START = CANON_INDEX["Matthew"]
NT_PRIORITY = {"John": 0, "Romans": 1, "1 Corinthians": 2}

CUES = [
    "take two", "take 2", "take one", "take three", "second take", "another take",
    "from the top", "start over", "start again", "let me start again",
    "lets start again", "let me try that again", "lets try that again",
    "let me read that again", "lets read that again", "read that again",
    "mic check", "sound check", "this is a test", "thanks for watching",
    "please subscribe", "subtitles by", "end of recording", "amara org",
]

_ONES = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen"
).split()
_TENS = "twenty thirty forty fifty sixty seventy eighty ninety".split()
NUM_WORD = {}
for _i, _w in enumerate(_ONES):
    NUM_WORD[_w] = str(_i)
for _i, _w in enumerate(_TENS, start=2):
    NUM_WORD[_w] = str(_i * 10)

FUNC = {
    "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with", "from",
    "by", "as", "at", "it", "he", "she", "they", "we", "you", "i", "his", "her",
    "their", "them", "this", "that", "these", "those", "then", "so", "when",
    "who", "what", "which", "there", "was", "were", "is", "are", "be", "been",
    "not", "no", "into", "over", "after", "before", "about", "than", "the",
    "his", "him", "had", "have", "has", "did", "do", "does",
}

TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:['’][A-Za-z]+)?")
ORDINALS = {"1": "first", "2": "second", "3": "third"}


def tokenize(text: str) -> list[tuple[str, str]]:
    out = []
    for raw in TOKEN_RE.findall(text or ""):
        norm = raw.lower().replace("'", "").replace("’", "")
        norm = re.sub(r"[^a-z0-9]", "", norm)
        if norm:
            out.append((norm, raw))
    return out


def one_edit(a: str, b: str) -> bool:
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la > lb:
        a, b = b, a
        la, lb = lb, la
    i = j = edits = 0
    while i < la and j < lb:
        if a[i] == b[j]:
            i += 1
            j += 1
        else:
            edits += 1
            if edits > 1:
                return False
            if la == lb:
                i += 1
                j += 1
            else:
                j += 1
    return True


def tokens_equal(a: str, b: str) -> bool:
    if a == b:
        return True
    na, nb = NUM_WORD.get(a), NUM_WORD.get(b)
    if na is not None and na == b:
        return True
    if nb is not None and nb == a:
        return True
    if na is not None and nb is not None and na == nb:
        return True
    if len(a) >= 7 and len(b) >= 7 and a[0] == b[0] and abs(len(a) - len(b)) <= 1 and one_edit(a, b):
        return True
    return False


def book_aliases(book: str) -> list[list[str]]:
    forms = [book.lower()]
    parts = book.split()
    if parts and parts[0] in ORDINALS:
        forms.append(ORDINALS[parts[0]] + " " + " ".join(parts[1:]).lower())
    if book == "Psalms":
        forms.append("psalm")
    if book == "Song of Solomon":
        forms.append("song of songs")
    if book == "Revelation":
        forms.append("the revelation")
    out = []
    for form in forms:
        out.append(form.split())
    return out


def number_forms(n: int) -> list[list[str]]:
    forms = [[str(n)]]
    if n < 20:
        forms.append([_ONES[n]])
        return forms
    if n < 100:
        tens, rest = divmod(n, 10)
        if rest == 0:
            forms.append([_TENS[tens - 2]])
        else:
            forms.append([_TENS[tens - 2], _ONES[rest]])
            forms.append([f"{_TENS[tens - 2]}{_ONES[rest]}"])
        return forms
    if n == 100:
        return [[str(n)], ["one", "hundred"], ["a", "hundred"]]
    tail = number_forms(n - 100)
    out = [[str(n)]]
    for part in tail:
        if part == [str(n - 100)]:
            continue
        out.append(["one", "hundred"] + part)
        out.append(["one", "hundred", "and"] + part)
        out.append(["a", "hundred"] + part)
    return out


def _contains(hay: list[str], needle: list[str]) -> bool:
    span = len(needle)
    if span == 0 or len(hay) < span:
        return False
    for i in range(len(hay) - span + 1):
        if hay[i : i + span] == needle:
            return True
    return False


def header_cut(norms: list[str], book: str, chapter: int) -> int:
    """How many leading tokens are a book/chapter announcement, or 0."""
    head = norms[:18]
    aliases = book_aliases(book)
    for form in number_forms(chapter):
        flen = len(form)
        for i in range(1, len(head) - flen + 1):
            if head[i : i + flen] != form:
                continue
            if head[i - 1] not in ("chapter", "chapters"):
                continue
            pre = head[: i - 1]
            if any(_contains(pre, alias) for alias in aliases):
                return i + flen
    return 0


def heard_chapter(norms: list[str], book: str) -> int | None:
    head = norms[:18]
    aliases = book_aliases(book)
    if not any(_contains(head, alias) for alias in aliases):
        return None
    for i, tok in enumerate(head[:-1]):
        if tok not in ("chapter", "chapters"):
            continue
        nxt = head[i + 1]
        if nxt.isdigit():
            return int(nxt)
        if nxt in NUM_WORD and NUM_WORD[nxt].isdigit() and int(NUM_WORD[nxt]) < 20:
            return int(NUM_WORD[nxt])
        if i + 2 < len(head):
            pair = nxt + head[i + 2]
            # twenty three
            if nxt in _TENS and head[i + 2] in _ONES[1:10]:
                return int(NUM_WORD[nxt]) + int(NUM_WORD[head[i + 2]])
            if pair in NUM_WORD:
                return int(NUM_WORD[pair])
        if nxt in NUM_WORD and int(NUM_WORD[nxt]) >= 20:
            return int(NUM_WORD[nxt])
    return None


def align(ref: list[str], hyp: list[str]) -> list[tuple[str, int | None, int | None]]:
    n, m = len(ref), len(hyp)
    if n == 0 and m == 0:
        return []
    bp = bytearray((n + 1) * (m + 1))
    width = m + 1

    def at(i: int, j: int) -> int:
        return i * width + j

    prev = list(range(m + 1))
    for j in range(1, m + 1):
        bp[at(0, j)] = 2
    for i in range(1, n + 1):
        bp[at(i, 0)] = 1
    cur = [0] * (m + 1)
    for i in range(1, n + 1):
        cur[0] = i
        ri = ref[i - 1]
        for j in range(1, m + 1):
            same = tokens_equal(ri, hyp[j - 1])
            cost_sub = prev[j - 1] + (0 if same else 1)
            cost_del = prev[j] + 1
            cost_ins = cur[j - 1] + 1
            if cost_sub <= cost_del and cost_sub <= cost_ins:
                cur[j] = cost_sub
                bp[at(i, j)] = 0 if same else 3
            elif cost_del <= cost_ins:
                cur[j] = cost_del
                bp[at(i, j)] = 1
            else:
                cur[j] = cost_ins
                bp[at(i, j)] = 2
        prev, cur = cur, prev
    i, j = n, m
    ops: list[tuple[str, int | None, int | None]] = []
    while i > 0 or j > 0:
        code = bp[at(i, j)]
        if i > 0 and j > 0 and code in (0, 3):
            ops.append(("eq" if code == 0 else "sub", i - 1, j - 1))
            i -= 1
            j -= 1
        elif i > 0 and (j == 0 or code == 1):
            ops.append(("del", i - 1, None))
            i -= 1
        else:
            ops.append(("ins", None, j - 1))
            j -= 1
    ops.reverse()
    return ops


def _quote(tokens: list[tuple], idxs: list[int], limit: int = 60) -> str:
    words = []
    seen_raw = set()
    for i in idxs:
        raw = tokens[i][1]
        if not raw or raw in seen_raw and tokens[i][0] not in raw.lower():
            raw = tokens[i][0]
        words.append(raw)
        if len(words) >= limit:
            break
    text = " ".join(words)
    if len(idxs) > limit:
        text += " …"
    return text


def _span_time(hyp: list[tuple], idxs: list[int]) -> tuple[float | None, float | None]:
    if not idxs:
        return None, None
    starts = [hyp[i][2] for i in idxs if len(hyp[i]) > 2 and hyp[i][2] is not None]
    ends = [hyp[i][3] for i in idxs if len(hyp[i]) > 3 and hyp[i][3] is not None]
    if not starts:
        return None, None
    return round(min(starts), 2), round(max(ends) if ends else min(starts), 2)


def name_set(verses: list[tuple[int, str]]) -> set[str]:
    names = set()
    for _num, text in verses:
        raws = TOKEN_RE.findall(text or "")
        for i, raw in enumerate(raws):
            if not raw[:1].isupper():
                continue
            norm = raw.lower().replace("'", "").replace("’", "")
            norm = re.sub(r"[^a-z0-9]", "", norm)
            if not norm or norm in FUNC or norm in NUM_WORD:
                continue
            prev = raws[i - 1] if i else ""
            sentence_start = i == 0 or prev.endswith((".", "!", "?"))
            # Sentence-initial function-looking words stay out via FUNC.
            # Keep sentence-initial capitals that are not function words: John, God, Lord.
            if sentence_start or True:
                names.add(norm)
    return names


def extract_error_spans(ops, ref, hyp, names: set[str]) -> tuple[list[dict], list[dict], list[dict]]:
    missing, inserted, name_spans = [], [], []
    group: list[tuple] = []

    def flush(group: list[tuple]) -> None:
        if not group:
            return
        ref_idx = [g[1] for g in group if g[1] is not None]
        hyp_idx = [g[2] for g in group if g[2] is not None]
        only_subs = all(g[0] == "sub" for g in group)
        if only_subs and ref_idx and all(ref[i][0] in names for i in ref_idx):
            start, end = _span_time(hyp, hyp_idx)
            name_spans.append(
                {
                    "verse": ref[ref_idx[0]][2],
                    "start": start,
                    "end": end,
                    "ref_quote": _quote(ref, ref_idx),
                    "hyp_quote": _quote(hyp, hyp_idx),
                    "ref_norm": " ".join(ref[i][0] for i in ref_idx),
                    "hyp_norm": " ".join(hyp[i][0] for i in hyp_idx),
                    "words": len(ref_idx),
                }
            )
            return
        if len(ref_idx) >= SPAN_MIN and any(g[0] in ("del", "sub") for g in group):
            start, end = _span_time(hyp, hyp_idx)
            if start is None and hyp_idx:
                start, end = _span_time(hyp, hyp_idx)
            # Deletions have no hyp index. Use the nearest following hyp time later.
            missing.append(
                {
                    "kind": "missing",
                    "verse": ref[ref_idx[0]][2],
                    "start": start,
                    "end": end,
                    "quote": _quote(ref, ref_idx),
                    "words": len(ref_idx),
                    "ref_index": ref_idx[0],
                }
            )
        if len(hyp_idx) >= SPAN_MIN and any(g[0] in ("ins", "sub") for g in group):
            start, end = _span_time(hyp, hyp_idx)
            verse = None
            if ref_idx:
                verse = ref[ref_idx[0]][2]
            inserted.append(
                {
                    "kind": "inserted",
                    "verse": verse,
                    "start": start,
                    "end": end,
                    "quote": _quote(hyp, hyp_idx),
                    "words": len(hyp_idx),
                    "hyp_index": hyp_idx[0],
                }
            )

    for op in ops:
        if op[0] == "eq":
            flush(group)
            group = []
        else:
            group.append(op)
    flush(group)
    return missing, inserted, name_spans


def fill_deletion_times(missing: list[dict], ops, hyp) -> None:
    """Put a deletion on the clock using the next heard word."""
    # Map ref index -> following hyp start.
    next_time = None
    ref_time: dict[int, float] = {}
    for kind, ri, hi in reversed(ops):
        if hi is not None and len(hyp[hi]) > 2 and hyp[hi][2] is not None:
            next_time = hyp[hi][2]
        if ri is not None and next_time is not None:
            ref_time[ri] = next_time
    for span in missing:
        if span["start"] is None:
            t = ref_time.get(span["ref_index"])
            if t is not None:
                span["start"] = round(t, 2)
                span["end"] = round(t, 2)


def repeated_spans(hyp, ref) -> list[dict]:
    h = [t[0] for t in hyp]
    r = [t[0] for t in ref]
    if len(h) < SPAN_MIN:
        return []
    ref_counts = Counter(tuple(r[i : i + SPAN_MIN]) for i in range(len(r) - SPAN_MIN + 1))
    running: Counter = Counter()
    extra_at = []
    for i in range(len(h) - SPAN_MIN + 1):
        gram = tuple(h[i : i + SPAN_MIN])
        running[gram] += 1
        # A phrase said once more than the source is a repeat. The first time a
        # phrase appears only in the transcript is an insertion, not a repeat.
        if running[gram] > ref_counts.get(gram, 0) and running[gram] > 1:
            extra_at.append(i)
    if not extra_at:
        return []
    spans = []
    start = extra_at[0]
    end = extra_at[0] + SPAN_MIN
    prev = extra_at[0]
    for i in extra_at[1:]:
        if i <= prev + 1:
            end = i + SPAN_MIN
            prev = i
            continue
        spans.append((start, end))
        start = i
        end = i + SPAN_MIN
        prev = i
    spans.append((start, end))
    out = []
    for a, b in spans:
        if b - a < SPAN_MIN:
            continue
        idxs = list(range(a, b))
        st, en = _span_time(hyp, idxs)
        out.append(
            {
                "kind": "repeated",
                "verse": None,
                "start": st,
                "end": en,
                "quote": _quote(hyp, idxs),
                "words": b - a,
            }
        )
    return out


def find_cues(hyp, ref) -> list[dict]:
    h = [t[0] for t in hyp]
    r = [t[0] for t in ref]
    rjoin = " ".join(r)
    found = []
    seen = set()
    for phrase in CUES:
        parts = phrase.split()
        key = tuple(parts)
        if key in seen:
            continue
        plen = len(parts)
        in_ref = phrase in rjoin and _contains(r, parts)
        if in_ref:
            continue
        for i in range(len(h) - plen + 1):
            if h[i : i + plen] == parts:
                seen.add(key)
                idxs = list(range(i, i + plen))
                st, en = _span_time(hyp, idxs)
                found.append(
                    {
                        "kind": "cue",
                        "verse": None,
                        "start": st,
                        "end": en,
                        "quote": phrase,
                        "words": plen,
                    }
                )
                break
    return found


def phrase_in_source_guard(cues, ref_norms_joined: str) -> list[dict]:
    return [c for c in cues if c["quote"] not in ref_norms_joined]


def tail_deleted(ops, ref_len: int, n: int = TAIL_WORDS) -> int:
    """How many of the final source words are deletes, walking from the end.
    Stops at the first real match. Substitutions at the tail count as missing.
    """
    deleted = 0
    for kind, ri, _hi in reversed(ops):
        if ri is None:
            continue
        if kind == "eq":
            break
        if kind in ("del", "sub"):
            deleted += 1
        if deleted >= n and ri <= ref_len - n:
            break
    return deleted


def nonname_sub_count(ops, ref, names: set[str]) -> int:
    count = 0
    for kind, ri, _hi in ops:
        if kind == "sub" and ri is not None and ref[ri][0] not in names:
            count += 1
    return count


def coverage_of(ops, ref_len: int) -> float:
    if ref_len == 0:
        return 1.0
    matched = sum(1 for kind, ri, _hi in ops if kind == "eq" and ri is not None)
    return matched / ref_len


def wer_of(ops, ref_len: int) -> tuple[float, int, int, int]:
    sub = sum(1 for k, _, _ in ops if k == "sub")
    delete = sum(1 for k, _, _ in ops if k == "del")
    ins = sum(1 for k, _, _ in ops if k == "ins")
    if ref_len == 0:
        return (1.0 if ops else 0.0), sub, delete, ins
    return (sub + delete + ins) / ref_len, sub, delete, ins


def analyze_hyp(hyp, verses, note: str, book: str, chapter: int, names: set[str]) -> dict:
    """Align hyp to the verses, or to verses plus the kids note if that is what was read."""
    norms = [t[0] for t in hyp]
    cut = header_cut(norms, book, chapter)
    announced = heard_chapter(norms, book)
    candidates = []
    options = [(hyp, False)]
    if cut:
        options.append((hyp[cut:], True))
    for tokens, stripped in options:
        for use_note in (False, True) if note else (False,):
            ref = []
            for num, text in verses:
                for norm, raw in tokenize(text):
                    ref.append((norm, raw, num))
            if use_note:
                for norm, raw in tokenize(note):
                    ref.append((norm, raw, 0))
            ops = align([t[0] for t in ref], [t[0] for t in tokens])
            wer, _s, _d, _i = wer_of(ops, len(ref))
            candidates.append((wer, use_note, stripped, ref, tokens, ops))
    # Prefer the lower WER. On a near tie, prefer verses-only (the note is optional).
    candidates.sort(key=lambda c: (round(c[0], 4), c[1], c[2]))
    best_wer = candidates[0][0]
    near = [c for c in candidates if c[0] <= best_wer + 0.01]
    near.sort(key=lambda c: (c[1], c[0], c[2]))
    _wer, use_note, stripped, ref, tokens, ops = near[0]
    # Score coverage against the verse words only, even if the note was spoken.
    verse_len = sum(1 for t in ref if t[2] != 0)
    verse_ops_ref = [i for i, t in enumerate(ref) if t[2] != 0]
    # Recompute verse-only coverage/WER by ignoring note-region ops.
    if use_note:
        note_start = verse_len
        verse_ops = []
        for kind, ri, hi in ops:
            if ri is not None and ri >= note_start:
                continue
            verse_ops.append((kind, ri, hi))
        # Insertions that sit inside the note (after the last verse match) are not verse errors.
        wer, sub, delete, ins = wer_of(verse_ops, verse_len)
        cov = coverage_of(verse_ops, verse_len)
        missing, inserted, name_spans = extract_error_spans(verse_ops, ref, tokens, names)
        # Drop inserted spans whose words are the kids note (hyp aligned into the note).
        reps = repeated_spans(tokens, ref)
        cues = find_cues(tokens, ref)
        tail = tail_deleted(verse_ops, verse_len)
        nonname = nonname_sub_count(verse_ops, ref, names)
        used_ops = verse_ops
    else:
        wer, sub, delete, ins = wer_of(ops, len(ref))
        cov = coverage_of(ops, len(ref))
        missing, inserted, name_spans = extract_error_spans(ops, ref, tokens, names)
        reps = repeated_spans(tokens, ref)
        cues = find_cues(tokens, ref)
        tail = tail_deleted(ops, len(ref))
        nonname = nonname_sub_count(ops, ref, names)
        used_ops = ops
        verse_len = len(ref)
    fill_deletion_times(missing, used_ops, tokens)
    # Attach verse numbers to insertions and repeats from the nearest source word.
    ref_at_hyp = _hyp_verse(used_ops, ref, len(tokens))
    for span in inserted + reps + cues:
        if span.get("verse") in (None, 0) and span.get("start") is not None:
            span["verse"] = _verse_at_time(tokens, ref_at_hyp, span["start"])
    wrong = None
    if announced is not None and announced != chapter:
        wrong = {
            "kind": "wrong_chapter",
            "verse": None,
            "start": 0.0,
            "end": None,
            "quote": f"announcement says chapter {announced}",
            "words": 0,
        }
    return {
        "wer": round(wer, 4),
        "coverage": round(cov, 4),
        "substitutions": sub,
        "deletions": delete,
        "insertions": ins,
        "ref_words": verse_len,
        "hyp_words": len(tokens),
        "nonname_sub_rate": round(nonname / verse_len, 4) if verse_len else 0.0,
        "kids_note_spoken": bool(use_note),
        "header_stripped": bool(stripped),
        "announced_chapter": announced,
        "tail_missing_words": tail,
        "truncation": tail >= TAIL_WORDS,
        "missing_spans": missing,
        "inserted_spans": inserted,
        "repeated_spans": reps,
        "name_spans": [s for s in name_spans if s["words"] >= SPAN_MIN],
        "cues": cues,
        "wrong_chapter": wrong,
    }


def _hyp_verse(ops, ref, n_hyp: int) -> list[int | None]:
    verse_at: list[int | None] = [None] * n_hyp
    last = None
    for kind, ri, hi in ops:
        if ri is not None and ref[ri][2]:
            last = ref[ri][2]
        if hi is not None:
            verse_at[hi] = last
    prev = None
    for i, v in enumerate(verse_at):
        if v is None:
            verse_at[i] = prev
        else:
            prev = v
    return verse_at


def _verse_at_time(hyp, verse_at, t: float) -> int | None:
    best = None
    best_d = 1e9
    for i, tok in enumerate(hyp):
        if len(tok) < 3 or tok[2] is None:
            continue
        d = abs(tok[2] - t)
        if d < best_d:
            best_d = d
            best = verse_at[i] if i < len(verse_at) else None
    return best


def text_defects(rep: dict) -> list[dict]:
    items = []
    items.extend(rep["missing_spans"])
    items.extend(rep["inserted_spans"])
    items.extend(rep["repeated_spans"])
    items.extend(rep["cues"])
    if rep.get("wrong_chapter"):
        items.append(rep["wrong_chapter"])
    if rep.get("truncation"):
        items.append(
            {
                "kind": "truncation",
                "verse": None,
                "start": None,
                "end": None,
                "quote": f"last {rep['tail_missing_words']} source words missing",
                "words": rep["tail_missing_words"],
            }
        )
    return items


def _quote_overlap(a: dict, b: dict) -> bool:
    wa = [w for w in (a.get("quote") or "").lower().split() if w not in FUNC and len(w) > 2]
    wb = [w for w in (b.get("quote") or "").lower().split() if w not in FUNC and len(w) > 2]
    if len(wa) < 3 or len(wb) < 3:
        return False
    inter = len(set(wa) & set(wb))
    return inter >= 3 and inter / min(len(set(wa)), len(set(wb))) >= 0.34


def _overlap(a: dict, b: dict) -> bool:
    if a.get("kind") != b.get("kind") and not (
        {a.get("kind"), b.get("kind")} <= {"inserted", "missing", "repeated"}
    ):
        return False
    if a.get("kind") == "cue" and b.get("kind") == "cue" and a.get("quote") == b.get("quote"):
        return True
    if a.get("kind") == "wrong_chapter" and b.get("kind") == "wrong_chapter":
        return True
    if a.get("kind") == "truncation" and b.get("kind") == "truncation":
        return True
    # Same clock time is not enough: both models often flag some span near the
    # start. The quoted words have to be the same defect.
    if not _quote_overlap(a, b):
        return False
    va, vb = a.get("verse"), b.get("verse")
    sa, sb = a.get("start"), b.get("start")
    same_verse = va and vb and abs(int(va) - int(vb)) <= 1
    same_time = sa is not None and sb is not None and abs(float(sa) - float(sb)) <= 12
    both_opening = (sa is None or sa <= 30) and (sb is None or sb <= 30)
    return bool(same_verse or same_time or both_opening)


def agreed_pairs(left: list[dict], right: list[dict]) -> list[tuple[dict, dict]]:
    used = set()
    pairs = []
    for a in left:
        for j, b in enumerate(right):
            if j in used:
                continue
            if _overlap(a, b):
                used.add(j)
                pairs.append((a, b))
                break
    return pairs


def agreed_name_errors(s: dict, m: dict) -> list[dict]:
    found = []
    used = set()
    for a in s.get("name_spans") or []:
        for j, b in enumerate(m.get("name_spans") or []):
            if j in used:
                continue
            if a.get("verse") != b.get("verse"):
                continue
            if a.get("hyp_norm") and a["hyp_norm"] == b.get("hyp_norm") and a["hyp_norm"] != a.get("ref_norm"):
                used.add(j)
                found.append(a)
                break
    return found


def decide(small: dict | None, medium: dict | None, acoustic: dict) -> tuple[str, list[str], list[dict]]:
    reasons: list[str] = []
    quotes: list[dict] = []
    if small is None or medium is None:
        return "UNSURE", ["one model did not finish; a single model cannot pass"], quotes

    for gap in acoustic.get("silence") or []:
        reasons.append(
            f"interior silence {gap['start']:.2f}-{gap['end']:.2f}s ({gap['seconds']:.1f}s)"
        )
        quotes.append(
            {
                "kind": "silence",
                "verse": gap.get("verse"),
                "time": gap["start"],
                "time_end": gap["end"],
                "quote": gap.get("context") or "silence",
                "models": "waveform",
            }
        )
    for loop in acoustic.get("loops") or []:
        reasons.append(
            f"audio loop at {loop['start']:.2f}s repeating near {loop['match_start']:.2f}s "
            f"(corr {loop['corr']:.3f})"
        )
        quotes.append(
            {
                "kind": "loop",
                "verse": loop.get("verse"),
                "time": loop["start"],
                "time_end": loop.get("match_start"),
                "quote": loop.get("context") or "repeated audio",
                "models": "waveform",
            }
        )

    s_def = text_defects(small)
    m_def = text_defects(medium)
    pairs = agreed_pairs(s_def, m_def)
    for a, b in pairs:
        reasons.append(f"both models: {a['kind']} verse {a.get('verse')} at {a.get('start')}")
        quotes.append(
            {
                "kind": a["kind"],
                "verse": a.get("verse") or b.get("verse"),
                "time": a.get("start") if a.get("start") is not None else b.get("start"),
                "time_end": a.get("end") if a.get("end") is not None else b.get("end"),
                "quote": a.get("quote") or b.get("quote"),
                "words": a.get("words") or b.get("words"),
                "models": "small.en+medium.en",
            }
        )
    name_hits = agreed_name_errors(small, medium)
    for hit in name_hits:
        reasons.append(f"both models heard the same wrong names at verse {hit.get('verse')}")
        quotes.append(
            {
                "kind": "names",
                "verse": hit.get("verse"),
                "time": hit.get("start"),
                "time_end": hit.get("end"),
                "quote": f"source '{hit.get('ref_quote')}' heard '{hit.get('hyp_quote')}'",
                "models": "small.en+medium.en",
            }
        )

    only_s = [a for a in s_def if not any(a is p[0] for p in pairs)]
    only_m = [b for b in m_def if not any(b is p[1] for p in pairs)]
    # identity of dicts in pairs is the same objects, so `is` works.

    paraphrase = (
        small["nonname_sub_rate"] > NONNAME_SUB_PARAPHRASE
        and medium["nonname_sub_rate"] > NONNAME_SUB_PARAPHRASE
    )
    paraphrase_split = (small["nonname_sub_rate"] > NONNAME_SUB_PARAPHRASE) != (
        medium["nonname_sub_rate"] > NONNAME_SUB_PARAPHRASE
    )
    if paraphrase:
        reasons.append(
            f"paraphrase-level drift (non-name substitution "
            f"small {small['nonname_sub_rate']:.3f}, medium {medium['nonname_sub_rate']:.3f})"
        )
        quotes.append(
            {
                "kind": "paraphrase",
                "verse": None,
                "time": None,
                "time_end": None,
                "quote": "scattered wording does not match the source",
                "models": "small.en+medium.en",
            }
        )

    both_low = small["coverage"] < COVERAGE_FAIL and medium["coverage"] < COVERAGE_FAIL
    both_high = small["coverage"] >= COVERAGE_PASS and medium["coverage"] >= COVERAGE_PASS
    if both_low:
        reasons.append(
            f"coverage low on both models (small {small['coverage']:.3f}, medium {medium['coverage']:.3f})"
        )
    coverage_unclear = not both_low and not both_high

    wer_both_bad = small["wer"] > WER_BACKSTOP and medium["wer"] > WER_BACKSTOP
    wer_split = (small["wer"] > WER_BACKSTOP) != (medium["wer"] > WER_BACKSTOP)
    if wer_both_bad:
        reasons.append(f"WER backstop both models (small {small['wer']:.3f}, medium {medium['wer']:.3f})")

    if reasons:
        # Waveform or agreed text defects.
        # Coverage-unclear still forces UNSURE when the only agreement is a soft one
        # and models also disagree. Agreed hard defects stay FAIL.
        hard = bool(pairs or name_hits or acoustic.get("silence") or acoustic.get("loops") or paraphrase or both_low or wer_both_bad)
        if hard and not (only_s or only_m or paraphrase_split or wer_split or coverage_unclear):
            return "FAIL", reasons, quotes
        if hard and (pairs or name_hits or acoustic.get("silence") or acoustic.get("loops") or paraphrase or both_low or wer_both_bad):
            # They agree something is wrong, even if extra one-sided noise exists.
            if only_s or only_m:
                reasons.append("models also disagree on other spans; agreed defects still fail the chapter")
            return "FAIL", reasons, quotes
        return "UNSURE", reasons, quotes

    if only_s or only_m or paraphrase_split or wer_split or coverage_unclear:
        if only_s:
            reasons.append(f"small.en only: {only_s[0]['kind']} '{only_s[0].get('quote')}'")
            quotes.append(_one_sided(only_s[0], SMALL))
        if only_m:
            reasons.append(f"medium.en only: {only_m[0]['kind']} '{only_m[0].get('quote')}'")
            quotes.append(_one_sided(only_m[0], MEDIUM))
        if coverage_unclear:
            reasons.append(
                f"coverage unclear (small {small['coverage']:.3f}, medium {medium['coverage']:.3f}; "
                f"pass needs both >= {COVERAGE_PASS:.2f})"
            )
        if paraphrase_split:
            reasons.append(
                f"paraphrase flag on one model (small {small['nonname_sub_rate']:.3f}, "
                f"medium {medium['nonname_sub_rate']:.3f})"
            )
        if wer_split:
            reasons.append(f"WER backstop on one model (small {small['wer']:.3f}, medium {medium['wer']:.3f})")
        return "UNSURE", reasons, quotes

    return "PASS", [], []


def _one_sided(span: dict, model: str) -> dict:
    return {
        "kind": span.get("kind"),
        "verse": span.get("verse"),
        "time": span.get("start"),
        "time_end": span.get("end"),
        "quote": span.get("quote"),
        "words": span.get("words"),
        "models": model,
    }


def load_pcm(path: Path) -> tuple[np.ndarray, float]:
    raw = subprocess.check_output(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
        stderr=subprocess.DEVNULL,
    )
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return audio, audio.shape[0] / 16000.0


def silence_gaps(audio: np.ndarray, sr: int = 16000) -> list[dict]:
    if audio.size == 0:
        return []
    frame = int(0.02 * sr)
    n = audio.size // frame
    if n == 0:
        return []
    rms = np.sqrt(np.mean(np.square(audio[: n * frame].reshape(n, frame)), axis=1))
    speech = np.percentile(rms, 95)
    thresh = max(0.004, 0.08 * float(speech))
    silent = rms < thresh
    duration = audio.shape[0] / sr
    gaps = []
    i = 0
    while i < n:
        if not silent[i]:
            i += 1
            continue
        j = i
        while j < n and silent[j]:
            j += 1
        start = i * frame / sr
        end = j * frame / sr
        i = j
        # Trim edge padding. Only the interior portion can be a defect.
        inner_start = max(start, 0.5)
        inner_end = min(end, max(0.5, duration - 0.5))
        if inner_end - inner_start > SILENCE_SEC:
            gaps.append(
                {
                    "start": round(inner_start, 2),
                    "end": round(inner_end, 2),
                    "seconds": round(inner_end - inner_start, 2),
                }
            )
    return gaps


def find_audio_loops(audio: np.ndarray, sr: int = 16000) -> list[dict]:
    step = 8
    x = np.ascontiguousarray(audio[::step])
    sr2 = sr / step
    win = int(LOOP_WIN_SEC * sr2)
    hop = int(1.0 * sr2)
    search = int(30.0 * sr2)
    if len(x) < win * 2:
        return []
    hits = []
    pos = 0
    n = len(x)
    while pos + win * 2 < n:
        seg = x[pos : pos + win]
        energy = float(np.dot(seg, seg)) / win
        if energy < 1e-4:
            pos += hop
            continue
        seg_n = float(np.linalg.norm(seg))
        last = min(n - win, pos + win + search)
        best = 0.0
        best_at = pos + win
        k = pos + win
        while k <= last:
            cand = x[k : k + win]
            sim = float(np.dot(seg, cand) / (seg_n * float(np.linalg.norm(cand)) + 1e-9))
            if sim > best:
                best = sim
                best_at = k
            k += hop
        if best >= LOOP_CORR:
            hits.append((pos / sr2, best_at / sr2, best))
        pos += hop
    if not hits:
        return []
    # Merge hits from the same loop.
    groups = [[hits[0]]]
    for start, match, corr in hits[1:]:
        ps, pm, _pc = groups[-1][-1]
        if start - ps <= 2.5 and abs((match - start) - (pm - ps)) <= 1.5:
            groups[-1].append((start, match, corr))
        else:
            groups.append([(start, match, corr)])
    loops = []
    for group in groups:
        start = group[0][0]
        match = group[0][1]
        corr = max(g[2] for g in group)
        loops.append(
            {
                "start": round(start, 2),
                "match_start": round(match, 2),
                "corr": round(corr, 3),
                "windows": len(group),
            }
        )
    return loops


def context_at(words: list[dict], t: float) -> str:
    near = []
    for w in words:
        if w["start"] is None:
            continue
        if abs(w["start"] - t) <= 4:
            near.append(w["word"])
    return " ".join(near[:20])


def spoken_forms(n: int) -> list[tuple[str, ...]]:
    """Spoken readings of a number written as digits in the source."""
    if n < 0 or n >= 10000:
        return []
    if n < 20:
        return [(_ONES[n],)]
    if n < 100:
        tens, rest = divmod(n, 10)
        if rest == 0:
            return [(_TENS[tens - 2],)]
        return [(_TENS[tens - 2], _ONES[rest]), (f"{_TENS[tens - 2]}{_ONES[rest]}",)]
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        head = (_ONES[hundreds], "hundred")
        if rest == 0:
            return [head]
        out = []
        for tail in spoken_forms(rest):
            out.append(head + tail)
            out.append(head + ("and",) + tail)
        return out
    thousands, rest = divmod(n, 1000)
    head = (_ONES[thousands], "thousand")
    if rest == 0:
        return [head]
    out = []
    for tail in spoken_forms(rest):
        out.append(head + tail)
        out.append(head + ("and",) + tail)
    return out


def _number_suffixes(token: str) -> list[tuple[str, ...]]:
    if not token.isdigit() or len(token) > 4:
        return []
    suffixes = []
    seen = set()
    for form in spoken_forms(int(token)):
        for i in range(len(form)):
            suf = form[i:]
            if suf not in seen:
                seen.add(suf)
                suffixes.append(suf)
    return suffixes


def _soft_slip(a: str, b: str) -> bool:
    if a == b:
        return True
    if min(len(a), len(b)) >= 3 and a.rstrip("s") == b.rstrip("s"):
        return True
    return min(len(a), len(b)) >= 4 and one_edit(a, b)


def gram_in_source(gram: tuple[str, ...], ref_norms: list[str]) -> bool:
    """True when a heard phrase is the source line, a spoken number, or one small slip."""
    span = len(gram)
    if span == 0 or not ref_norms:
        return False
    limit = len(ref_norms) - span + 1
    for i in range(max(0, limit)):
        if all(tokens_equal(gram[k], ref_norms[i + k]) for k in range(span)):
            return True
    for i in range(len(ref_norms)):
        gi = 0
        si = i
        slips = 0
        while gi < span and si < len(ref_norms):
            tok = ref_norms[si]
            suffixes = _number_suffixes(tok)
            taken = 0
            for suf in suffixes:
                length = len(suf)
                if length <= span - gi and all(tokens_equal(gram[gi + k], suf[k]) for k in range(length)):
                    taken = max(taken, length)
            if taken:
                gi += taken
                si += 1
                continue
            if tokens_equal(tok, gram[gi]):
                gi += 1
                si += 1
                continue
            if slips < 1 and _soft_slip(tok, gram[gi]):
                slips += 1
                gi += 1
                si += 1
                continue
            break
        if gi == span:
            return True
    return False


def shared_extra_phrase(
    models: dict,
    audio: np.ndarray,
    ref_norms: list[str],
    book: str,
    chapter: int,
    sr: int = 16000,
) -> dict | None:
    """When full-file transcripts disagree, check short windows.

    A long file lets one model skip a bad opening that the other model
    quotes. Both models transcribe the first 36 seconds in overlapping
    windows. A 5-word phrase that is in both windows and not in the source
    is an agreed content defect. A leading book/chapter announcement is not
    an insertion, including the chapter number plus the first source words.
    """
    if audio.size < sr * 8:
        return None
    def in_source(gram: tuple[str, ...]) -> bool:
        # path/paths, spoken numbers (930 -> "nine hundred and thirty"), and one
        # plural slip are the source line, not an extra passage.
        return gram_in_source(gram, ref_norms)

    number_keys = {tuple(form) for form in number_forms(chapter)}

    def is_announcement(gram: tuple[str, ...]) -> bool:
        if in_source(gram):
            return True
        if gram[:1] in number_keys and in_source(gram[1:]):
            return True
        if gram and gram[0] in ("chapter", "chapters") and gram[1:2] in number_keys and in_source(gram[2:]):
            return True
        return False

    found = {SMALL: {}, MEDIUM: {}}
    limit = min(audio.size / sr, 36.0)
    start = 0.0
    while start < limit - 6:
        end = min(audio.size / sr, start + 14.0)
        clip = audio[int(start * sr) : int(end * sr)]
        for name, model in models.items():
            words = transcribe(model, clip)
            norms = [tok[0] for tok in words_to_hyp(words)]
            cut = header_cut(norms, book, chapter)
            if cut:
                norms = norms[cut:]
            for i in range(len(norms) - SPAN_MIN + 1):
                gram = tuple(norms[i : i + SPAN_MIN])
                if gram in found[name] or is_announcement(gram):
                    continue
                content = [w for w in gram if w not in FUNC and not w.isdigit()]
                if len(content) < 2:
                    continue
                found[name][gram] = round(start, 2)
        start += 7.0
    shared = []
    for gram, t0 in found[SMALL].items():
        if gram not in found[MEDIUM]:
            continue
        shared.append((found[MEDIUM][gram], gram))
    if not shared:
        return None
    shared.sort()
    # Join overlapping 5-grams into one quoted phrase.
    phrase = list(shared[0][1])
    t_start = shared[0][0]
    t_end = t_start
    for t0, gram in shared[1:]:
        if gram[:4] == tuple(phrase[-4:]):
            phrase.append(gram[-1])
            t_end = t0
        elif t0 - t_end > 10 and len(phrase) >= SPAN_MIN:
            break
    return {
        "kind": "inserted",
        "verse": None,
        "time": t_start,
        "time_end": t_end,
        "quote": " ".join(phrase),
        "models": "small.en+medium.en windows",
    }


def transcribe(model, audio: np.ndarray) -> list[dict]:
    segments, _info = model.transcribe(
        audio,
        beam_size=1,
        word_timestamps=True,
        vad_filter=False,
        condition_on_previous_text=False,
        language="en",
        temperature=0.0,
        compression_ratio_threshold=10.0,
        log_prob_threshold=-1.5,
        no_speech_threshold=0.8,
    )
    words = []
    for seg in segments:
        if not seg.words:
            continue
        for w in seg.words:
            words.append({"word": w.word.strip(), "start": float(w.start), "end": float(w.end)})
    return words


def words_to_hyp(words: list[dict]) -> list[tuple]:
    hyp = []
    for w in words:
        pieces = tokenize(w["word"])
        if not pieces:
            continue
        # One whisper token usually becomes one word. If punctuation split it,
        # share the same timestamps.
        for norm, raw in pieces:
            hyp.append((norm, raw, w["start"], w["end"]))
    return hyp


def file_hashes(path: Path) -> tuple[str, str, int]:
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest(), hashlib.sha1(data).hexdigest(), len(data)


def load_sources(root: Path) -> dict[str, dict]:
    books = {}
    if not root.is_dir():
        return books
    for path in sorted(root.glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("book") and data.get("chapters"):
            books[data["book"]] = data
    return books


def load_manifests(audio_root: Path) -> dict[tuple[str, int], dict]:
    found = {}
    for book_dir in sorted(p for p in audio_root.iterdir() if p.is_dir()):
        manifest = book_dir / "manifest.json"
        if not manifest.exists():
            continue
        try:
            rows = json.loads(manifest.read_text())
        except json.JSONDecodeError:
            continue
        for row in rows:
            found[(row["book"], int(row["chapter"]))] = row
    return found


def band_of(book: str, chapter: int) -> tuple:
    key = (book, chapter)
    if key in SKIP:
        return (9, 0, 0, 0)
    for i, item in enumerate(PRIORITY_ADD):
        if item == key:
            return (0, i, 0, 0)
    for i, item in enumerate(SUSPECTS):
        if item == key:
            return (1, i, 0, 0)
    idx = CANON_INDEX.get(book, 500)
    if idx >= NT_START:
        tier = NT_PRIORITY.get(book, 3)
        # John, Romans, 1 Corinthians before the other NT books, including
        # the gospel chapters that were not on the suspect list.
        if tier < 3:
            return (2, tier, idx, chapter)
        return (2, 3, idx, chapter)
    return (3, idx, chapter, 0)


def list_label(book: str, chapter: int) -> str:
    key = (book, chapter)
    if key in PRIORITY_ADD:
        return "priority-add"
    if key in SUSPECTS:
        return "stt-suspect"
    if CANON_INDEX.get(book, 0) >= NT_START:
        return "nt"
    return "ot"


def passes_from_ref(ref: str) -> set[tuple[str, int]]:
    """Chapters already PASS in qa/*.jsonl on a git ref. Audio is not opened."""
    try:
        listing = subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", ref, "qa"],
            cwd=REPO,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return set()
    passed: set[tuple[str, int]] = set()
    for rel in listing.splitlines():
        if not rel.endswith(".jsonl"):
            continue
        try:
            blob = subprocess.check_output(["git", "show", f"{ref}:{rel}"], cwd=REPO, stderr=subprocess.DEVNULL)
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
        for line in blob.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("verdict") != "PASS":
                continue
            book = row.get("book")
            chapter = row.get("chapter")
            if book not in CANON_INDEX or CANON_INDEX[book] >= NT_START:
                continue
            if chapter is None:
                continue
            passed.add((book, int(chapter)))
    return passed


def iter_jobs(audio_root: Path) -> list[dict]:
    jobs = []
    manifests = load_manifests(audio_root)
    for (book, chapter), row in manifests.items():
        if CANON_INDEX.get(book, 999) >= NT_START:
            continue
        if (book, chapter) in SKIP or (book, chapter) in LAB_PASS:
            continue
        path = audio_root / book / f"{chapter}.m4a"
        if not path.exists():
            alt = audio_root / book / row.get("file", "")
            path = alt if alt.exists() else path
        jobs.append(
            {
                "book": book,
                "chapter": chapter,
                "path": path,
                "manifest_duration": row.get("durationSec"),
                "manifest_text_sha1": row.get("textSha1"),
                "list": list_label(book, chapter),
            }
        )
    jobs.sort(key=lambda j: band_of(j["book"], j["chapter"]))
    return jobs


def chapter_source(book_data: dict, chapter: int):
    for ch in book_data["chapters"]:
        if int(ch["chapter"]) == int(chapter):
            verses = [(int(v["v"]), v.get("text") or "") for v in ch.get("verses") or []]
            note = ch.get("kidsNote") or ""
            return verses, note
    return None


def source_sha1(verses, note: str) -> str:
    text = "\n".join(v for _n, v in verses)
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def fmt_clock(seconds) -> str:
    if seconds is None:
        return "?"
    seconds = max(0, int(round(float(seconds))))
    return f"{seconds // 60}:{seconds % 60:02d}"


def public_model(rep: dict | None) -> dict | None:
    if rep is None:
        return None
    def slim(spans):
        out = []
        for s in spans:
            out.append(
                {
                    "kind": s.get("kind"),
                    "verse": s.get("verse"),
                    "start": s.get("start"),
                    "end": s.get("end"),
                    "words": s.get("words"),
                    "quote": s.get("quote"),
                }
            )
        return out

    return {
        "wer": rep["wer"],
        "coverage": rep["coverage"],
        "substitutions": rep["substitutions"],
        "deletions": rep["deletions"],
        "insertions": rep["insertions"],
        "ref_words": rep["ref_words"],
        "hyp_words": rep["hyp_words"],
        "nonname_sub_rate": rep["nonname_sub_rate"],
        "kids_note_spoken": rep["kids_note_spoken"],
        "header_stripped": rep["header_stripped"],
        "announced_chapter": rep["announced_chapter"],
        "tail_missing_words": rep["tail_missing_words"],
        "truncation": rep["truncation"],
        "missing_spans": slim(rep["missing_spans"]),
        "inserted_spans": slim(rep["inserted_spans"]),
        "repeated_spans": slim(rep["repeated_spans"]),
        "name_spans": slim(rep["name_spans"]),
        "cues": slim(rep["cues"]),
        "wrong_chapter": rep["wrong_chapter"]["quote"] if rep.get("wrong_chapter") else None,
    }


def source_tail_text(verses, n: int = 12) -> str:
    words = []
    for _num, text in verses:
        words.extend(raw for _norm, raw in tokenize(text))
    return " ".join(words[-n:])


def quote_coverage(hyp_norms: list[str], quote: str) -> float:
    wanted = [norm for norm, _raw in tokenize(quote or "")]
    if not wanted:
        return 1.0
    return coverage_of(align(wanted, hyp_norms), len(wanted))


def phrase_count(norms: list[str], phrase: str) -> int:
    parts = [norm for norm, _raw in tokenize(phrase or "")]
    if not parts or len(norms) < len(parts):
        return 0
    span = len(parts)
    count = 0
    i = 0
    while i <= len(norms) - span:
        if all(tokens_equal(parts[k], norms[i + k]) for k in range(span)):
            count += 1
            i += span
        else:
            i += 1
    return count


def slice_clip(audio: np.ndarray, start, end, sr: int = 16000) -> tuple[np.ndarray, float, float]:
    n = int(audio.shape[0])
    dur = n / sr if sr else 0.0
    s = 0.0 if start is None else max(0.0, float(start) - 1.0)
    e = dur if end is None else min(dur, float(end) + 6.0)
    if e - s < 8.0:
        e = min(dur, s + 12.0)
    if e - s < 8.0:
        s = max(0.0, e - 12.0)
    if e - s > 24.0:
        e = s + 24.0
    a = int(s * sr)
    b = min(n, max(a + 1, int(e * sr)))
    return audio[a:b], s, b / sr


def _checkable_quote(quote: dict) -> bool:
    kind = quote.get("kind")
    if kind not in ("missing", "inserted", "repeated", "truncation"):
        return False
    if kind == "truncation":
        return True
    return quote.get("time") is not None


def first_words(text: str, n: int = 16) -> str:
    return " ".join(raw for _norm, raw in list(tokenize(text or ""))[:n])


def check_disputed_spans(models, audio, quotes, verses) -> list[dict]:
    """Re-transcribe each disputed span with both models. The slice is the audio check.

    A missing-span timestamp is the next word the model did hear, so the gap
    is before that clock time. The slice covers the gap, and the check uses
    the first words of the quote (the part at the start of the gap).
    """
    ranked = [q for q in (quotes or []) if _checkable_quote(q)]
    ranked.sort(key=lambda q: (-(q.get("words") or 0), q.get("time") is None, q.get("time") or 0.0))
    tail = source_tail_text(verses)
    dur = audio.shape[0] / 16000.0 if audio.size else 0.0
    checks = []
    for quote in ranked[:MAX_SLICE_CHECKS]:
        kind = quote["kind"]
        if kind == "truncation":
            t0, t1 = max(0.0, dur - 18.0), dur
            target = tail
            clip, abs_s, abs_e = slice_clip(audio, t0, t1)
        elif kind == "missing":
            anchor = float(quote["time"])
            n_words = quote.get("words") or len(tokenize(quote.get("quote") or ""))
            # Long clips that start on a chapter title make Whisper drop the
            # words that follow. Keep the check on the first words only.
            if n_words > 20:
                gap = min(40.0, float(n_words) * 0.4)
                abs_s = max(0.0, anchor - gap)
                abs_e = min(dur, abs_s + 9.0)
            else:
                abs_e = min(dur, anchor + 1.0)
                abs_s = max(0.0, abs_e - 10.0)
            target = first_words(quote.get("quote") or "", 12)
            a = int(abs_s * 16000)
            b = min(int(audio.shape[0]), max(a + 1, int(abs_e * 16000)))
            clip = audio[a:b]
        else:
            t0 = quote.get("time")
            t1 = quote.get("time_end")
            target = first_words(quote.get("quote") or "", 24)
            clip, abs_s, abs_e = slice_clip(audio, t0, t1)
        heard = {}
        for name, model in models.items():
            words = transcribe(model, clip)
            norms = [tok[0] for tok in words_to_hyp(words)]
            text = " ".join(w["word"] for w in words)
            if len(text) > 220:
                text = text[:217] + "..."
            entry = {"text": text, "coverage": round(quote_coverage(norms, target), 3), "words": len(norms)}
            if kind == "repeated":
                entry["times"] = phrase_count(norms, target)
            heard[name] = entry
        checks.append(
            {
                "kind": kind,
                "verse": quote.get("verse"),
                "start": round(abs_s, 2),
                "end": round(abs_e, 2),
                "quote": target,
                "full_file_models": quote.get("models"),
                "slice": heard,
            }
        )
    return checks


def _slice_class(check: dict) -> str:
    small = check["slice"].get(SMALL) or {}
    medium = check["slice"].get(MEDIUM) or {}
    if (small.get("words") or 0) < 4 and (medium.get("words") or 0) < 4:
        return "unclear"
    if check["kind"] == "repeated":
        st = small.get("times", 0)
        mt = medium.get("times", 0)
        if st >= 2 and mt >= 2:
            return "confirmed"
        if st <= 1 and mt <= 1:
            return "refuted"
        return "unclear"
    sc = small.get("coverage", 0.0)
    mc = medium.get("coverage", 0.0)
    if check["kind"] in ("missing", "truncation"):
        if sc >= SLICE_CONFIRM and mc >= SLICE_CONFIRM:
            return "refuted"
        if sc < SLICE_REFUTE and mc < SLICE_REFUTE:
            return "confirmed"
        return "unclear"
    if sc >= SLICE_CONFIRM and mc >= SLICE_CONFIRM:
        return "confirmed"
    if sc < SLICE_REFUTE and mc < SLICE_REFUTE:
        return "refuted"
    return "unclear"


def _bars_ok(rep: dict | None, ignore_truncation: bool = False) -> bool:
    if not rep:
        return False
    truncated = False if ignore_truncation else bool(rep.get("truncation"))
    return (
        rep["coverage"] >= COVERAGE_PASS
        and rep["nonname_sub_rate"] <= NONNAME_SUB_PARAPHRASE
        and rep["wer"] <= WER_BACKSTOP
        and not truncated
    )


def apply_slice_checks(verdict, reasons, quotes, checks, small, medium, acoustic):
    """Both models on the slice must agree before a disagreement becomes PASS or FAIL."""
    if not checks:
        return verdict, reasons, quotes, None
    confirmed, refuted, unclear = [], [], []
    for check in checks:
        label = _slice_class(check)
        check["slice_result"] = label
        {"confirmed": confirmed, "refuted": refuted, "unclear": unclear}[label].append(check)
    notes = []
    for check in checks:
        heard_s = check["slice"][SMALL]
        heard_m = check["slice"][MEDIUM]
        where = f"verse {check['verse']}" if check.get("verse") else "verse ?"
        extra = ""
        if check["kind"] == "repeated":
            extra = f", times {heard_s.get('times')}/{heard_m.get('times')}"
        notes.append(
            f"{check['slice_result']}: {check['kind']} {where} "
            f"{fmt_clock(check['start'])}-{fmt_clock(check['end'])} "
            f"(slice coverage small {heard_s.get('coverage', 0):.2f}, "
            f"medium {heard_m.get('coverage', 0):.2f}{extra})"
        )
    note = " ".join(notes)
    blocking_kinds = {"names", "paraphrase", "cue", "wrong_chapter", "silence", "loop"}
    blocking = [q for q in quotes if q.get("kind") in blocking_kinds]
    n_checkable = sum(1 for q in quotes if _checkable_quote(q))
    incomplete = n_checkable > len(checks)
    acoustic_bad = bool((acoustic.get("silence") or []) or (acoustic.get("loops") or []))
    if confirmed:
        reasons = [
            "both models, on the audio span: "
            + "; ".join(
                (
                    f"{c['kind']} verse {c['verse']}" if c.get("verse") else c["kind"]
                )
                + f" at {fmt_clock(c['start'])}"
                for c in confirmed
            )
        ] + list(reasons)
        return "FAIL", reasons, quotes, note
    if unclear or incomplete or blocking or acoustic_bad:
        return verdict, reasons, quotes, note
    ignore_tail = all(c["kind"] == "truncation" for c in refuted) and bool(refuted)
    if refuted and _bars_ok(small, ignore_tail) and _bars_ok(medium, ignore_tail):
        return "PASS", ["disputed spans are not in the audio; both models meet the pass bars"], [], note
    # The slice heard the source words, so a low full-file coverage is a
    # recognizer miss, not an agreed missing passage.
    reasons = [
        "audio slice contains the disputed words; the models still disagree "
        f"(coverage small {small['coverage']:.3f}, medium {medium['coverage']:.3f})"
    ]
    kept = [q for q in quotes if not _checkable_quote(q)]
    return "UNSURE", reasons, kept, note


def score_chapter(job: dict, verses, note: str, models: dict) -> dict:
    path: Path = job["path"]
    sha256, sha1, size = file_hashes(path)
    audio, duration = load_pcm(path)
    names = name_set(verses)
    acoustic_silence = silence_gaps(audio)
    loops = find_audio_loops(audio)
    reports = {}
    word_cache = {}
    for name, model in models.items():
        t0 = time.time()
        words = transcribe(model, audio)
        word_cache[name] = words
        hyp = words_to_hyp(words)
        rep = analyze_hyp(hyp, verses, note, job["book"], job["chapter"], names)
        rep["seconds"] = round(time.time() - t0, 1)
        reports[name] = rep
    # Context for waveform defects from the medium transcript (fuller), else small.
    ctx_words = word_cache.get(MEDIUM) or word_cache.get(SMALL) or []
    for gap in acoustic_silence:
        gap["context"] = context_at(ctx_words, gap["start"])
        gap["verse"] = None
    for loop in loops:
        loop["context"] = context_at(ctx_words, loop["start"])
        loop["verse"] = None
    small = reports.get(SMALL)
    medium = reports.get(MEDIUM)
    acoustic = {"silence": acoustic_silence, "loops": loops}
    # Duration vs expected uses verse words.
    ref_words = (small or medium or {}).get("ref_words") or sum(len(tokenize(t)) for _n, t in verses)
    expected = ref_words / WORDS_PER_SEC if ref_words else None
    ratio = round(duration / expected, 3) if expected else None
    if ratio is not None and ratio < DURATION_SHORT:
        duration_flag = "short"
    elif ratio is not None and ratio > DURATION_LONG:
        duration_flag = "long"
    else:
        duration_flag = "ok"
    # A short file plus both models missing the tail is truncation even if each
    # tail count is just under the word cutoff. analyze_hyp already flags tails.
    if (
        duration_flag == "short"
        and small
        and medium
        and small["coverage"] < COVERAGE_FAIL
        and medium["coverage"] < COVERAGE_FAIL
    ):
        small["truncation"] = True
        medium["truncation"] = True
    verdict, reasons, quotes = decide(small, medium, acoustic)
    # Never allow PASS unless both model blocks exist. decide already enforces this.
    if verdict == "PASS" and (small is None or medium is None):
        verdict = "UNSURE"
        reasons = ["single-model result cannot pass"]
    probe = None
    if verdict == "UNSURE" and small is not None and medium is not None:
        ref_norms = []
        for _num, text in verses:
            ref_norms.extend(norm for norm, _raw in tokenize(text))
        probe = shared_extra_phrase(models, audio, ref_norms, job["book"], job["chapter"])
        if probe:
            verdict = "FAIL"
            reasons = [
                "both models, on short windows, say words that are not in the chapter: "
                + probe["quote"]
            ] + reasons
            quotes = [probe] + quotes
    audio_checks = []
    audio_note = None
    if verdict != "PASS" and small is not None and medium is not None:
        audio_checks = check_disputed_spans(models, audio, quotes, verses)
        verdict, reasons, quotes, audio_note = apply_slice_checks(
            verdict, reasons, quotes, audio_checks, small, medium, acoustic
        )
    row = {
        "book": job["book"],
        "chapter": job["chapter"],
        "list": job["list"],
        "audio_path": str(path.relative_to(REPO)) if path.is_relative_to(REPO) else str(path),
        "audio_sha256": sha256,
        "audio_sha1": sha1,
        "audio_bytes": size,
        "manifest_text_sha1": job.get("manifest_text_sha1"),
        "source_text_sha1": source_sha1(verses, note),
        "source_ref": SOURCE_REF,
        "duration_sec": round(duration, 2),
        "manifest_duration_sec": job.get("manifest_duration"),
        "expected_duration_sec": round(expected, 2) if expected else None,
        "duration_ratio": ratio,
        "duration_flag": duration_flag,
        "ref_words": ref_words,
        "silence": acoustic_silence,
        "audio_loops": loops,
        "models": {name: public_model(reports.get(name)) for name in (SMALL, MEDIUM)},
        "verdict": verdict,
        "reasons": reasons,
        "quotes": quotes,
        "window_probe": probe,
        "audio_check": audio_note,
        "audio_checks": audio_checks or None,
        "engine": {
            "tool": "faster-whisper",
            "models": [SMALL, MEDIUM],
            "compute_type": "int8",
            "device": "cpu",
            "beam_size": 1,
            "word_timestamps": True,
            "condition_on_previous_text": False,
            "compression_ratio_threshold": 10.0,
            "no_speech_threshold": 0.8,
        },
    }
    return row


def load_done(path: Path) -> dict[tuple[str, int], dict]:
    done = {}
    if not path.exists():
        return done
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        done[(row["book"], int(row["chapter"]))] = row
    return done


def append_row(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def compact_jsonl(path: Path, done: dict[tuple[str, int], dict]) -> None:
    """One row per chapter. The append log can hold a re-score; keep the latest."""
    rows = sorted(done.values(), key=lambda r: band_of(r["book"], int(r["chapter"])))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)


def pass_groups(rows: list[dict]) -> list[str]:
    by_book: dict[str, list[int]] = {}
    for row in rows:
        if row.get("verdict") != "PASS":
            continue
        by_book.setdefault(row["book"], []).append(int(row["chapter"]))
    lines = []
    for book in CANON:
        nums = sorted(set(by_book.get(book, [])))
        if not nums:
            continue
        ranges = []
        start = prev = nums[0]
        for n in nums[1:]:
            if n == prev + 1:
                prev = n
                continue
            ranges.append(str(start) if start == prev else f"{start}–{prev}")
            start = prev = n
        ranges.append(str(start) if start == prev else f"{start}–{prev}")
        lines.append(f"- {book} {', '.join(ranges)}")
    return lines


def write_summary(path: Path, rows: list[dict], jobs: list[dict]) -> None:
    by_verdict = Counter(r["verdict"] for r in rows)
    by_list = Counter(r.get("list") for r in rows)
    fails = [r for r in rows if r["verdict"] == "FAIL"]
    unsures = [r for r in rows if r["verdict"] == "UNSURE"]
    done_keys = {(r["book"], r["chapter"]) for r in rows}
    remaining = [j for j in jobs if (j["book"], j["chapter"]) not in done_keys]
    rem_band = Counter(j["list"] for j in remaining)

    def quote_lines(row: dict) -> list[str]:
        lines = []
        if not row.get("quotes"):
            why = "; ".join(row.get("reasons") or []) or row["verdict"]
            lines.append(f"- **{row['book']} {row['chapter']}** — {why}")
            if row.get("audio_check"):
                lines.append(f"  - audio check: {row['audio_check']}")
            return lines
        for q in row["quotes"]:
            verse = q.get("verse")
            if verse:
                where = f"verse {verse}"
            elif q.get("time") is not None and float(q["time"]) < 20:
                where = "before verse 1"
            else:
                where = "verse ?"
            clock = fmt_clock(q.get("time"))
            end = fmt_clock(q.get("time_end")) if q.get("time_end") is not None else ""
            span = f"{clock}–{end}" if end and end != clock else clock
            text = (q.get("quote") or "").replace("\n", " ")
            lines.append(
                f"- **{row['book']} {row['chapter']}** — {q.get('kind')} {where} at {span} — "
                f"\"{text}\" ({q.get('models')})"
            )
        if row.get("audio_check"):
            lines.append(f"  - audio check: {row['audio_check']}")
        return lines

    lines = [
        "# Girl Old Testament voice machine QA — 2026-11-17",
        "",
        "Machine content check of `kids-bible-audio/sample1` (Old Testament chapters)",
        f"against the retold kids text in {SOURCE_REF}.",
        "Audio blobs are hashed in the jsonl (sha256 and sha1).",
        "No audio was added or changed.",
        "",
        "## Excluded",
        "",
    ]
    if LAB_PASS:
        lines.append("Already PASS in qa/*.jsonl on origin/lab-audio, not re-scored:")
        lines.append("")
        for book, chapter in sorted(LAB_PASS, key=lambda item: band_of(item[0], item[1])):
            lines.append(f"- {book} {chapter}")
        lines.append("")
    else:
        lines.append(
            "No Old Testament chapter was already PASS in qa/*.jsonl on origin/lab-audio. "
            "Every girl Old Testament chapter is in scope. New Testament files in sample1/ "
            "are not this shard."
        )
        lines.append("")
    lines.extend([
        "## How a chapter passes",
        "",
        "Two models, faster-whisper `small.en` and `medium.en`, int8, CPU, beam 1,",
        "word timestamps, `condition_on_previous_text` off. Each transcript is aligned",
        "to the chapter with light normalization (case, punctuation, a one-letter slip",
        "on long words, and number words). A leading \"Book, chapter N\" announcement",
        "is not an insertion. The kids note at the end of the source is counted only",
        "when the audio actually reads it.",
        "",
        "PASS requires both models to agree that all of the following are true:",
        "",
        f"- No inserted, missing, or repeated span longer than 4 words. A run of",
        "  proper-name substitutions is name noise, not a failed span, unless both",
        "  models heard the same wrong names.",
        f"- Coverage of source words is at least {COVERAGE_PASS:.0%} on both models.",
        f"  Both under {COVERAGE_FAIL:.0%} fails. A result in between, or a split",
        "  between the models, is UNSURE (coverage unclear).",
        f"- Non-name substitution rate is at most {NONNAME_SUB_PARAPHRASE:.0%} on both.",
        "  Above that on both models is paraphrase-level drift (a different telling,",
        "  not a misheard name). Raw WER is recorded for each model and is not the",
        "  pass line: name-heavy chapters move WER without changing the story, and",
        "  the two models miss different names.",
        f"- WER is also backstopped at {WER_BACKSTOP:.0%}. Both models above that fail",
        "  even if the errors never form a 5-word span.",
        f"- No interior silence longer than {SILENCE_SEC:.0f} seconds, and no",
        f"  sample-level audio loop ({LOOP_WIN_SEC:.0f}s at correlation >= {LOOP_CORR}).",
        "  Those are measured on the waveform, so they are not a model vote.",
        "- No production or non-story phrase (\"take two\", \"start again\",",
        "  \"thanks for watching\", and the other phrases in the script) unless that",
        "  phrase is in the source. Both transcripts must contain it. One model",
        "  alone is UNSURE.",
        f"- Not truncated: both models missing the last {TAIL_WORDS} or more source",
        "  words, or a short file (under "
        f"{DURATION_SHORT:.0%} of expected) with both coverages under {COVERAGE_FAIL:.0%}.",
        "",
        f"Expected duration is source words / {WORDS_PER_SEC} words per second",
        "(Matthew 3 lands near 2.6). `duration_ratio` is recorded on every row.",
        "A slow or fast reading that still says the chapter is not a content defect.",
        "",
        "UNSURE in the jsonl (shown as UNCERTAIN here) means the models disagree,",
        "one model did not finish, or coverage stayed between the pass and fail lines.",
        "A single model never passes. If the full-file transcripts disagree, both",
        "models are run again on short windows of the first 36 seconds. The same",
        "5-word phrase in both windows, and not in the source, fails the chapter.",
        "Each disputed span is then transcribed again from that slice of the audio.",
        "Both models hearing the defect fails the chapter. Both hearing the source",
        "words clears that span. A split slice stays UNCERTAIN.",
        "",
        "## Counts",
        "",
        f"- Scored chapters: {len(rows)}",
        f"- PASS: {by_verdict.get('PASS', 0)}",
        f"- FAIL: {by_verdict.get('FAIL', 0)}",
        f"- UNCERTAIN: {by_verdict.get('UNSURE', 0)} (jsonl verdict UNSURE)",
        f"- Still to score: {len(remaining)} Old Testament chapters",
        "",
    ])
    lines.append("## PASS")
    lines.append("")
    grouped = pass_groups(rows)
    if not grouped:
        lines.append("None yet.")
        lines.append("")
    else:
        lines.append(
            f"{by_verdict.get('PASS', 0)} chapters. Both models agreed there was no "
            "missing, invented, or repeated passage."
        )
        lines.append("")
        lines.extend(grouped)
        lines.append("")
    lines.append("## FAIL")
    lines.append("")
    if not fails:
        lines.append("None.")
        lines.append("")
    else:
        for row in fails:
            lines.extend(quote_lines(row))
            small = (row.get("models") or {}).get(SMALL) or {}
            medium = (row.get("models") or {}).get(MEDIUM) or {}
            lines.append(
                f"  - WER small {small.get('wer')} / medium {medium.get('wer')}; "
                f"coverage small {small.get('coverage')} / medium {medium.get('coverage')}; "
                f"duration {row.get('duration_sec')}s vs expected {row.get('expected_duration_sec')}s "
                f"(ratio {row.get('duration_ratio')}); sha256 `{row.get('audio_sha256')}`"
            )
        lines.append("")
    lines.append("## UNCERTAIN")
    lines.append("")
    if not unsures:
        lines.append("None.")
        lines.append("")
    else:
        for row in unsures:
            lines.extend(quote_lines(row))
            small = (row.get("models") or {}).get(SMALL) or {}
            medium = (row.get("models") or {}).get(MEDIUM) or {}
            why = "; ".join(row.get("reasons") or [])
            lines.append(
                f"  - {why}; WER small {small.get('wer')} / medium {medium.get('wer')}; "
                f"coverage small {small.get('coverage')} / medium {medium.get('coverage')}; "
                f"sha256 `{row.get('audio_sha256')}`"
            )
        lines.append("")
    lines.append("## Script")
    lines.append("")
    lines.append("`qa/girl_ot_machine_qa.py` resumes from the jsonl. It only reads audio.")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def load_models(threads: int):
    from faster_whisper import WhisperModel

    models = {}
    for name in (SMALL, MEDIUM):
        t0 = time.time()
        models[name] = WhisperModel(name, device="cpu", compute_type="int8", cpu_threads=threads)
        print(f"loaded {name} in {time.time() - t0:.1f}s", flush=True)
    return models


def commit_batch(scored_total: int, push: bool) -> None:
    rels = [
        "qa/girl-ot-machine-qa-2026-11-17.jsonl",
        "qa/girl-ot-machine-qa-summary.md",
    ]
    subprocess.run(["git", "add", "--", *rels], cwd=REPO, check=False)
    staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=REPO)
    if staged.returncode == 0:
        print("commit skipped, nothing staged", flush=True)
        return
    message = f"Record girl OT machine QA ({scored_total} chapters scored)."
    result = subprocess.run(["git", "commit", "-m", message], cwd=REPO)
    if result.returncode != 0:
        print("commit failed", flush=True)
        return
    print(f"committed: {message}", flush=True)
    if not push:
        return
    pushed = subprocess.run(["git", "push", "-u", "origin", "HEAD"], cwd=REPO)
    if pushed.returncode != 0:
        print("push failed", flush=True)


def run(args) -> int:
    global LAB_PASS
    audio_root = Path(args.audio_root)
    source_root = Path(args.source_root)
    out_path = Path(args.out)
    summary_path = Path(args.summary)
    LAB_PASS = passes_from_ref(args.pass_ref)
    print(f"already passed on {args.pass_ref}: {len(LAB_PASS)}", flush=True)
    sources = load_sources(source_root)
    jobs = iter_jobs(audio_root)
    if args.only:
        wanted = set()
        for item in args.only:
            book, chapter = item.rsplit(":", 1)
            wanted.add((book, int(chapter)))
        jobs = [j for j in jobs if (j["book"], j["chapter"]) in wanted]
    done = load_done(out_path)
    pending = []
    for job in jobs:
        key = (job["book"], job["chapter"])
        prev = done.get(key)
        if prev and not args.force:
            # Re-score if the file on disk is not the blob already recorded.
            if job["path"].exists():
                sha256, _sha1, _size = file_hashes(job["path"])
                if prev.get("audio_sha256") == sha256 and prev.get("verdict") in ("PASS", "FAIL", "UNSURE"):
                    continue
        pending.append(job)
    if args.max_chapters:
        pending = pending[: args.max_chapters]
    print(
        f"jobs {len(jobs)} done {len(done)} pending {len(pending)} sources {len(sources)}",
        flush=True,
    )
    if not pending:
        rows = list(done.values())
        write_summary(summary_path, rows, iter_jobs(audio_root))
        print("nothing to score", flush=True)
        return 0
    missing_books = sorted({j["book"] for j in pending if j["book"] not in sources})
    if missing_books:
        print("missing source books: " + ", ".join(missing_books), flush=True)
        pending = [j for j in pending if j["book"] in sources]
        if not pending:
            return 2
    models = load_models(args.threads)
    scored = 0
    for job in pending:
        chapter_src = chapter_source(sources[job["book"]], job["chapter"])
        if chapter_src is None:
            print(f"no source text {job['book']} {job['chapter']}", flush=True)
            continue
        if not job["path"].exists():
            print(f"missing audio {job['path']}", flush=True)
            continue
        verses, note = chapter_src
        t0 = time.time()
        print(f"scoring {job['book']} {job['chapter']} ({job['list']})", flush=True)
        try:
            row = score_chapter(job, verses, note, models)
        except Exception as exc:
            row = {
                "book": job["book"],
                "chapter": job["chapter"],
                "list": job["list"],
                "audio_path": str(job["path"]),
                "verdict": "UNSURE",
                "reasons": [f"scorer error: {type(exc).__name__}"],
                "quotes": [],
                "models": {SMALL: None, MEDIUM: None},
            }
            print(f"error {job['book']} {job['chapter']}: {type(exc).__name__}: {exc}", flush=True)
        append_row(out_path, row)
        done[(row["book"], row["chapter"])] = row
        scored += 1
        small = (row.get("models") or {}).get(SMALL) or {}
        medium = (row.get("models") or {}).get(MEDIUM) or {}
        print(
            f"  {row['verdict']} wer {small.get('wer')}/{medium.get('wer')} "
            f"cov {small.get('coverage')}/{medium.get('coverage')} "
            f"dur {row.get('duration_sec')}s ratio {row.get('duration_ratio')} "
            f"in {time.time() - t0:.0f}s",
            flush=True,
        )
        for reason in row.get("reasons") or []:
            print(f"    {reason}", flush=True)
        if scored % 5 == 0 or scored == len(pending):
            write_summary(summary_path, list(done.values()), iter_jobs(audio_root))
        if args.commit_every and scored % args.commit_every == 0:
            compact_jsonl(out_path, done)
            write_summary(summary_path, list(done.values()), iter_jobs(audio_root))
            commit_batch(len(done), args.push)
    compact_jsonl(out_path, done)
    write_summary(summary_path, list(done.values()), iter_jobs(audio_root))
    if args.commit_every and scored % args.commit_every != 0:
        commit_batch(len(done), args.push)
    print(f"scored {scored}", flush=True)
    return 0
def self_test() -> None:
    verses = [
        (1, "Jesus went into Jericho and was passing through the town."),
        (2, "A man named Zacchaeus lived there. He was a chief tax collector and he was rich."),
    ]
    names = name_set(verses)
    note = "Zacchaeus climbed a tree to see Jesus."

    def hyp_from_text(text: str, t0: float = 0.0):
        hyp = []
        t = t0
        for norm, raw in tokenize(text):
            hyp.append((norm, raw, t, t + 0.3))
            t += 0.35
        return hyp

    ref_text = " ".join(v for _n, v in verses)
    exact = analyze_hyp(hyp_from_text("Luke chapter 19. " + ref_text), verses, note, "Luke", 19, names)
    assert exact["wer"] < 0.02, exact["wer"]
    assert exact["coverage"] > 0.98
    assert not exact["inserted_spans"], exact["inserted_spans"]
    assert exact["header_stripped"] or exact["announced_chapter"] == 19
    assert not exact["kids_note_spoken"]

    dropped = ref_text.replace("was passing through the town.", "")
    missing = analyze_hyp(hyp_from_text(dropped), verses, "", "Luke", 19, names)
    assert missing["missing_spans"], missing
    assert missing["missing_spans"][0]["words"] >= 5

    cue = analyze_hyp(
        hyp_from_text("take two " + ref_text),
        verses,
        "",
        "Luke",
        19,
        names,
    )
    assert cue["cues"], cue["cues"]
    assert any(s["kind"] == "inserted" or s["words"] >= 1 for s in cue["cues"])

    doubled = ref_text + " " + "Jesus went into Jericho and was passing through the town."
    reps = analyze_hyp(hyp_from_text(doubled), verses, "", "Luke", 19, names)
    assert reps["repeated_spans"], reps["repeated_spans"]
    extra = analyze_hyp(
        hyp_from_text("There was a man whose name was Zachary a Syrian tax collector. " + ref_text),
        verses,
        "",
        "Luke",
        19,
        names,
    )
    assert extra["inserted_spans"], extra
    assert not extra["repeated_spans"], extra["repeated_spans"]

    # Five name substitutions are not a content span.
    name_verses = [(1, "Abraham Isaac Jacob Judah Perez were listed.")]
    name_names = name_set(name_verses)
    swapped = analyze_hyp(
        hyp_from_text("Abram Izaak Jakob Judas Peres were listed."),
        name_verses,
        "",
        "Matthew",
        1,
        name_names,
    )
    assert not swapped["missing_spans"], swapped["missing_spans"]

    # Agreed defects fail. One-sided defects are UNSURE.
    clean = exact
    other = dict(exact)
    bad = missing
    verdict, reasons, _quotes = decide(clean, other, {"silence": [], "loops": []})
    assert verdict == "PASS", (verdict, reasons)
    verdict, reasons, _quotes = decide(bad, bad, {"silence": [], "loops": []})
    assert verdict == "FAIL", (verdict, reasons)
    verdict, reasons, _quotes = decide(bad, clean, {"silence": [], "loops": []})
    assert verdict == "UNSURE", (verdict, reasons)
    verdict, _reasons, _quotes = decide(clean, None, {"silence": [], "loops": []})
    assert verdict == "UNSURE"

    sr = 16000
    tone = np.sin(2 * np.pi * 220 * np.arange(sr * 4) / sr).astype(np.float32) * 0.2
    looped = np.concatenate([tone, tone, np.zeros(sr, dtype=np.float32)])
    loops = find_audio_loops(looped, sr)
    assert loops, "expected a loop on a repeated tone"
    noise = np.random.default_rng(0).normal(0, 0.05, sr * 20).astype(np.float32)
    assert not find_audio_loops(noise, sr)

    gap_audio = np.zeros(sr * 10, dtype=np.float32)
    gap_audio[:sr] = 0.2
    gap_audio[6 * sr : 7 * sr] = 0.2
    gaps = silence_gaps(gap_audio, sr)
    assert gaps and gaps[0]["seconds"] > 3.0, gaps
    assert header_cut("genesis chapter 1 in the very beginning god made".split(), "Genesis", 1) == 3
    assert gram_in_source(tuple("thirty years in all and".split()), "adam lived 930 years in all and then".split())
    assert gram_in_source(tuple("that was when gods son".split()), "that was when gods sons had children".split())
    assert not gram_in_source(
        tuple("temple and his attic promise".split()),
        "the lord appeared to abram he said i will give".split(),
    )

    clean_models = {
        "coverage": 0.99,
        "nonname_sub_rate": 0.01,
        "wer": 0.02,
        "truncation": False,
    }
    acoustic = {"silence": [], "loops": []}

    def fake(kind, sc, mc, times=None):
        small = {"coverage": sc, "text": "one two three four five", "words": 8}
        medium = {"coverage": mc, "text": "one two three four five", "words": 8}
        if times is not None:
            small["times"], medium["times"] = times
        return {
            "kind": kind,
            "verse": 1,
            "start": 12.0,
            "end": 20.0,
            "quote": "was passing through the town",
            "full_file_models": MEDIUM,
            "slice": {SMALL: small, MEDIUM: medium},
        }

    quote = {"kind": "missing", "verse": 1, "time": 12.0, "quote": "was passing through the town", "models": MEDIUM}
    verdict, _reasons, _quotes, _note = apply_slice_checks(
        "UNSURE", ["one sided"], [quote], [fake("missing", 0.0, 0.1)], clean_models, clean_models, acoustic
    )
    assert verdict == "FAIL", verdict
    verdict, _reasons, _quotes, _note = apply_slice_checks(
        "UNSURE", ["one sided"], [quote], [fake("missing", 0.9, 0.95)], clean_models, clean_models, acoustic
    )
    assert verdict == "PASS", verdict
    verdict, _reasons, _quotes, _note = apply_slice_checks(
        "UNSURE", ["one sided"], [quote], [fake("missing", 0.95, 0.2)], clean_models, clean_models, acoustic
    )
    assert verdict == "UNSURE", verdict
    weak = dict(clean_models)
    weak["coverage"] = 0.91
    verdict, _reasons, _quotes, _note = apply_slice_checks(
        "FAIL", ["both missing"], [quote], [fake("missing", 0.9, 0.9)], clean_models, weak, acoustic
    )
    assert verdict == "UNSURE", verdict
    verdict, _reasons, _quotes, _note = apply_slice_checks(
        "UNSURE", ["repeat"], [dict(quote, kind="repeated")], [fake("repeated", 1, 1, times=(2, 2))], clean_models, clean_models, acoustic
    )
    assert verdict == "FAIL", verdict
    assert passes_from_ref("origin/lab-audio") == set()

    print("self-test ok", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Dual-model QA for girl Old Testament chapter audio")
    parser.add_argument("--audio-root", default=str(AUDIO_ROOT_DEFAULT))
    parser.add_argument("--source-root", default="/tmp/kids-bible")
    parser.add_argument("--out", default=str(OUT_DEFAULT))
    parser.add_argument("--summary", default=str(SUMMARY_DEFAULT))
    parser.add_argument("--only", action="append", default=[], help="Book:chapter, repeatable")
    parser.add_argument("--max-chapters", type=int, default=0)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--force", action="store_true", help="re-score even if the blob hash matches")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--commit-every", type=int, default=0, help="commit the jsonl and summary every N newly scored chapters")
    parser.add_argument("--push", action="store_true", help="push after each of those commits")
    parser.add_argument("--pass-ref", default="origin/lab-audio", help="git ref whose qa/*.jsonl PASS rows are skipped")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    sys.exit(run(args))


if __name__ == "__main__":
    main()
