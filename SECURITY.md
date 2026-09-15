# Security and responsible sharing

The packaged presets start with `https://example.invalid/usage.json` and `latch = 0~~~~`. These defaults are intentional. They contain no real account state.

Keep private configuration, input data, output payloads, and tokens in `local/`, outside Git. Never commit `.env`, `.codex`, `auth.json`, actual `usage.json`, browser storage, or a personalized KWGT export. JSON inside a `.kwgt` archive can expose globals even though the file looks binary.

The included loopback helper serves only `/usage.json`, supports GET only, accepts cache query parameters, caps payload size, and does not list directories. It is a convenience for a trusted local machine behind a private transport, not a hardened public or multi-tenant service. Other local processes and allowed tailnet readers may read the payload; configure your access policy accordingly.

Never expose a credential directory using Tailscale Serve. Do not enable public Funnel for private usage. Do not install an exit node or advertise LAN subnets merely to show this widget. Review existing Serve configuration before changing it.

For generic collectors, authenticate upstream on the source side and redact the export. Protect any published endpoint according to the sensitivity of the data. Private addressing is not a license to publish credentials or internal hostnames.

Before publishing, run the tests and scan the uncompressed preset JSON and image metadata. Only sample-generated widget previews are included here; personal home-screen screenshots are excluded. Do not include meeting details, wallpaper portraits, local paths, or account identifiers in promotional images.

Report issues with a redacted payload and version information. Do not open a public issue containing live tokens. This project has no staffed security response service or SLA.
