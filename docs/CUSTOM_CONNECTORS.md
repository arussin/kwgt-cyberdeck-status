# Use another data source

**Keep the widgets. Replace what produces `usage.json`.** No Codex tray software is needed for a different source.

```text
Your API or script → small JSON status file → HTTPS URL → KWGT
```

Have your collector return this shape (these are dated sample values):

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

Use a **number from 0–100** for `remaining`. Set `available` to false when unavailable; `refreshedAt` is when the reading was measured, in ISO format with a timezone. `resetsAt` can be null. `weekly` is just the existing field name: it need not be a weekly metric.

These are **reserve meters**: higher is better, below 10 is low, and 100 is full. API allowance, free storage, or battery reserve fit; CPU load, logs, and arbitrary service states need different semantics.

Already have JSON in another shape? Adapt it using the included example:

```sh
python tools/connector.py --input examples/api-response.json --mapping examples/api-mapping.json --output local/usage.json
```

Change the mapping to select your fields. The helper converts an existing file; your collector handles authentication and scheduled updates. [Modes and examples](CONNECTOR_REFERENCE.md).

Serve that file over an appropriate HTTPS connection. For a private PC feed, use [setup step 2](CODEX_SETUP.md#2-connect-privately). Set the new URL in **KWGT → Globals → Source** and save.

Keep tokens and account details in the collector, not the feed or preset. [Change the title or colors](CUSTOMIZE.md).
