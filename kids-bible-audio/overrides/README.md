# Kids Bible audio overrides

Trimmed, QA-passed replacements for specific lab-audio files. They live beside the
original trees and must not overwrite `kids-bible-audio/<voice>/` or
`long-road-kids-audio/<voice>/`.

Layout:

    kids-bible-audio/overrides/stories/<source_dir>/<n>.m4a

`source_dir` is `sample1` (girl) or `boy`. See `manifest.json` for sha256, size,
duration, and the lab-audio `04409065` path and git blob each file replaces.

## Bundler rule

If a package script copies story or chapter audio, it must prefer an override
when the override file exists and is non-empty. The current bundler is
`kids-bible-package/build_kids_bible_audio_package.py` on branch
`cursor/kids-bible-audio-package-58b1` (not yet on `lab-audio`). Until that
script is updated, the bundler must apply this rule by hand.

Suggested change when choosing a story source, using the existing
`VOICES` `source_dir` mapping:

```python
stories_dir = story_root / "stories"
overrides_stories = repo / "kids-bible-audio" / "overrides" / "stories" / voice["source_dir"]
src = stories_dir / f"{story}.m4a"
override = overrides_stories / f"{story}.m4a"
if override.is_file() and override.stat().st_size > 0:
    src = override
```

Chapter overrides, if added later, should win the same way over
`kids-bible-audio/<source_dir>/<Book>/<n>.m4a`. The package script looks for
those at `kids-bible-audio/overrides/chapters/<source_dir>/<Book>/<n>.m4a`.

`kids-bible-package/build_kids_bible_audio_package.py` calls `story_source()`
for every story. It checks the override file's sha256 against this manifest
and refuses to build when the lab-audio file named in `replaces.sha256` has
changed. Output rows from an override set `"source": "override"`.
