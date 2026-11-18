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

- Scored chapters: 20
- PASS: 0
- FAIL: 14
- UNCERTAIN: 6 (jsonl verdict UNSURE)
- Still to score: 909 Old Testament chapters

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
- **Genesis 11** — missing verse 4 at 0:55 — "for ourselves Then we won't be scattered all over the earth The LORD came down to see the city and the tower the people were building The LORD said Look They are one people and they all speak one language This is only the beginning of what they will do Now nothing they plan will be too hard for them …" (small.en+medium.en)
  - audio check: unclear: missing verse 4 0:23-0:32 (slice coverage small 0.67, medium 0.67)
  - WER small 0.2185 / medium 0.2133; coverage small 0.7902 / medium 0.792; duration 219.61s vs expected 228.8s (ratio 0.96); sha256 `8e0e67cff41b41880fa9aec31793c6cf6dcffdb0b798a6b6bc66fd74f0b5d28e`
- **Genesis 12** — inserted verse 6 at 0:55–1:05 — "The Lord of Brant Then Abram said in Haran's golden peace says The Lord blesses those who bless you and curses those who hurt you" (small.en+medium.en)
- **Genesis 12** — inserted verse 7 at 1:06–1:09 — "remembered God's promise and invited Abraham to come" (small.en+medium.en)
- **Genesis 12** — inserted verse 7 at 1:09–1:11 — "the temple and his attic promise" (small.en+medium.en)
- **Genesis 12** — inserted verse 7 at 1:12–2:12 — "said as I had been the Lord blesses the nation of Abraham and invited Abraham to come to the temple and his the attic promise The king Isaac also blessed Abraham and Evan navigated to the temple and his attic promise The name Evan sounds and invites Abraham to come to the temple and his attic promise The Lord was …" (small.en+medium.en)
- **Genesis 12** — repeated verse 7 at 1:16–1:19 — "and invited Abraham to come to the temple and his" (small.en+medium.en)
- **Genesis 12** — repeated verse 7 at 1:29–1:33 — "Abraham to come to the temple and his attic promise The" (small.en+medium.en)
- **Genesis 12** — repeated verse 7 at 1:57–2:00 — "Abraham married a son of the same age as his wife" (small.en+medium.en)
- **Genesis 12** — repeated verse 7 at 2:04–2:07 — "Abraham married a son of the same age as his wife" (small.en+medium.en)
  - audio check: unclear: inserted verse 7 1:11-1:35 (slice coverage small 1.00, medium 0.29) unclear: inserted verse 6 0:54-1:11 (slice coverage small 0.88, medium 0.17) refuted: repeated verse 7 1:28-1:39 (slice coverage small 0.91, medium 1.00, times 0/1)
  - WER small 0.4632 / medium 0.5736; coverage small 0.9935 / medium 0.6277; duration 233.3s vs expected 184.8s (ratio 1.262); sha256 `9b839e3906b6850d3b95b52040fbfc40a10a286bf048c4b3726d456257df9764`
- **Genesis 15** — inserted verse 9 at 1:17–2:25 — "Abram brought all these animals to the Lord Then Abram brought them all together and kept them in a cozy barn and made them in a toasting furnace The Lord believed Abram's trust and he waved his exapatite The Lord promised Abram You will get everything you want There will no doubts in your mind Never tell you what will …" (small.en+medium.en)
- **Genesis 15** — repeated verse 9 at 2:02–2:04 — "The Lord brought Abram a past fat" (small.en+medium.en)
- **Genesis 15** — repeated verse 9 at 2:15–2:21 — "The Lord brought Abram a past fat and a memorable mega a dove of hen a dove of" (small.en+medium.en)
- **Genesis 15** — repeated verse 9 at 2:24–2:26 — "and a lazy stag of eggs Abram" (small.en+medium.en)
- **Genesis 15** — repeated verse 10 at 2:26–2:28 — "Abram brought all these animals to the" (small.en+medium.en)
  - audio check: confirmed: inserted verse 9 1:16-1:40 (slice coverage small 1.00, medium 1.00) refuted: repeated verse 9 2:14-2:27 (slice coverage small 1.00, medium 0.00, times 1/0) refuted: repeated verse 9 2:01-2:10 (slice coverage small 1.00, medium 1.00, times 1/1)
  - WER small 0.5298 / medium 0.5787; coverage small 0.8894 / medium 0.6681; duration 240.73s vs expected 188.0s (ratio 1.28); sha256 `0042e579a790759ca785809c43fd48e7830f13120d45220df8c5e52a4dfd800b`
- **Genesis 16** — missing verse 2 at 0:19 — "Abram did what Sarai said" (small.en+medium.en)
  - audio check: unclear: missing verse 2 0:10-0:20 (slice coverage small 1.00, medium 0.00)
  - WER small 0.1806 / medium 0.2408; coverage small 0.8194 / medium 0.7618; duration 134.02s vs expected 152.8s (ratio 0.877); sha256 `8121a580f1c285f6bb2cab32cd631e428a6d6092aeb7c5b380a3746322b5fc7f`
