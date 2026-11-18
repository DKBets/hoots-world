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

- Scored chapters: 50
- PASS: 1
- FAIL: 32
- UNCERTAIN: 17 (jsonl verdict UNSURE)
- Still to score: 879 Old Testament chapters

## PASS

1 chapters. Both models agreed there was no missing, invented, or repeated passage.

- Genesis 42

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
- **Genesis 21** — missing verse 14 at 1:49 — "Abraham took some bread and a skin bag of water He gave them to Hagar and put them on her shoulder He sent her away with the boy She wandered in the desert of Beersheba When the water was all gone she put the boy under a bush Then she went and sat down" (small.en+medium.en)
  - audio check: confirmed: missing verse 14 1:28-1:37 (slice coverage small 0.17, medium 0.25)
  - WER small 0.1322 / medium 0.2447; coverage small 0.8678 / medium 0.7584; duration 238.98s vs expected 263.2s (ratio 0.908); sha256 `a2dc90ea8d5ef519974db369de3ca2b5fe7b77e7a176ce7c156bb125b5d1e41c`
- **Genesis 24** — inserted verse 48 at 6:18–7:01 — "the Lord And he praised me and said blessed be the Lord your God And he said blessed be the Lord your God for the great canyon and desert And I again placed my feet and knelt in prayer to the Lord And he asked me if Yahweh God is with you tell me and welcome you in person And …" (small.en+medium.en)
- **Genesis 24** — inserted verse 48 at 7:02–7:23 — "And he asked me if Yahweh God is with you tell me your family is blessed with so many sons And he asked me if Yahweh God is with you tell me your lineage is blessed with so many sons And he asked me if Yahweh God is with you tell me your lineage is blessed with so many sons" (small.en+medium.en)
- **Genesis 24** — repeated verse 48 at 6:16–6:18 — "bowed down and worshipped the Lord" (small.en+medium.en)
- **Genesis 24** — repeated verse 48 at 6:23–6:26 — "said blessed be the Lord your God" (small.en+medium.en)
- **Genesis 24** — repeated verse 48 at 6:44–6:48 — "And he asked me if Yahweh God is with you tell me" (small.en+medium.en)
- **Genesis 24** — repeated verse 48 at 6:57–7:06 — "and I again placed my feet and knelt in prayer to the Lord And he asked me if Yahweh God is with you tell me your" (small.en+medium.en)
- **Genesis 24** — repeated verse 48 at 7:14–7:23 — "is blessed with so many sons And he asked me if Yahweh God is with you tell me your lineage is blessed with so many sons" (small.en+medium.en)
  - audio check: confirmed: inserted verse 48 6:17-6:41 (slice coverage small 1.00, medium 1.00) unclear: inserted verse 48 7:01-7:25 (slice coverage small 1.00, medium 0.00) refuted: repeated verse 48 6:56-7:12 (slice coverage small 1.00, medium 1.00, times 1/1)
  - WER small 0.1606 / medium 0.3044; coverage small 0.9563 / medium 0.7081; duration 590.46s vs expected 640.0s (ratio 0.923); sha256 `80b9131f02b68c960dae8addf02ddf1cfe0f82c0a2ba72feb654be9ae3ac2ebd`
- **Genesis 25** — missing verse 23 at 2:53 — "said to her Two nations are inside you Two peoples will come from you and go separate ways One will be stronger than the other" (small.en)
- **Genesis 25** — missing verse 1 at 0:00–0:01 — "Abraham married another wife Her name was Keturah She had these sons with him Zimran Jokshan Medan Midian Ishbak and Shuah Jokshan was the father of Sheba and Dedan Dedan's sons were the Asshurim the Letushim and the Leummim Midian's sons were Ephah Epher Hanoch Abida and Eldaah All" (medium.en)
  - audio check: refuted: missing verse 1 0:00-0:09 (slice coverage small 1.00, medium 1.00) confirmed: missing verse 23 2:43-2:52 (slice coverage small 0.08, medium 0.08)
  - WER small 0.0821 / medium 0.3176; coverage small 0.9179 / medium 0.69; duration 266.03s vs expected 263.2s (ratio 1.011); sha256 `d3e799f360c7f760cc0eca5368f78f3cc0cabcd9e85558644a70f5099c834a26`
