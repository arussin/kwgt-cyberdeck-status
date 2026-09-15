# Release status and final checks

**Not a published release.** The Windows source is now recovered; the public download and final user acceptance tests are still pending. No widget redesign is needed.

## Evidence in hand

The separate local-Codex handoff reports passing isolated Windows Release builds/publishes, self-tests, formatting, and private HTTPS reads with cache-busting query strings. It supplies the historical exporter and a new default-off, configurable-path candidate. No normal replacement tray was installed or launched.

A separate review verified 49 packaged checksums and both patches against the five modified upstream file hashes at `7801b0445f133bef3d8db0bdae1b9c5670389f4b`; reverse/forward reconstruction matched the supplied source. The license matched upstream. This establishes the source delta, not a reproducible-binary attestation or an Android test.

## Finish before an end-to-end Codex release

- [ ] Verify the real GitHub fork and its upstream parent; identify the exact release-candidate commit.
- [ ] Rebuild/test from that fork commit; package the entire self-contained x64 build, LICENSE, and checksums.
- [ ] On Windows, test normal launch, default-off state, **Enable export**, file picker, manual/five-minute refresh, disable, and restart. Check that old files age rather than becoming fresh placeholders.
- [ ] Test a clean supported installation, signed-in CLI discovery, and Windows startup behavior. Do not claim compatibility from the existing customized PC alone.
- [ ] On Android, open the status URL by its ordinary hostname and read through real file replacements; test the five-minute/query/tap path and a public-package widget import. The handoff's Windows transport test used a temporary per-request address override, not a new DNS configuration.
- [ ] Confirm stale/no-data/low/FULL behavior; test failures without breaking the owner's live setup.
- [ ] Publish only after owner approval; insert the verified exporter release link and remove the draft warning from the setup guide. Community posting is separate.

## Keep scope and freshness honest

The new menu candidate is not the owner's deployed always-on build. Export remains optional, uses the existing tray poll, and has no HTTP server or second timer. Its default file is `%LOCALAPPDATA%\CodexUsagePhone\usage.json`; preferences are elsewhere.

`refreshedAt` is the PC time of parsing a successful quota response—not the phone download time. Fetch or write failures preserve old data; disabling export does not remove a previously shared file or disable Tailscale.

Do not call the complete Windows candidate an exporter-only upstream PR: it also contains prior CLI-discovery and display-scaling changes. Separate those changes, then re-test. The two handoff patches are alternatives, not a sequence.