- **Genesis 19** — inserted verse 24 at 3:18–4:12 — "onto Sodom and Gomorrah I will judge them as I always saw by their all generations and ancestors But the woman who had been brought with her was left in the middle of the new seed And the land was so moved into the heaven and a great pleas fair that every narrative of the book shows in the narrative …" (small.en+medium.en)
- **Genesis 19** — inserted verse 24 at 4:12–4:29 — "breeches and one save was richly made with fire And one night Nana saw that a man was gifting a blessing of great weight And one night Nana saw that a man was gifting of great weight And one night Nana saw that a man was gifted of great weight" (small.en+medium.en)
- **Genesis 19** — inserted verse 24 at 4:30–4:32 — "one night Nana saw that Amlan" (small.en+medium.en)
- **Genesis 19** — repeated verse 24 at 3:52–3:54 — "the name of God's saved man" (small.en+medium.en)
- **Genesis 19** — repeated verse 24 at 4:16–4:18 — "And one night Nana saw that" (small.en+medium.en)
- **Genesis 19** — repeated verse 24 at 4:21–4:24 — "And one night Nana saw that a man was gifting" (small.en+medium.en)
  - audio check: confirmed: inserted verse 24 3:17-3:41 (slice coverage small 1.00, medium 1.00) confirmed: inserted verse 24 4:11-4:35 (slice coverage small 1.00, medium 0.96) refuted: repeated verse 24 4:20-4:30 (slice coverage small 0.90, medium 1.00, times 0/1)
  - WER small 0.2454 / medium 0.3388; coverage small 0.9661 / medium 0.8737; duration 384.6s vs expected 389.6s (ratio 0.987); sha256 `b5b34f7b1f08ad250e31c43cdabdf8afd35672ff0cd336240d86148a865f4100`

## UNCERTAIN

- **Genesis 1** — audio slice contains the disputed words; the models still disagree (coverage small 0.981, medium 0.810)
  - audio check: refuted: repeated verse 27 3:32-3:41 (slice coverage small 1.00, medium 1.00, times 1/1)
  - audio slice contains the disputed words; the models still disagree (coverage small 0.981, medium 0.810); WER small 0.0187 / medium 0.1936; coverage small 0.9813 / medium 0.8104; sha256 `86ba1ba1ef465ab70417e00f1968b46b5e27a6c2709321bc4ba53277ed521b4b`
- **Genesis 13** — audio slice contains the disputed words; the models still disagree (coverage small 0.750, medium 0.693)
  - audio check: refuted: missing verse 18 2:08-2:18 (slice coverage small 1.00, medium 1.00)
  - audio slice contains the disputed words; the models still disagree (coverage small 0.750, medium 0.693); WER small 0.2524 / medium 0.3119; coverage small 0.75 / medium 0.6929; sha256 `5ed0630b5aeb25ce45172dc3461eaf3c929be1c5d092a451d64a86d2cc2ec50c`
- **Genesis 14** — inserted verse 4 at 0:30 — "they joined the Valley of Sidim which is also called the" (small.en)
- **Genesis 14** — missing verse 2 at 0:43 — "king of Zeboiim and the" (medium.en)
  - audio check: refuted: inserted verse 4 0:29-0:41 (slice coverage small 0.27, medium 0.27) unclear: missing verse 2 0:34-0:44 (slice coverage small 0.40, medium 0.40)
  - small.en only: inserted 'they joined the Valley of Sidim which is also called the'; medium.en only: missing 'king of Zeboiim and the'; coverage unclear (small 0.938, medium 0.628; pass needs both >= 0.96); WER backstop on one model (small 0.090, medium 0.377); WER small 0.0905 / medium 0.3769; coverage small 0.938 / medium 0.6281; sha256 `ef5c4978a521e26ca2bb37c5d4485b40e7b011121d4b05909e44501c431ae39d`
- **Genesis 17** — missing verse 4 at 0:22 — "will be the father of many nations Your name will not be Abram anymore Your name" (medium.en)
  - audio check: unclear: missing verse 4 0:13-0:23 (slice coverage small 0.25, medium 0.42)
  - medium.en only: missing 'will be the father of many nations Your name will not be Abram anymore Your name'; coverage unclear (small 0.995, medium 0.784; pass needs both >= 0.96); WER small 0.0082 / medium 0.2209; coverage small 0.9951 / medium 0.784; sha256 `c8e7e4f8a2913a16d39686f8ffa099abee21c481c0906ea8acdcaee39caaced3`
- **Genesis 18** — missing verse 1 at 0:00–0:02 — "The LORD appeared to Abraham by the big oak trees of Mamre Abraham was sitting at the door of his tent in the hottest part of the day He looked up and saw three men standing nearby When he saw them he ran from his tent to meet them He bowed low to the ground He said My lord if …" (medium.en)
  - audio check: unclear: missing verse 1 0:00-0:09 (slice coverage small 1.00, medium 0.00)
  - medium.en only: missing 'The LORD appeared to Abraham by the big oak trees of Mamre Abraham was sitting at the door of his tent in the hottest part of the day He looked up and saw three men standing nearby When he saw them he ran from his tent to meet them He bowed low to the ground He said My lord if …'; coverage unclear (small 1.000, medium 0.643; pass needs both >= 0.96); WER backstop on one model (small 0.001, medium 0.357); WER small 0.0013 / medium 0.3567; coverage small 1.0 / medium 0.6433; sha256 `bf6c8c6e89d66fc4b4a09b8a99426cab75de8327378ad7d9e45b25c05bf40180`
- **Genesis 20** — missing verse 3 at 0:21 — "You are going to die because of" (medium.en)
  - audio check: unclear: missing verse 3 0:12-0:22 (slice coverage small 0.71, medium 0.71)
  - medium.en only: missing 'You are going to die because of'; coverage unclear (small 0.984, medium 0.910; pass needs both >= 0.96); WER small 0.023 / medium 0.0922; coverage small 0.9839 / medium 0.9101; sha256 `78556b073cbb1ce3ca96f79a48bb4bf12ee024c3f2a503104ee9c24eef0bd7d2`

## Script

`qa/girl_ot_machine_qa.py` resumes from the jsonl. It only reads audio.

