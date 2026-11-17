# Kids Bible narration package

Snapshot: `lab-audio` at `044090657f7eeb258692ff793a1874e400207f4a` (includes the re-record fixes landed 10–13 Nov).

Chapters live in `kids-bible-audio/sample1` (girl) and `kids-bible-audio/boy` (boy). Stories live in `long-road-kids-audio/sample1/stories` and `long-road-kids-audio/boy/stories`. The app voice names used below are `girl` and `boy`.

## Recommendation

Ship **both voices, all 66 books, all 1,189 chapters, and all 50 stories**, using the source AAC-LC files as they are.

| | |
| --- | ---: |
| Encoding | AAC-LC, mono, 24 kHz, about 33 kbps, in `.m4a` |
| How it is built | `ffmpeg` stream copy (`-c:a copy -movflags +faststart`). No re-encode |
| Package audio | **2,463,206,070 bytes** (2,349.10 MiB, 2.294 GiB) |
| Non-audio allowance | 300 MiB = 314,572,800 bytes |
| Projected bundle | **2,777,778,870 bytes** (2,649.10 MiB, 2.588 GiB) |
| Apple cap used here | 4 GiB = 4,294,967,296 bytes |
| Headroom under 4 GiB | **1,517,188,426 bytes** (1,446.90 MiB, 1.413 GiB) |
| Comfort margin held back | 400 MiB = 419,430,400 bytes |
| Audio budget (cap − 300 MiB − 400 MiB) | 3,560,964,096 bytes |
| Headroom inside that budget | **1,097,758,026 bytes** (1,046.90 MiB) |

A faststart stream copy does not change the AAC frames. On a 20-file sample the copied files grew by 8 bytes in total. On a real 4-file build every output matched the source length exactly (the sha256 changed because the `moov` atom was rewritten). The built package stays at 2,463,206,070 bytes, plus at most a few bytes per file.

Left out of the bundle: the 14 diagnostic takes in `kids-bible-audio/boy/Revelation/diagnostic-rev5/` (`v01.m4a`–`v14.m4a`). They are not Revelation chapters. Together they are 638,745 bytes and 154.0 seconds. Every canon chapter and every story 1–50 is in, for both voices.

## Inventory

2,492 `.m4a` files. Every one is AAC-LC, one channel, 24,000 Hz, and decodes. None are zero-length.

| Set | Files | Bytes | Duration |
| --- | ---: | ---: | ---: |
| Girl chapters | 1,189 | 1,176,162,918 | 284,174.940 s (78.94 h) |
| Boy chapters | 1,189 | 1,258,032,165 | 303,912.438 s (84.42 h) |
| Girl stories | 50 | 14,057,655 | 3,401.304 s (56.7 min) |
| Boy stories | 50 | 14,953,332 | 3,613.497 s (60.2 min) |
| **Package** | **2,478** | **2,463,206,070** | **595,102.179 s (165.31 h)** |
| Diagnostic takes (excluded) | 14 | 638,745 | 154.008 s |

Container bitrate of the package is 33,117 bps (bytes × 8 / duration).

Loudness (EBU R128, true peak on, all 2,492 files):

| | Integrated LUFS | True peak (dBTP) |
| --- | ---: | ---: |
| Minimum | −17.4 | −3.4 |
| Median | −16.4 | −0.2 |
| Mean | −16.43 | −0.07 |
| Maximum | −15.7 | +5.3 |

### Gaps

