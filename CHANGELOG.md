# Changelog

## Per-model limit on Ember Dual - 2026-11-22

- Ember Dual can show a weekly limit that applies to one model, which can run out well before the all-models one. A thin needle marks its level on the lower meter, and the footer names it with its percentage, for example `MARK=FABLE 19%`. No new row.
- It reads an optional `weeklyScoped` object in the feed. Without that object nothing appears and nothing else changes.
- The formulas are the theme's percentage formulas plus one step for the needle's position and two for the footer wording.
- The published Ember Dual downloads are rebuilt. Two new offline tests (65 total passing). They do not run KWGT.
- Confirmed working on the user's phone the same day. [What that covers](docs/DUAL.md#what-is-verified).

## Ember Dual reworked - 2026-11-21

- Ember Dual keeps its two rows and gains a title plate, tag plates, leaning meter segments and, under each meter, a line for the time left in that window. The line turns red when less reserve is left than time, meaning the reserve is being used faster than the clock.
- The time line is one new formula built on the theme's reset-time formula. The meter segments are the theme's cells drawn as native paths. Everything else is still reused unchanged.
- Shared drawing helpers moved into `tools/dual.py`; `tools/cassette.py` uses them.
- Three new offline tests (63 total passing). They do not run KWGT.
- Ready-made downloads with CLAUDE and CODEX headers are in `dual/`, checked against the builder by a test.
- Confirmed working on the user's phone the same day, with the CLAUDE label and Ember palette. [What that covers](docs/DUAL.md#what-is-verified). The `--field` builds and Data Cassette are still not confirmed on a phone.

## Data Cassette - 2026-11-21

- New experimental **Data Cassette**: a cassette in a deck with one reel per reserve. Tape winds off a reel in twenty steps as its reserve is used; the paper label lists both reset times. Composed by `tools/cassette.py` from Phosphor Classic's formulas. A reel is the theme's twenty meter cells drawn as stacked discs.
- One new formula turns the reel hubs each minute. Everything else is reused.
- `tools/preview.py` now draws either generated design (`--design dual` or `--design cassette`) and replaces `tools/dual_preview.py`.
- Eleven new offline tests (60 total passing). They do not run KWGT. **Not confirmed on a phone yet.**

## Second feed object and Ember Dual - 2026-11-21

- `tools/build.py --field <name>` rebuilds the six themes to read another object of the feed, such as `fiveHour`, in place of `weekly`. Only the feed paths and the preset identity change.
- New experimental **Ember Dual**: one card with the five-hour and weekly reserves stacked, composed by `tools/dual.py` from Phosphor Classic's formulas with a new layout and a warm palette. `tools/preview.py` draws it offline with sample data.
- The six published presets, their sources and checksums are unchanged.
- Thirteen new offline tests (49 total passing). They compare the generated formulas with the theme they come from and check structure, layout bounds and archive reproducibility. They do not run KWGT. **Neither addition has been confirmed on a phone yet.**

## CD4.2 low-reserve color fix - 2026-09-17

- Keep valid below-10% warning colors independent of source freshness across all six themes.
- Preserve stale/cached/error status labels, source age, reset text, and fresh-only FULL behavior.
- Cover percentage glyphs, filled bar cells, borders, and theme-specific warning accents.
- Rebuild all six native presets and checksums; preset titles identify CD4.2.
- Add eight offline regression tests (36 total passing). Tests evaluate the final color-expression subset and archive consistency, not Android/KWGT rendering. Phosphor Classic was confirmed working on the phone by the user; other themes still require on-device acceptance.

## Documentation handoff v3 — 2026-09-15

- Filled in the recovered export path and the candidate's explicit Enable export step.
- Kept the default setup to direct Tailscale directory sharing; no extra server.
- Recorded real-fork, candidate-build, upstream-PR scope, and final installation checks.
- Kept the six presets, editable sources, tools, and previews unchanged.
- No Windows source, patch, build helper, notice copy, or binary added here.

## Initial public-package candidate — 2026-09-15

- Six native R4.1 cyberdeck presets with a direct web feed and captured refresh fallback.
- Default distribution removes private source configuration and captured data.
- Editable preset JSON, reproducible archive builder, synthetic previews and checksums.
- Original standard-library schema adapter, demo snapshot generator, and loopback single-file server.
- Clear attribution to Tooblippe/codex-usage; upstream tray source/exporter is not bundled.
- Optional pixel-header personalization; device verification still required for personalized builds.

This changelog covers the public package. It is not a claim that earlier failed development prototypes were published releases.
