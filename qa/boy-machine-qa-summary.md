# Boy voice machine QA — 2026-11-17

Machine content check of `kids-bible-audio/boy` against the retold kids text
in longroad-ios release-1.2-build9 BibleApp/Resources/KidsBible. Audio blobs are hashed in the jsonl (sha256 and sha1).
No audio was added or changed. No pass list was stored in this repo at
04409065, so every boy chapter is in scope except three that were already
sent for a new recording.

## Excluded

- Genesis 36, Luke 6, and Luke 16 are already sent for re-record and were not scored.

## How a chapter passes

Two models, faster-whisper `small.en` and `medium.en`, int8, CPU, beam 1,
word timestamps, `condition_on_previous_text` off. Each transcript is aligned
to the chapter with light normalization (case, punctuation, a one-letter slip
on long words, and number words). A leading "Book, chapter N" announcement
is not an insertion. The kids note at the end of the source is counted only
when the audio actually reads it.

PASS requires both models to agree that all of the following are true:

- No inserted, missing, or repeated span longer than 4 words. A run of
  proper-name substitutions is name noise, not a failed span, unless both
  models heard the same wrong names.
- Coverage of source words is at least 96% on both models.
  Both under 90% fails. A result in between, or a split
  between the models, is UNSURE (coverage unclear).
- Non-name substitution rate is at most 8% on both.
  Above that on both models is paraphrase-level drift (a different telling,
  not a misheard name). Raw WER is recorded for each model and is not the
  pass line: name-heavy chapters move WER without changing the story, and
  the two models miss different names.
- WER is also backstopped at 35%. Both models above that fail
  even if the errors never form a 5-word span.
- No interior silence longer than 3 seconds, and no
  sample-level audio loop (3s at correlation >= 0.97).
  Those are measured on the waveform, so they are not a model vote.
- No production or non-story phrase ("take two", "start again",
  "thanks for watching", and the other phrases in the script) unless that
  phrase is in the source. Both transcripts must contain it. One model
  alone is UNSURE.
- Not truncated: both models missing the last 8 or more source
  words, or a short file (under 70% of expected) with both coverages under 90%.

Expected duration is source words / 2.5 words per second
(Matthew 3 lands near 2.6). `duration_ratio` is recorded on every row.
A slow or fast reading that still says the chapter is not a content defect.

UNSURE means the models disagree, one model did not finish, or coverage
stayed between the pass and fail lines. A single model never passes.
If the full-file transcripts disagree, both models are run again on short
windows of the first 36 seconds. The same 5-word phrase in both windows,
and not in the source, fails the chapter. That catches a bad opening that
one full-file pass skipped.

## Counts

- Scored chapters: 6
- PASS: 0
- FAIL: 2
- UNSURE: 4
- By list: priority-add 1, stt-suspect 5, nt 0, ot 0
- Still to score: 1180 (suspect 40, nt 212, ot 928, priority-add 0)

## FAIL

- **Luke 19** — inserted before verse 1 at 0:02–0:24 — "There was a man whose name was Zachary a Syrian tax collector He was one of the richest in the world This man was trying to see Kenri Zeltin but couldn't because he was seven feet two feet ten inches of height He was one of the richest in the world Then he saw the man who went by each …" (small.en+medium.en)
  - WER small 0.298 / medium 0.222; coverage small 0.917 / medium 0.839; duration 371.11s vs expected 400.0s (ratio 0.928); sha256 `6c67232dd15b287e6badcc91fdabafd03ee2b9ab28e84f0997378fbf10a2a5b8`
- **Matthew 8** — missing verse 12 at 1:48 — "There they will cry and grind their teeth" (small.en+medium.en)
  - WER small 0.0185 / medium 0.1735; coverage small 0.9841 / medium 0.8278; duration 280.79s vs expected 302.0s (ratio 0.93); sha256 `1c9e960422b88ef24036f7d3887e8e916d1fdb37c8b4297dfa1715c472463c2e`

## UNSURE

- **Matthew 3** — missing verse 4 at 0:56 — "He ate locusts and wild honey. People came out to him from Jerusalem" (medium.en)
  - coverage unclear (small 0.990, medium 0.836); pass needs both >= 0.96; medium.en only misses the locusts-and-honey stretch; small.en coverage 0.990; window phrase was the source line with path/paths and was not counted; WER small 0.0169 / medium 0.1783; coverage small 0.9904 / medium 0.8361; sha256 `b56b8b4b20f79383e207f8b244138292bbde72a081945f87ac6c03fa72dffc76`
- **Matthew 5** — coverage verse 1 at 0:02–0:06 — "Jesus saw the crowds, so he went up on a hill and sat down. Said once in the opening." (slice check)
  - models flagged verse 1 as an inserted repeat; a 0-18s slice says that sentence once; coverage unclear (small 0.906, medium 0.796); WER small 0.1092 / medium 0.2331; coverage small 0.9056 / medium 0.7956; sha256 `6f46486c995d1c0e278d09d353187ff381758b04da143989f1ddd24d484c52e7`
- **Matthew 6** — missing verse 27 at 4:06 — "worrying And why do you worry about clothes Look at how the wildflowers grow They don't work or make their own clothes" (medium.en)
  - medium.en only: missing 'worrying And why do you worry about clothes Look at how the wildflowers grow They don't work or make their own clothes'; WER small 0.0037 / medium 0.0362; coverage small 0.9988 / medium 0.97; sha256 `17878fa585ee86dd8f01a9d5e2764d16ed848b6f3190d271d4ba26ebe42d5b23`
- **Matthew 9** — missing verse 1 at ? — "Jesus got into a boat and crossed the lake. He came to his own town." (medium.en)
  - coverage unclear (small 0.977, medium 0.879); window phrase 'he came home the sons' matches the source line 'He came to his own town' and was not counted; medium.en only misses the boat-and-mat opening; small.en coverage 0.977; WER small 0.0604 / medium 0.122; coverage small 0.9774 / medium 0.8792; sha256 `62c19692173f035947affc49ad6619906e0acd6e4520aa01eeecec3394a8386c`

## Script

`qa/boy_machine_qa.py` resumes from the jsonl. It only reads audio.