- **Missing chapters:** none. Both voices have all 66 Protestant books and chapters 1..N for each book (1,189 each). Stories 1–50 are present for both voices.
- **Manifest mismatches:** each chapter and story file has one manifest row, and each manifest row has a file. Probed duration and the manifest duration differ by under 0.75 s on every row (the differences are rounding, a few thousandths of a second).
- **Duplicates:** no shared sha256 among the 2,492 files. Girl and boy takes are distinct files.
- **Undecodable or zero-length:** none.
- **True peak above −1.0 dBTP:** 2,348 of the 2,478 package files (94.8%). 920 of those are above 0 dBTP (girl chapters 552, boy chapters 358, girl stories 7, boy stories 3). Six files are at or above +3.0 dBTP:

  | Voice | Book | Chapter | True peak |
  | --- | --- | ---: | ---: |
  | girl | 2 Kings | 25 | +5.3 dBTP |
  | girl | Job | 1 | +4.2 dBTP |
  | girl | Micah | 1 | +3.5 dBTP |
  | boy | 2 Kings | 14 | +3.2 dBTP |
  | girl | Genesis | 24 | +3.1 dBTP |
  | girl | 2 Chronicles | 18 | +3.0 dBTP |

Integrated loudness is already in a narrow band around −16.4 LUFS. The hot peaks are intersample peaks in the existing AAC, not missing or corrupt files. The package keeps those masters. A limiter would mean a second lossy AAC generation. Re-encoding the whole library at the same ~32 kbps drops time-domain SNR to about 14 dB and does not shrink the package (see the 32 kbps row below).

## Encode options

iOS AVPlayer plays AAC-LC and HE-AAC in `.m4a` natively. Both were measured. HE-AAC v2 (parametric stereo) is a stereo tool and was not used for this mono narration.

Ubuntu’s ffmpeg AAC encoder produces AAC-LC only. HE-AAC was encoded with a local build of libfdk-aac 4.0.1 (`fdkaac -p 5`, CBR, mono WAV in). That binary is not part of this repo. The HE-AAC files probe as stereo; the two decoded channels are identical (dual-mono signaling) and the bitrate is the mono target.

Size for each re-encode is extrapolated from a fixed 20-file sample (5,170.052 s, both voices, short stories through Psalm 119): sample bytes per second × 595,102.17 s of library audio. The same method predicts the source library at 2,461,692,833 bytes against the exact 2,463,206,070 (−0.06%), so the other rows are good to well under 1%.

Quality on that same sample:

- **Log-spectral distance (LSD).** Decode to 16 kHz mono, 32 ms Hann, 16 ms hop, speech frames within 45 dB of the peak frame. Mean over frames of the RMS bin error in dB. HE-AAC is shifted by the measured encoder delay (125.5 ms) before the compare.
- **SNR.** 10 log10 of signal power over (source − encode) on the first 45 s, no extra gain, for AAC-LC. HE-AAC SNR is on the delay-aligned full sample. HE-AAC’s spectral-band replication does not preserve the waveform, so its SNR stays near 5 dB at every bitrate; the speech-to-text column is the intelligibility check for those rows.
- **Speech-to-text.** faster-whisper `base`, int8, English, VAD on, first 45 seconds. Reference is the transcript of the **source** file, so the score is “did the same words still come through,” not a comparison to a written script. Six clips: girl and boy Genesis 1, girl and boy story 1, girl Acts 16, boy Revelation 5.

| Option | Library bytes | Library MiB | In audio budget (3,560,964,096) | LSD dB | SNR dB | WER mean (max) |
| --- | ---: | ---: | --- | ---: | ---: | ---: |
| **Source AAC-LC (recommended)** | **2,463,206,070 exact** | **2,349.1** | yes | — | — | reference |
| Stream copy | 2,463,206,070 exact | 2,349.1 | yes | — | — | same audio |
| AAC-LC 64 kbps | 4,983,398,834 | 4,752.5 | no (audio alone is over 4 GiB) | 2.63 | 30.0 | 0.015 (0.050) |
| AAC-LC 48 kbps | 3,687,330,886 | 3,516.5 | no | 3.65 | 24.6 | — |
| AAC-LC 40 kbps | 3,066,504,034 | 2,924.4 | yes | 4.18 | 22.5 | — |
| AAC-LC 32 kbps re-encode | 2,465,893,131 | 2,351.7 | yes | 4.97 | 14.2 | 0.026 (0.086) |
| AAC-LC 24 kbps | 1,860,832,726 | 1,774.6 | yes | 9.92 | 11.4 | 0.058 (0.252) |
| AAC-LC 16 kbps | 1,260,957,864 | 1,202.5 | yes | 36.06 | 9.0 | 0.109 (0.289) |
| HE-AAC 32 kbps | 2,416,013,792 | 2,304.0 | yes | 8.07 | 4.7 | 0.049 (0.182) |
| HE-AAC 24 kbps | 1,820,911,545 | 1,736.6 | yes | 9.02 | 4.6 | 0.057 (0.182) |
| HE-AAC 16 kbps | 1,225,807,687 | 1,169.0 | yes | 10.04 | 4.6 | 0.047 (0.147) |