- **Genesis 27** — missing verse 25 at 3:11 — "Bring me some of the meat to eat my son Then I will give you my blessing So Jacob brought it to him and" (small.en+medium.en)
  - audio check: confirmed: missing verse 25 3:01-3:10 (slice coverage small 0.08, medium 0.08)
  - WER small 0.1654 / medium 0.159; coverage small 0.841 / medium 0.8494; duration 367.1s vs expected 432.8s (ratio 0.848); sha256 `b6db3d796671daafa22605fa57b7491ea6bccb7adb349bd48de42d65f058af7f`
- **Genesis 29** — coverage low on both models (small 0.852, medium 0.855); models also disagree on other spans; agreed defects still fail the chapter
  - WER small 0.156 / medium 0.152; coverage small 0.8519 / medium 0.8545; duration 256.73s vs expected 305.2s (ratio 0.841); sha256 `58683f6d1645f21d169fc65137d68af21992acb8a69f7f56641dcf5d9472c04b`
- **Genesis 30** — missing verse 21 at 2:25 — "Later she had a daughter and named her Dinah" (small.en)
- **Genesis 30** — missing verse 15 at 1:36 — "son's mandrakes too Rachel said All right Jacob can spend tonight with you in return for your" (medium.en)
  - audio check: confirmed: missing verse 15 1:27-1:37 (slice coverage small 0.17, medium 0.25) refuted: missing verse 21 2:16-2:26 (slice coverage small 1.00, medium 1.00)
  - WER small 0.0273 / medium 0.1525; coverage small 0.9769 / medium 0.857; duration 340.1s vs expected 380.4s (ratio 0.894); sha256 `443af245b5ee9ebded99968ca653582015bf0acd2711a3f3abc627ee1801e619`
- **Genesis 31** — missing verse 1 at 0:30–0:34 — "heard that Laban's sons were saying" (small.en+medium.en)
- **Genesis 31** — missing verse 1 at 0:35–0:40 — "has taken everything our father owned He got all his riches from our father" (small.en+medium.en)
- **Genesis 31** — missing verse 2 at 0:41–0:45 — "also saw that Laban was not as friendly" (small.en+medium.en)
- **Genesis 31** — inserted verse 1 at 0:30–0:34 — "have been found with his father And the Lord said to" (small.en+medium.en)
- **Genesis 31** — inserted verse 1 at 0:35–0:40 — "Go back to your father's land and get yourself a sizable and use it to build an elaborate tent" (small.en+medium.en)
- **Genesis 31** — inserted verse 2 at 0:41–0:45 — "agreed and went to the village of Nazareth Jacob said" (small.en+medium.en)
- **Genesis 31** — inserted verse 2 at 0:45–0:59 — "his employees Get rid of your ungolawed seba and whether you have any means put it on your camera and get the sons of Nazareth out of your family Jacob said Yes we have seba and it's all in the past" (small.en+medium.en)
- **Genesis 31** — inserted verse 3 at 1:01–1:06 — "you will go into Canaan and you will get 10 of the proceeds of your vineyards" (small.en+medium.en)
- **Genesis 31** — inserted verse 3 at 1:09–1:24 — "into Canaan and whether you have any means out of your vineyards Give me the max in the past Jacob said yes I will give you of the means of your vineyards now in the past in Gaglobeth Jacob said yes I will give you of" (small.en+medium.en)
- **Genesis 31** — inserted verse 3 at 1:25–1:30 — "vineyards now in the past Jacob said yes I will give you of the means of" (small.en+medium.en)
- **Genesis 31** — repeated verse 3 at 1:10–1:12 — "and whether you have any means" (small.en+medium.en)
- **Genesis 31** — repeated verse 3 at 1:15–1:17 — "Jacob said yes I will" (small.en+medium.en)
- **Genesis 31** — repeated verse 3 at 1:21–1:27 — "Jacob said yes I will give you of the means of your vineyards now in the past" (small.en+medium.en)
- **Genesis 31** — repeated verse 3 at 1:26–1:31 — "in the past Jacob said yes I will give you of the means of your vineyards now" (small.en+medium.en)
  - audio check: confirmed: inserted verse 3 1:08-1:30 (slice coverage small 1.00, medium 1.00) unclear: inserted verse 2 0:44-1:05 (slice coverage small 0.96, medium 0.21) confirmed: inserted verse 1 0:34-0:46 (slice coverage small 1.00, medium 1.00)
  - WER small 0.2422 / medium 0.2044; coverage small 0.8533 / medium 0.8985; duration 512.77s vs expected 540.0s (ratio 0.95); sha256 `ea69fb93ef83facca071fc062470e990dc260f55ff0baba40099e194b7cc3d9e`
