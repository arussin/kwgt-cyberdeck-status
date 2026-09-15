# Connect another data source

The theme only needs a percentage, availability flag, source timestamp, and optional reset time. Authentication, API polling, retries, and rate-limit compliance belong in your data collector, not in exported KWGT presets.

```text
Your API / home-lab collector / script
                ↓ normalize and redact
             usage.json
                ↓ private or appropriate HTTPS endpoint
              KWGT
```

## The stable contract

```json
{
  "weekly": {
    "available": true,
    "remaining": 64,
    "resetsAt": null
  },
  "refreshedAt": "2026-01-01T12:00:00Z"
}
```

`weekly` is retained for compatibility with the working Codex presets. It can carry a non-weekly reserve metric. There is one metric per widget instance.

- `available`: real JSON boolean. False means unavailable; never encode “offline” as a healthy 100.
- `remaining`: finite numeric percentage, 0–100. Higher means more reserve; low warnings are below 10 and FULL requires exactly 100 with fresh data.
- `resetsAt`: ISO timestamp with explicit timezone, or null when there is no reset cycle. Existing designs may retain a reset label with a placeholder; advanced authors can change that label in the native source.
- `refreshedAt`: when the source was measured, not when the file was copied or the phone fetched it. Unknown can be null, and is displayed as unknown rather than fabricated freshness.

Use case | Appropriate mapping
---|---
API quota reporting percentage used | `100 - usedPercent`
Storage reporting free and total bytes | `100 * freeBytes / totalBytes`
Battery level reported as 0–1 | `100 * fraction`
Binary service health / CPU load / work complete | Requires careful semantic mapping or different warning labels; not a turnkey supported dashboard

## Normalize an existing JSON file

`tools/connector.py` uses only Python's standard library and allows dotted keys and list indices. It is a schema adapter, **not** a live integration with a particular vendor. Your authenticated collector is responsible for writing/updating the input.

```sh
python tools/connector.py --input examples/api-response.json --mapping examples/api-mapping.json --output local/usage.json
```

The example input is synthetic and dated; it should become stale, not look live. Mapping:

```json
{
  "value": "quota.usedPercent",
  "mode": "used",
  "available": "ok",
  "updated": "measuredAt",
  "reset": "quota.nextReset"
}
```

Available modes are `remaining` (already 0–100), `used` (invert 0–100), `fraction` (0–1 times 100), and `ratio` (value / total times 100). See `examples/storage-mapping.json` for a ratio.

Only the four whitelisted output fields are written. Extra input fields, headers, credentials, and account identifiers are not copied. Numeric strings, booleans masquerading as numbers, invalid dates, zero capacity, and out-of-range readings are rejected. Failed normalization leaves the previous output untouched with its old timestamp. Schedule or call the adapter after a successful collector update; the adapter itself is one-shot.

For a private Windows feed, serve its dedicated output directory directly with [Tailscale Serve](CODEX_SETUP.md#2-connect-privately). `tools/serve.py` is an optional loopback server for generic connectors or demos, not a Codex setup requirement. Any appropriately secured HTTPS host serving the contract can be used; Tailscale is transport, not part of the schema.

## Relabel a theme without drawing layers manually

```sh
python tools/build.py --label "API RESERVE" --source-label "SOURCE" --output local/presets
```

This recomposes the main header from the same native pixel paths. It does not add bitmap dependencies or font files, and does not change the data formulas. Keep headers short (up to 20 supported characters). The original overview thumbnails do not change; custom title layouts need an on-device check.

Some themes also contain decorative labels such as WEEKLY or 7D. In custom-label builds, supported secondary time-period labels are neutralized. For deeper changes to unit wording, reset labels, thresholds, or non-percentage metrics, edit `src/<theme>/preset.json` and rebuild. This is not a drag-and-drop integration with every API.

## Try a synthetic demo

```sh
python tools/build.py --label "DEMO" --source-label "DEMO" --output local/demo-presets
python tools/demo.py --remaining 64 --output local/usage.json
python tools/serve.py --file local/usage.json
```

Expose that loopback server using your private transport, then set the demo preset's Source to its own endpoint. The demo sets a timestamp for this **synthetic measurement**, prints a warning, and does not start an account reader. It is a one-time snapshot and will become stale. Use only the DEMO-labeled preset; do not confuse it with live service data.

## Safety and refresh

Do not put long-lived API tokens in Source. Presets are portable and exported globals can contain secrets. Keep authenticated collection on the source side; share the smallest possible status payload. Use HTTPS and restrict readers. Rate-limit polling responsibly; the widget's cache-busting request does not need to trigger another vendor API call every time.

[Refresh notes](REFRESH.md) explain the remaining Android/KWGT scheduling limits. [Security checklist](../SECURITY.md).