AAC-LC commands (mono, 24 kHz, `.m4a`, faststart):

```
ffmpeg -y -i INPUT -c:a aac -profile:a aac_low -b:a 32k -ac 1 -ar 24000 -movflags +faststart OUTPUT
```

HE-AAC:

```
ffmpeg -y -i INPUT -ac 1 -ar 24000 -f wav - | fdkaac -p 5 -b 32000 -m 0 -o OUTPUT -
```

What the table says:

- 64 kbps is a larger file than the 4 GiB cap allows, for audio that is already a 32 kbps master.
- 48 kbps is still larger than the source and misses the audio budget.
- 40 kbps fits and is still larger than the source, with a second-generation SNR around 22 dB.
- 32 kbps re-encode lands within about 2.7 MB of the source size and costs about 14 dB SNR. Words stay intact (mean WER 2.6%). There is no size reason to pay that.
- 24 kbps and 16 kbps shrink the library. Mean WER stays under 11%, and the worst 16 kbps clip reaches 29% word error. 16 kbps AAC-LC from the native encoder also blows the spectrum apart (LSD about 36 dB).
- HE-AAC 32 kbps saves about 45 MiB (1.9%) against the source and is further from the original spectrum than a 32 kbps AAC-LC re-encode. Lower HE-AAC rates save more space and keep mean WER near 5%, with a worst clip around 15–18%.

Both voices already fit with 1.41 GiB of room under the 4 GiB cap after the 300 MiB non-audio allowance, and with 1.05 GiB of room inside the 400 MiB margin. The package is the source files.

## Build

`kids-bible-package/build_kids_bible_audio_package.py` reads this repo and writes:

```
<out>/KidsChapterAudio/<voice>/<Book>/<chapter>.m4a
<out>/KidsChapterAudio/<voice>/manifest.json
<out>/KidsStoryAudio/<voice>/<story>.m4a
<out>/KidsStoryAudio/<voice>/manifest.json
<out>/package-summary.json
```

Books are in Protestant order. Stories use `book: "Stories"` and `chapter` as the story number so every row has the same fields: `kind`, `book`, `chapter`, `voice`, `file`, `duration_sec`, `size_bytes`, `sha256_source`, `sha256_encoded`, `source_path`.

```
python3 kids-bible-package/build_kids_bible_audio_package.py \
  --dry-run --output /tmp/kids-bible-pkg

python3 kids-bible-package/build_kids_bible_audio_package.py \
  --output /path/to/package
```

The script refuses to write inside `kids-bible-audio/` or `long-road-kids-audio/`. A full build that would exceed the audio budget exits non-zero. `--only voice:book:chapter` builds a subset (stories are `girl:Stories:1`).

Dry run of the full library (this commit’s `dry-run/` folder): 2,478 files, 0 missing, `audio_bytes` 2,463,206,070, `within_audio_budget` true. `sha256_encoded` is null and `size_bytes` is the source size.

Real build checked on four files (`girl` 3 John 1, `boy` Philemon 1, `girl` story 1, `boy` story 1), output under `sample-build/` as JSON only. Each output decoded, duration matched within 0.05 s, `sha256_encoded` matched the file on disk, and `sha256_source` matched the repo blob. Those four copies were the same length as the source. The audio files from that run are not in git.