- **Genesis 32** — coverage low on both models (small 0.876, medium 0.672); models also disagree on other spans; agreed defects still fail the chapter
  - WER small 0.1243 / medium 0.3392; coverage small 0.8757 / medium 0.6716; duration 264.15s vs expected 296.0s (ratio 0.892); sha256 `a28229a9f50b498f61317f89f544da5c837bb4b899d899086c1a8bc0da30bc85`
- **Genesis 35** — inserted verse 14 at 2:36–2:42 — "place Benya we beloved Israel we come from this very special" (small.en+medium.en)
- **Genesis 35** — inserted verse 14 at 2:45–2:47 — "to those safer every day and bake you" (small.en+medium.en)
- **Genesis 35** — inserted verse 15 at 2:57–3:06 — "there was a baby and Azap We come from Benya's son by days where there was a baby and Azap We come" (small.en+medium.en)
- **Genesis 35** — inserted verse 16 at 3:12–3:15 — "Benya's son by days where there was a" (small.en+medium.en)
- **Genesis 35** — inserted verse 18 at 3:32–3:43 — "a baby and A ZAP We come from Benya's son by days where there was a baby and A ZAP Both Benya's sons have buried their and he lost his family" (small.en+medium.en)
  - audio check: confirmed: inserted verse 18 3:31-3:49 (slice coverage small 1.00, medium 0.75) confirmed: inserted verse 15 2:56-3:12 (slice coverage small 0.91, medium 0.82) confirmed: inserted verse 14 2:35-2:48 (slice coverage small 1.00, medium 0.82)
  - WER small 0.4274 / medium 0.3729; coverage small 0.731 / medium 0.9257; duration 300.67s vs expected 242.4s (ratio 1.24); sha256 `0f4311b2887be864073f808b22fba912698912f08746be27408954f4935ea32f`
- **Genesis 36** — coverage low on both models (small 0.750, medium 0.725); models also disagree on other spans; agreed defects still fail the chapter
  - WER small 0.258 / medium 0.2786; coverage small 0.7497 / medium 0.7253; duration 323.5s vs expected 311.6s (ratio 1.038); sha256 `a2e9a8188e51740a0d4f995a50c48c4a6bed78f7da8e717ee7119a8550d01426`
- **Genesis 37** — coverage low on both models (small 0.891, medium 0.832); models also disagree on other spans; agreed defects still fail the chapter
  - WER small 0.1122 / medium 0.1701; coverage small 0.8912 / medium 0.8322; duration 289.92s vs expected 352.8s (ratio 0.822); sha256 `89c42d1baca89ec68409dcba0f70ff1f2113c53e4ece4d7d81142e8cb7ac2738`
- **Genesis 38** — coverage low on both models (small 0.877, medium 0.812); models also disagree on other spans; agreed defects still fail the chapter
  - WER small 0.1268 / medium 0.1949; coverage small 0.8772 / medium 0.8117; duration 255.79s vs expected 299.6s (ratio 0.854); sha256 `74ed4c72649c9f903319ffd96d0b40c99f7d5ddbb7d0339ca0cabdcdd42864ef`
