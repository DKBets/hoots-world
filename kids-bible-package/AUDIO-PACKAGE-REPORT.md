# Kids Bible narration package

Audio tree: `lab-audio` at `044090657f7eeb258692ff793a1874e400207f4a`, plus the story 10 overrides from PR #2 (`b6fab24`). This branch merges that PR in. The pull request is based on `kids-story-10-baby-moses-overrides` so those override files stay with PR #2.

Chapters are in `kids-bible-audio/sample1` (girl) and `kids-bible-audio/boy`. Stories are in `long-road-kids-audio/<same>/stories`. Overrides live in `kids-bible-audio/overrides/` and win when present.

## Recommendation

Ship both voices, all 66 books, all 1,189 chapters, and all 50 stories.

Files at or below −1.0 dBTP are an ffmpeg stream copy. Files above −1.0 dBTP are decoded, true-peak limited, and re-encoded as AAC-LC mono at 24 kHz and that file’s own stream bitrate. Story 10 for both voices comes from the trimmed override, not the untrimmed lab-audio file.

| | |
| --- | ---: |
| Package audio | **2,461,032,628 bytes** (2,347.0 MiB, 2.292 GiB) |
| Plus 300 MiB non-audio | **2,775,605,428 bytes** (2,647.1 MiB, 2.586 GiB) |
| Headroom under 4 GiB | **1,519,361,868 bytes** (1,449.0 MiB, 1.415 GiB) |
| Headroom inside the 400 MiB margin | **1,099,931,468 bytes** (1,049.0 MiB) |
| Peak-limited files | 2,346 |
| Stream copies | 132 |
| Overrides used | 2 (girl and boy story 10) |

The audio budget is 4 GiB − 300 MiB − 400 MiB = 3,560,964,096 bytes. This package is inside it.

Left out: the 14 diagnostic takes in `kids-bible-audio/boy/Revelation/diagnostic-rev5/` (638,745 bytes). They are not chapters.

## Peak fix

Trigger: true peak above −1.0 dBTP. Master target for a re-encoded file: −1.5 dBTP.

The PCM limiter is ffmpeg `alimiter` after a 4× resample (24 kHz → 96 kHz), with `level=false` so quiet audio is not turned up, `latency=true`, attack 1 ms, release 80 ms. The first ceiling is −2.7 dB. That is the −1.5 dBTP target plus the overshoot libfdk-aac adds at about 32 kbps. The encoded file is measured. If it is still above −1.5 dBTP, the ceiling drops by at least 1.5 dB and the file is encoded again (up to 5 tries).

ffmpeg’s built-in AAC encoder cannot hold this target. A PCM file limited to −1.5 dBTP came back near 0 dBTP after that encoder at 32 kbps. The re-encode uses `fdkaac -p 2` (libfdk-aac AAC-LC), then a faststart remux. `fdkaac` has to be on PATH.

On this build: 2,187 files passed on the first encode, 145 on the second, 14 on the third. None of the re-encoded files are above −1.5 dBTP. The hottest file in the whole package is −1.0 dBTP, and it is a stream copy.

Loudness change on the 2,346 limited files (after minus before):

| | LUFS |
| --- | ---: |
| Median | −0.3 |
| Mean | −0.30 |
| Smallest drop | −0.1 |
| Largest drop | −1.1 |
| Files that dropped 0.5 dB or more | 85 |
| Files that dropped 1.0 dB or more | 2 |

The limiter does not aim at a new integrated-loudness target. The drops are the peaks it reduced, plus a lower ceiling on files whose AAC encode overshot. Boy Psalms 31 started at +0.4 dBTP and needed a −4.2 dB PCM ceiling; integrated loudness went from −17.2 to −18.1 LUFS and the encoded true peak is −1.7 dBTP.

67 stream copies are still above −1.5 dBTP and at or below −1.0 dBTP, so the trigger did not touch them. The loudest of those is −1.0 dBTP. Boy story 10 (the override) is one of them.

## Overrides

