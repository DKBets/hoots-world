# Girl Old Testament voice machine QA — 2026-11-17

Machine content check of `kids-bible-audio/sample1` (Old Testament chapters)
against the retold kids text in longroad-ios release-1.2-build9 BibleApp/Resources/KidsBible.
Audio blobs are hashed in the jsonl (sha256 and sha1).
No audio was added or changed.

## Excluded

No Old Testament chapter was already PASS in qa/*.jsonl on origin/lab-audio. Every girl Old Testament chapter is in scope. New Testament files in sample1/ are not this shard.

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

UNSURE in the jsonl (shown as UNCERTAIN here) means the models disagree,
one model did not finish, or coverage stayed between the pass and fail lines.
A single model never passes. If the full-file transcripts disagree, both
models are run again on short windows of the first 36 seconds. The same
5-word phrase in both windows, and not in the source, fails the chapter.
Each disputed span is then transcribed again from that slice of the audio.
Both models hearing the defect fails the chapter. Both hearing the source
words clears that span. A split slice stays UNCERTAIN.

## Counts

- Scored chapters: 10
- PASS: 0
- FAIL: 9
- UNCERTAIN: 1 (jsonl verdict UNSURE)
- Still to score: 919 Old Testament chapters

## PASS

None yet.

## FAIL

- **Genesis 2** — missing verse 11 at 1:51 — "It flows all around the land of Havilah where there is gold The gold of that land is good Sweet smelling resin and onyx stones are there too The second river is named Gihon" (small.en+medium.en)
  - audio check: unclear: missing verse 11 1:37-1:46 (slice coverage small 0.50, medium 0.50)
  - WER small 0.1528 / medium 0.2971; coverage small 0.8489 / medium 0.7114; duration 188.25s vs expected 235.6s (ratio 0.799); sha256 `00accc7e8face842622ca3f78b6c617e27e74797bbed2ecc9d54c5912be61891`
- **Genesis 3** — missing verse 1 at 0:00–0:02 — "Now the snake was sneakier than any wild animal the LORD God had made The snake said to the woman Did God really say You must not eat from any tree in the garden The woman answered the snake We may eat fruit from the trees in the garden But God said Do not eat fruit from the tree in …" (small.en)
- **Genesis 3** — missing verse 22 at 2:52 — "the man has become like one of us knowing good and evil Now he must not reach out and take fruit from" (medium.en)
  - audio check: unclear: missing verse 1 0:00-0:09 (slice coverage small 0.00, medium 0.00) confirmed: missing verse 22 2:44-2:53 (slice coverage small 0.25, medium 0.25)
  - WER small 0.1513 / medium 0.0702; coverage small 0.8565 / medium 0.936; duration 204.03s vs expected 256.4s (ratio 0.796); sha256 `494264005916df0ebcff4de701994317abc126f313f4191df44e48e2a930be6f`
- **Genesis 4** — coverage low on both models (small 0.847, medium 0.741); models also disagree on other spans; agreed defects still fail the chapter
  - WER small 0.1628 / medium 0.2641; coverage small 0.8472 / medium 0.7409; duration 215.17s vs expected 240.8s (ratio 0.894); sha256 `2f0cda25f81b47f304884ff055763afcaac2fc9a0f3cf607839ecb507604e8af`
- **Genesis 5** — coverage low on both models (small 0.872, medium 0.798); models also disagree on other spans; agreed defects still fail the chapter
  - WER small 0.1276 / medium 0.2227; coverage small 0.8724 / medium 0.7981; duration 175.74s vs expected 172.4s (ratio 1.019); sha256 `d5014b609e951cba73dd18f42dc5e57e510590fcf151580e67e509de8f1f616a`
- **Genesis 6** — missing verse 9 at 1:31 — "Noah was a good man who did what was right No one in his time could find any wrong in him Noah walked closely with God" (medium.en)
  - audio check: confirmed: missing verse 9 1:21-1:30 (slice coverage small 0.08, medium 0.08)
  - WER small 0.0041 / medium 0.2053; coverage small 0.998 / medium 0.8008; duration 172.12s vs expected 196.8s (ratio 0.875); sha256 `02159b9d6d7cefc82fc25a710eabefc7aa7e61d0b18b28bb98078432f57328a7`
- **Genesis 7** — missing verse 1 at 0:00–0:01 — "The LORD said to Noah Go into the boat with your whole family I have seen that you are the one person in this time who does what is right Take seven pairs of every kind of clean animal with you a male and a female Take one pair" (small.en+medium.en)
- **Genesis 7** — missing verse 23 at 2:42 — "earth people animals crawling things and birds Only Noah was left and everyone with him in" (small.en+medium.en)
  - audio check: unclear: missing verse 1 0:00-0:09 (slice coverage small 0.00, medium 0.00) refuted: missing verse 23 2:33-2:43 (slice coverage small 0.83, medium 0.83)
  - WER small 0.3333 / medium 0.3996; coverage small 0.8146 / medium 0.6071; duration 164.14s vs expected 181.2s (ratio 0.906); sha256 `c112e7127eb19210369455888fe7fe5b1caf3f7ba35bbf3af2491fba46f0888d`
- **Genesis 8** — coverage low on both models (small 0.844, medium 0.802); models also disagree on other spans; agreed defects still fail the chapter
  - WER small 0.164 / medium 0.1976; coverage small 0.8439 / medium 0.8024; duration 174.89s vs expected 202.4s (ratio 0.864); sha256 `79f3d96e7cd5d710d6410d8b916c5f2c92ebb79d5f9a9001974ba42e40740538`
- **Genesis 9** — missing verse 17 at 2:09 — "with all living things on the earth" (small.en+medium.en)
- **Genesis 9** — inserted verse 19 at 2:21 — "came out of the big boat" (small.en+medium.en)
  - audio check: refuted: missing verse 17 2:00-2:10 (slice coverage small 1.00, medium 1.00) unclear: inserted verse 19 2:20-2:32 (slice coverage small 0.50, medium 0.50)
  - WER small 0.3344 / medium 0.2512; coverage small 0.6805 / medium 0.7521; duration 202.45s vs expected 240.4s (ratio 0.842); sha256 `1f2cb76f2da39bc229b6b8967009daf367d84fb31e9f582aae8f466514c9916b`
- **Genesis 10** — inserted verse 25 at 2:29–2:36 — "Peleg lived in the days of the deep rebirth of Egypt Jepath is a name of the distant family of Rachel and Whelan" (small.en+medium.en)
  - audio check: confirmed: inserted verse 25 2:28-2:42 (slice coverage small 0.96, medium 0.91)
  - WER small 0.1526 / medium 0.4601; coverage small 0.9021 / medium 0.5968; duration 197.93s vs expected 175.6s (ratio 1.127); sha256 `21c9f5e60029c7707432b635e4359904c70e3c7aa70cd89c313f9ef73337ebc6`

## UNCERTAIN

- **Genesis 1** — audio slice contains the disputed words; the models still disagree (coverage small 0.981, medium 0.810)
  - audio check: refuted: repeated verse 27 3:32-3:41 (slice coverage small 1.00, medium 1.00, times 1/1)
  - audio slice contains the disputed words; the models still disagree (coverage small 0.981, medium 0.810); WER small 0.0187 / medium 0.1936; coverage small 0.9813 / medium 0.8104; sha256 `86ba1ba1ef465ab70417e00f1968b46b5e27a6c2709321bc4ba53277ed521b4b`

## Script

`qa/girl_ot_machine_qa.py` resumes from the jsonl. It only reads audio.