- **Genesis 40** — repeated verse 20 at 2:29–2:31 — "bearer and the chief baker" (small.en)
- **Genesis 40** — missing verse 9 at 1:22 — "cupbearer told Joseph his dream He said In my dream I saw a grapevine in front of me The vine had three branches As soon as it started to bud it bloomed Then its bunches of grapes became ripe I was holding Pharaoh's cup I took the grapes and squeezed them into Pharaoh's cup Then I put the" (medium.en)
  - audio check: confirmed: missing verse 9 0:59-1:08 (slice coverage small 0.00, medium 0.00) refuted: repeated verse 20 2:28-2:37 (slice coverage small 1.00, medium 1.00, times 1/1)
  - WER small 0.0487 / medium 0.1988; coverage small 0.9727 / medium 0.8109; duration 166.66s vs expected 205.2s (ratio 0.812); sha256 `9b3897f8b15f66f8e3e404efb13d3c674d970a97f65072eb23e9a63db509b3fc`
- **Genesis 41** — missing verse 1 at 0:04 — "Pharaoh had a dream He was standing by the Nile River Seven cows came up out of the river They were healthy and fat and they ate the grass by the river Then seven other cows came up out of the river after them They were ugly and skinny They stood beside the fat cows on the riverbank Then the …" (small.en+medium.en)
  - audio check: unclear: missing verse 1 0:00-0:09 (slice coverage small 1.00, medium 0.00)
  - WER small 0.1954 / medium 0.1356; coverage small 0.8123 / medium 0.8728; duration 456.19s vs expected 522.0s (ratio 0.874); sha256 `18389824c3e2cd3f52655beef0a0a78144e74cf739afab361bc37db05f59b053`
- **Genesis 44** — coverage low on both models (small 0.884, medium 0.732); models also disagree on other spans; agreed defects still fail the chapter
  - WER small 0.1156 / medium 0.2706; coverage small 0.8844 / medium 0.7318; duration 261.38s vs expected 335.6s (ratio 0.779); sha256 `0424ce127a104a8587069a96269b28a3887d8b417eb009e914ddc3cecc855b21`
- **Genesis 45** — missing verse 5 at 1:26 — "be angry with yourselves for selling me here God sent me ahead of you to save people's lives For two years now there has been famine in the land And for five more years there will be no plowing and no harvest God sent me ahead of you to keep your family alive on the earth He did it to …" (medium.en)
  - audio check: confirmed: missing verse 5 0:46-0:55 (slice coverage small 0.08, medium 0.08)
  - WER small 0.0059 / medium 0.2386; coverage small 0.9956 / medium 0.7673; duration 236.16s vs expected 271.6s (ratio 0.87); sha256 `1ffe00fb25ca2fae258e84e9bccc3f5d1ae6e0e578b8fbde36ffd5a04a60ca27`
- **Genesis 46** — missing verse 14 at 1:58 — "Zebulun's sons were Sered Elon and Jahleel These were the sons Leah had with Jacob in Paddan Aram She also had a daughter Dinah Altogether there were 33 sons and daughters and grandchildren in this part of the family Gad's sons were Ziphion Haggi Shuni Ezbon Eri Arodi and Areli" (small.en+medium.en)
  - audio check: unclear: missing verse 14 1:38-1:47 (slice coverage small 0.58, medium 0.58)
  - WER small 0.2482 / medium 0.254; coverage small 0.7518 / medium 0.746; duration 263.17s vs expected 272.4s (ratio 0.966); sha256 `c0bbc258cd110393ee1ee60c11501fafc22df1b7b55ca55d78ce0036291ed424`
