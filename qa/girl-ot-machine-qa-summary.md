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
- FAIL: 6
- UNCERTAIN: 4 (jsonl verdict UNSURE)
- Still to score: 919 Old Testament chapters

## PASS

None yet.

## FAIL

- **Genesis 3** — missing verse 1 at 0:24–0:28 — "Now the snake was sneakier than any wild animal the LORD God had made The snake said to the woman Did God really say You must not eat from any tree in the garden The woman answered the snake We may eat fruit from the trees in the garden But God said Do not eat fruit from the tree in …" (small.en+medium.en)
  - audio check: unclear: missing verse 1 0:00-0:24 (slice coverage small 0.00, medium 0.00)
  - WER small 0.1654 / medium 0.156; coverage small 0.8346 / medium 0.8518; duration 204.03s vs expected 256.4s (ratio 0.796); sha256 `494264005916df0ebcff4de701994317abc126f313f4191df44e48e2a930be6f`
- **Genesis 4** — missing verse 1 at 0:00–0:02 — "Adam and his wife Eve came together and she became pregnant She had a son named Cain She said With the LORD's help I have had a baby boy Later she had another son Cain's brother Abel Abel took care of sheep Cain worked the ground and grew crops After a while Cain brought some of his crops as a …" (small.en+medium.en)
- **Genesis 4** — missing verse 14 at 1:55 — "Anyone who finds me will kill me The LORD said to him No If anyone kills Cain that" (small.en+medium.en)
  - audio check: unclear: missing verse 1 0:00-0:02 (slice coverage small 0.00, medium 0.00) refuted: missing verse 14 1:43-1:57 (slice coverage small 1.00, medium 1.00)
  - WER small 0.2143 / medium 0.2276; coverage small 0.789 / medium 0.7757; duration 215.17s vs expected 240.8s (ratio 0.894); sha256 `2f0cda25f81b47f304884ff055763afcaac2fc9a0f3cf607839ecb507604e8af`
- **Genesis 5** — inserted verse ? at 0:28 — "thirty years in all and" (small.en+medium.en windows)
- **Genesis 5** — inserted verse 13 at 1:10–1:11 — "eight eight hundred and forty" (small.en)
- **Genesis 5** — missing verse 1 at 0:29–0:30 — "This is the written list of Adam's family When God made people he made them to be like himself He made them male and female and he blessed them On the day they were made he called them people When Adam was 130 years old he had a son who was like him He named him Seth After Seth was …" (medium.en)
  - audio check: refuted: missing verse 1 0:00-0:24 (slice coverage small 1.00, medium 1.00) refuted: inserted verse 13 1:09-1:17 (slice coverage small 0.20, medium 0.20) confirmed: inserted verse ? 0:27-0:39 (slice coverage small 0.80, medium 0.80)
  - WER small 0.0557 / medium 0.348; coverage small 0.9698 / medium 0.6566; duration 175.74s vs expected 172.4s (ratio 1.019); sha256 `d5014b609e951cba73dd18f42dc5e57e510590fcf151580e67e509de8f1f616a`
- **Genesis 6** — inserted before verse 1 at 0:14 — "that was when gods son" (small.en+medium.en windows)
- **Genesis 6** — missing verse 1 at 0:00–0:02 — "People began to grow in number all over the earth and daughters were born to them God's sons saw that the daughters of people were beautiful They married any of them they wanted The LORD said My Spirit will not keep struggling with people forever They are only human So they will live 120 years The Nephilim were on the …" (small.en)
  - audio check: unclear: missing verse 1 0:00-0:02 (slice coverage small 0.00, medium 0.00) refuted: inserted verse ? 0:13-0:25 (slice coverage small 0.00, medium 0.00)
  - WER small 0.1626 / medium 0.0041; coverage small 0.8374 / medium 0.998; duration 172.12s vs expected 196.8s (ratio 0.875); sha256 `02159b9d6d7cefc82fc25a710eabefc7aa7e61d0b18b28bb98078432f57328a7`
- **Genesis 7** — coverage low on both models (small 0.815, medium 0.874); models also disagree on other spans; agreed defects still fail the chapter
  - WER small 0.1854 / medium 0.1325; coverage small 0.8146 / medium 0.8742; duration 164.14s vs expected 181.2s (ratio 0.906); sha256 `c112e7127eb19210369455888fe7fe5b1caf3f7ba35bbf3af2491fba46f0888d`