`build_kids_bible_audio_package.py` calls `story_source()` in `kids-bible-audio/overrides/prefer_override.py`. For chapters it calls `prefer_override()` on `kids-bible-audio/overrides/chapters/<source_dir>/<Book>/<n>.m4a`, which is empty today.

When an override file is used, the script checks two hashes and stops if either fails:

- The override file must match `sha256` in `overrides/manifest.json`.
- The lab-audio file named in `replaces` must still match `replaces.sha256`. A mismatch is a stale override.

Story 10 in the built manifests:

| Voice | Source | Treatment | True peak | LUFS | Duration |
| --- | --- | --- | ---: | ---: | ---: |
| girl | override | copy | −1.1 dBTP | −17.2 | 65.37 s |
| boy | override | copy | −1.0 dBTP | −18.8 | 71.47 s |

`source` is `"override"`. `sha256_source` is the override file. `replaced_sha256` is the 04409065 blob that was checked. Both replaced hashes matched.

## Quality

Re-encoding is a second AAC generation at about 32 kbps. Time-domain SNR against the source, first 45 seconds:

| File | What happened | SNR |
| --- | --- | ---: |
| Girl Genesis 1 | limited, one pass | 21.8 dB |
| Girl 2 Kings 25 (+5.3 dBTP) | limited, one pass | 19.6 dB |
| Boy 2 Kings 14 | limited, three passes, −0.9 LUFS | 15.7 dB |
| Boy Psalms 31 | limited to a −4.2 dB ceiling | 15.0 dB |
| Stream copy (boy Psalms 21) | copy | 161 dB |
| Girl and boy story 10 | copy of the override | 160 dB |

A copy is the same AAC frames (the residual is decoder delay). A one-pass re-encode at about 20 dB SNR is the mild loss of a second 32 kbps generation: a little softer up top, words intact. The earlier speech-to-text check on a 32 kbps re-encode at about 14 dB SNR had a mean word error of 2.6% against the source transcript. Files that need a deeper ceiling, like Psalms 31, sit nearer 15 dB and lose about 1 dB of integrated loudness. That is the audible risk of holding −1.5 dBTP. The package does not raise quiet passages, and it does not retarget loudness to a new LUFS number.

## Inventory that did not change

2,478 package files, both voices, no missing chapters or stories, no duplicate hashes, no zero-length or undecodable files. Source codec is AAC-LC, mono, 24 kHz. Source integrated loudness sits around −16.4 LUFS. Before this pass, 2,348 package files were above −1.0 dBTP and the hottest was girl 2 Kings 25 at +5.3 dBTP.

## Manifests

`kids-bible-package/build/` holds the manifests from this full pass and `package-summary.json`. No encoded audio is committed. The shape matches longroad-ios PR #3 and `scripts/check_kids_audio.py`:

Girl Genesis 1 from this build:

```json
{
  "book": "GEN",
  "chapter": 1,
  "voice": "girl",
  "file": "GEN/001.m4a",
  "duration": 260.096,
  "size": 1073834,
  "sha256": "71f8907808545052257783126fd306b3beb509f6126016f3c57daaaa890d45e5",
  "sha256_source": "86ba1ba1ef465ab70417e00f1968b46b5e27a6c2709321bc4ba53277ed521b4b",
  "true_peak_dbtp_before": -0.6,
  "true_peak_dbtp_after": -1.9,
  "lufs_before": -16.6,
  "lufs_after": -16.9,
  "treatment": "peak-limit",
  "source": "lab-audio",
  "source_path": "kids-bible-audio/sample1/Genesis/1.m4a"
}
```

Stories use `storyId` and `file` `stories/1.m4a`, with no `book` field, so the checker treats them as stories. `sha256` is the output file. Every one of the 2,478 output files was checked against `size` and `sha256` after the build.

```
python3 kids-bible-package/build_kids_bible_audio_package.py \
  --output /path/to/package
```

The script refuses to write inside the source audio trees. A full package over the audio budget exits non-zero. `--resume` continues from `progress.jsonl`.