- **Genesis 50** — inserted verse 8 at 1:11–1:12 — "their little children and their children and" (small.en)
- **Genesis 50** — missing verse 26 at ? — "and he was placed in a coffin in Egypt" (medium.en)
  - audio check: confirmed: inserted verse 8 1:10-1:18 (slice coverage small 0.86, medium 0.86)
  - WER small 0.0234 / medium 0.0328; coverage small 0.9891 / medium 0.9766; duration 237.48s vs expected 256.0s (ratio 0.928); sha256 `9a749817fc670e4ec039897f45f7867292cfb3bc86d34ba5156bfba5347831c9`

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
- **Genesis 22** — missing verse 4 at 0:58 — "and saw the place far away Abraham said to his servants Stay here with the donkey The boy and I will go over there We will worship" (medium.en)
  - audio check: unclear: missing verse 4 0:47-0:56 (slice coverage small 0.42, medium 0.42)
  - medium.en only: missing 'and saw the place far away Abraham said to his servants Stay here with the donkey The boy and I will go over there We will worship'; coverage unclear (small 0.974, medium 0.593; pass needs both >= 0.96); WER backstop on one model (small 0.029, medium 0.412); WER small 0.0293 / medium 0.4121; coverage small 0.9744 / medium 0.5934; sha256 `17af77c5284d3b175a32cb46d5709bab68051591aed12b0b44645e1cd197342d`
- **Genesis 23** — audio slice contains the disputed words; the models still disagree (coverage small 0.989, medium 0.903)
  - audio check: refuted: repeated verse 16 1:51-1:59 (slice coverage small 0.60, medium 0.60, times 0/0)
  - audio slice contains the disputed words; the models still disagree (coverage small 0.989, medium 0.903); WER small 0.0271 / medium 0.1086; coverage small 0.9887 / medium 0.9027; sha256 `f4d204f58871106a4c6f9936b9e571ab9c14e63549c079ab3338a702a2a32807`
- **Genesis 26** — audio slice contains the disputed words; the models still disagree (coverage small 0.798, medium 0.842)
  - audio check: refuted: missing verse 26 3:37-3:46 (slice coverage small 0.83, medium 0.92) refuted: missing verse 29 3:58-4:08 (slice coverage small 1.00, medium 1.00)
  - audio slice contains the disputed words; the models still disagree (coverage small 0.798, medium 0.842); WER small 0.2072 / medium 0.1638; coverage small 0.7978 / medium 0.8424; sha256 `401125bd31ebf6be30f8c1c6e0d2fb3cf73001b374bd325fa03b69302c92bdab`
- **Genesis 28** — audio slice contains the disputed words; the models still disagree (coverage small 0.981, medium 0.833)
  - audio check: refuted: missing verse 1 0:00-0:09 (slice coverage small 0.92, medium 0.92)
  - audio slice contains the disputed words; the models still disagree (coverage small 0.981, medium 0.833); WER small 0.0195 / medium 0.172; coverage small 0.9805 / medium 0.8333; sha256 `33742cdd9dcefbed568c799ba0729d790429e90e513b90cae0ba213d8c0cc14f`
- **Genesis 33** — missing verse 14 at 2:17 — "until I come to you in Seir Esau said Then let me leave some of my men with you But Jacob said Why do that You have already been so kind to me sir So that day Esau started back home to Seir But Jacob went to Succoth There he built a house for himself and shelters for his animals …" (medium.en)
  - audio check: unclear: missing verse 14 1:47-1:56 (slice coverage small 0.83, medium 0.67)
  - medium.en only: missing 'until I come to you in Seir Esau said Then let me leave some of my men with you But Jacob said Why do that You have already been so kind to me sir So that day Esau started back home to Seir But Jacob went to Succoth There he built a house for himself and shelters for his animals …'; coverage unclear (small 0.987, medium 0.816; pass needs both >= 0.96); WER small 0.0153 / medium 0.1904; coverage small 0.9869 / medium 0.8162; sha256 `edab97e9648f217e5f631ddfd2a7ee46cde547a67537c21490812cc6e636e733`
