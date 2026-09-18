# Changelog

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