- **Genesis 10** — inserted verse 25 at 2:29–2:36 — "Peleg lived in the days of the deep rebirth of Egypt Jepath is a name of the distant family of Rachel and Whelan" (small.en+medium.en)
  - audio check: confirmed: inserted verse 25 2:28-2:42 (slice coverage small 0.96, medium 0.91)
  - WER small 0.2255 / medium 0.2141; coverage small 0.8314 / medium 0.7904; duration 197.93s vs expected 175.6s (ratio 1.127); sha256 `21c9f5e60029c7707432b635e4359904c70e3c7aa70cd89c313f9ef73337ebc6`

## UNCERTAIN

- **Genesis 1** — missing verse 1 at 0:29–0:30 — "In the very beginning God made the sky above and the earth below The earth had no shape yet and it was empty It was dark over the deep water God's Spirit was moving over the water God said Let there be light And there was light God saw that the light was good God split the light apart from …" (medium.en)
  - audio check: unclear: missing verse 1 0:00-0:24 (slice coverage small 1.00, medium 0.00)
  - medium.en only: missing 'In the very beginning God made the sky above and the earth below The earth had no shape yet and it was empty It was dark over the deep water God's Spirit was moving over the water God said Let there be light And there was light God saw that the light was good God split the light apart from …'; coverage unclear (small 0.999, medium 0.764; pass needs both >= 0.96); WER small 0.004 / medium 0.2417; coverage small 0.9987 / medium 0.7637; sha256 `86ba1ba1ef465ab70417e00f1968b46b5e27a6c2709321bc4ba53277ed521b4b`
- **Genesis 2** — audio slice contains the disputed words; the models still disagree (coverage small 0.995, medium 0.825)
  - audio check: refuted: missing verse 1 0:00-0:24 (slice coverage small 1.00, medium 1.00)
  - audio slice contains the disputed words; the models still disagree (coverage small 0.995, medium 0.825); WER small 0.0051 / medium 0.1766; coverage small 0.9949 / medium 0.8251; sha256 `00accc7e8face842622ca3f78b6c617e27e74797bbed2ecc9d54c5912be61891`
- **Genesis 8** — missing verse 1 at 0:29–0:30 — "But God remembered Noah and all the animals with him in the boat God sent a wind to blow over the earth and the water began to go down The water under the earth stopped bursting out The windows of the sky were closed and the rain stopped Little by little the water went down from the earth After 150 …" (medium.en)
  - audio check: unclear: missing verse 1 0:00-0:24 (slice coverage small 1.00, medium 0.00)
  - medium.en only: missing 'But God remembered Noah and all the animals with him in the boat God sent a wind to blow over the earth and the water began to go down The water under the earth stopped bursting out The windows of the sky were closed and the rain stopped Little by little the water went down from the earth After 150 …'; coverage unclear (small 0.986, medium 0.373; pass needs both >= 0.96); WER backstop on one model (small 0.020, medium 0.626); WER small 0.0198 / medium 0.6265; coverage small 0.9862 / medium 0.3735; sha256 `79f3d96e7cd5d710d6410d8b916c5f2c92ebb79d5f9a9001974ba42e40740538`
- **Genesis 9** — missing verse 1 at 0:00–0:02 — "God blessed Noah and his sons He said to them Have many children Fill the earth again Every animal on the earth and every bird in the sky will be afraid of you Everything that moves on the ground and all the fish in the sea are put in your care Every living thing that moves can be food for …" (medium.en)
  - audio check: unclear: missing verse 1 0:00-0:02 (slice coverage small 0.00, medium 0.00)
  - medium.en only: missing 'God blessed Noah and his sons He said to them Have many children Fill the earth again Every animal on the earth and every bird in the sky will be afraid of you Everything that moves on the ground and all the fish in the sea are put in your care Every living thing that moves can be food for …'; coverage unclear (small 0.995, medium 0.800; pass needs both >= 0.96); WER small 0.0083 / medium 0.2146; coverage small 0.995 / medium 0.8003; sha256 `1f2cb76f2da39bc229b6b8967009daf367d84fb31e9f582aae8f466514c9916b`

## Script

`qa/girl_ot_machine_qa.py` resumes from the jsonl. It only reads audio.