- **Genesis 34** — repeated verse 20 at 2:16–2:18 — "Haymore and his son Shechem" (small.en)
- **Genesis 34** — missing verse 1 at 0:00–0:02 — "One day Dinah the daughter of Leah and Jacob went out to visit the young women of the land Shechem the son of Hamor the Hivite was the prince of that land He saw Dinah and he took her and did a very wrong and shameful thing to her But then his heart was drawn to Dinah Jacob's daughter He …" (medium.en)
  - audio check: unclear: missing verse 1 0:00-0:09 (slice coverage small 0.92, medium 0.00) refuted: repeated verse 20 2:15-2:24 (slice coverage small 1.00, medium 0.80, times 1/0)
  - small.en only: repeated 'Haymore and his son Shechem'; medium.en only: missing 'One day Dinah the daughter of Leah and Jacob went out to visit the young women of the land Shechem the son of Hamor the Hivite was the prince of that land He saw Dinah and he took her and did a very wrong and shameful thing to her But then his heart was drawn to Dinah Jacob's daughter He …'; coverage unclear (small 0.996, medium 0.843; pass needs both >= 0.96); WER small 0.0057 / medium 0.1617; coverage small 0.9957 / medium 0.8426; sha256 `239a4d17b59c22f8e2b034dd14ef1f60ce694c547337b9596ce3b190a45d35d8`
- **Genesis 39** — audio slice contains the disputed words; the models still disagree (coverage small 0.998, medium 0.872)
  - audio check: refuted: missing verse 17 2:23-2:32 (slice coverage small 1.00, medium 1.00)
  - audio slice contains the disputed words; the models still disagree (coverage small 0.998, medium 0.872); WER small 0.0019 / medium 0.13; coverage small 0.9981 / medium 0.8719; sha256 `d189c067690349ad96e71551238158f66cd24aeffdb94a8224c0f0fd3010d879`
- **Genesis 43** — audio slice contains the disputed words; the models still disagree (coverage small 0.973, medium 0.673)
  - audio check: refuted: missing verse 28 3:42-3:52 (slice coverage small 1.00, medium 1.00)
  - audio slice contains the disputed words; the models still disagree (coverage small 0.973, medium 0.673); WER small 0.043 / medium 0.3315; coverage small 0.9725 / medium 0.6729; sha256 `59b4c1946d30e7e13dabf6c893419aeee2adec502f776470ba8f0266512dc34d`
- **Genesis 47** — audio slice contains the disputed words; the models still disagree (coverage small 0.948, medium 0.576)
  - audio check: refuted: missing verse 15 2:09-2:19 (slice coverage small 1.00, medium 1.00)
  - audio slice contains the disputed words; the models still disagree (coverage small 0.948, medium 0.576); WER small 0.0626 / medium 0.4309; coverage small 0.9481 / medium 0.5762; sha256 `70582e1ad3fe0c73f9ef8b78718fcf219d5fdb13361977a44c0b22b46606b74f`
- **Genesis 48** — audio slice contains the disputed words; the models still disagree (coverage small 0.980, medium 0.711)
  - audio check: refuted: missing verse 4 0:21-0:31 (slice coverage small 1.00, medium 1.00)
  - audio slice contains the disputed words; the models still disagree (coverage small 0.980, medium 0.711); WER small 0.0218 / medium 0.2893; coverage small 0.9798 / medium 0.7107; sha256 `29791a5f7b96ab8934ba6a6c1738ab1cb43cb225e72ceeff2ef25a24379f1300`
- **Genesis 49** — missing verse 7 at 0:56 — "Their rage is cursed because it is so cruel I will scatter" (medium.en)
  - audio check: unclear: missing verse 7 0:47-0:57 (slice coverage small 0.67, medium 0.67)
  - medium.en only: missing 'Their rage is cursed because it is so cruel I will scatter'; coverage unclear (small 0.991, medium 0.836; pass needs both >= 0.96); WER small 0.0116 / medium 0.1848; coverage small 0.991 / medium 0.8359; sha256 `f470b856a2705257c6241ac7790e0d2d6cedc2afb20e2e8ce8b9b9043c845413`

## Script

`qa/girl_ot_machine_qa.py` resumes from the jsonl. It only reads audio.

