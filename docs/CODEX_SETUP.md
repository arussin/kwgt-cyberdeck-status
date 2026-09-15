# Codex on your phone

**Windows tray → private Tailscale URL → KWGT Pro.** No extra server or task app.

> **Exporter release candidate:** use [my direct fork](https://github.com/arussin/codex-usage), not the unmodified upstream app. The first binary is held as a draft until final Windows/phone checks pass. [Release status](RELEASE_CHECKLIST.md).

## 1. Enable JSON export

When available, download the **complete self-contained Windows x64 ZIP** from [the fork’s releases](https://github.com/arussin/codex-usage/releases). Extract everything to a stable folder and run `CodexUsageTray.exe`. You need a working, signed-in Codex CLI; no SDK or compilation is required. Already running a tray? Use the fork release's backup/update instructions first.

Right-click the tray → **JSON export → Enable export**. After a successful reading it writes:

```text
%LOCALAPPDATA%\CodexUsagePhone\usage.json
```

Keep this default for the setup below. **Choose output file…** is optional; selecting a path does not enable export. Confirm the file exists before continuing.

## 2. Connect privately

Connect Tailscale on the PC and phone to the same tailnet. On the PC, open PowerShell:

```powershell
tailscale serve status
```

**Already have a working status URL? Reuse it and skip the next command.** Otherwise, after confirming `/codex-status` is unused:

```powershell
tailscale serve --bg --set-path=/codex-status "$env:LOCALAPPDATA\CodexUsagePhone"
```

Complete any HTTPS approval prompt. Use the host printed by Serve and append `/codex-status/usage.json`:

```text
https://<pc-name>.<tailnet>.ts.net/codex-status/usage.json
```

Open it on the phone; you should see JSON. Keep this directory for status files only. Do not reset other Serve mappings or serve your installation/credentials. No Funnel, exit node, or subnet router is needed. [Tailscale reference](https://tailscale.com/docs/reference/tailscale-cli/serve).

## 3. Load the widget

[Download a theme](THEMES.md), import it in KWGT, and set **Globals → Source** to that URL without query strings or fragments. **Save**, return home, and tap the body.

The PC normally polls every five minutes; tapping only downloads its latest file. Keep the PC, tray, and Tailscale running. Failed readings or disabled export leave the old file to age. [Freshness and troubleshooting](REFRESH.md).
