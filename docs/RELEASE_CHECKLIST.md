# Release verification

Status on 2026-09-16: widget source and individual `.kwgt` files are public.
The downloadable bundle remains a **draft prerelease**.

## Verified

- The six-theme bundle comes from
  `44c802fc15b43000fed166e99160cd20fd7a6fd9`.
- [Widget CI](https://github.com/arussin/kwgt-cyberdeck-status/actions/runs/35032781178)
  passed all 28 tests at that commit.
- Downloaded draft assets matched their SHA-256 checksums and passed ZIP integrity
  checks. Presets contain an inert Source URL and no captured personal readings.
- The public Phosphor Classic preset was imported on Android. After replacing
  the example Source with the working URL and saving, the user confirmed it
  displayed usage and completed the phone test task.
- The user reported slow tap refresh with battery saver active and confirmed
  normal tap refresh after disabling it. No preset changes were needed.
- The separate Windows repository is a verified direct GitHub fork, with a
  self-contained draft build and passing automated checks. Its isolated export
  controls, persistence and failure behavior have also been exercised.
  [Windows evidence and limits](https://github.com/arussin/codex-usage/blob/main/docs/RELEASE_CHECKS.md).
- The earlier Windows folder draft passed launch, usage, layout at 150%
  scaling, opt-in export, custom destination, manual/automatic refresh,
  preference persistence and startup after real sign-in on a separate PC.
  [Folder-build acceptance](https://github.com/arussin/codex-usage/blob/main/docs/WINDOWS_ACCEPTANCE.md).
- The single-EXE draft passed separate-PC launch, layout, retained export
  settings, manual refresh, disabled-export preservation and return to the
  preserved folder build. Startup remains unresolved: an automatic launch used
  a temporary ZIP copy while its Run entry targeted the permanent folder.
  [Single-EXE acceptance and remaining check](https://github.com/arussin/codex-usage/blob/main/docs/SINGLE_EXE_ACCEPTANCE.md).

The phone check used the existing deployed exporter. It does not establish an
end-to-end installation of the draft Windows binary or all Android edge cases.
No widget redesign or preset changes were needed for this check.

## Remaining acceptance checks

- [x] Verify switching from the preserved Windows folder build to the single
  EXE and back, with readings and the saved export destination retained.
- [ ] Resolve the single-EXE startup-path and UI cleanup anomaly on the separate
  test PC before accepting that Windows package.
- [ ] Read that candidate export from Android by its ordinary private hostname,
  including the automatic/query/tap path across real file replacements.
- [ ] Confirm stale, no-data, unavailable, low, exhausted and FULL states using a
  separate synthetic feed; preserve the working feed.
- [ ] Record acceptance and approve the download releases before publication.
  Then update the setup guide with the verified Windows release URL.

## Setup and freshness

Every public preset starts with `https://example.invalid/usage.json`.
Set **Globals → Source** to the working JSON URL, **Save**, return home, and tap
the card body. The example URL cannot return readings.

`refreshedAt` is the collector's successful-reading timestamp. It is not the phone
download time. Failed readings and disabled export leave the old file to age.
[Setup](CODEX_SETUP.md) · [Refresh help](REFRESH.md).

Windows source, patches and binaries belong in the separate tray fork, not in
this widget repository or its downloads. An upstream PR and community posts are
separate decisions.
