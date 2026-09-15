# Refresh, stale data, and known limits

There are two independent clocks: the collector's measurement time and KWGT's download/evaluation time. A successful tap can download a file containing a reading measured several minutes earlier. We display the source age, not the time of the tap.

The original source project polls every five minutes. The preset changes its URL in five-minute windows and on a body tap to reduce reuse of one cache entry. This is **not a five-minute Android job**. KWGT evaluation, network settings, HTTP caching, battery optimization, idle state, and connectivity can delay reads. There is no guaranteed freshness interval.

The native R4.1 body action stores the available quota and its timestamps in one captured snapshot before choosing a new request URL. While a current response is empty it can use that snapshot or a recent preceding-window response. The fallback is identified, and the source age continues increasing. First load has no prior snapshot; no design can retain data it never received. Restart/export/cache behavior still depends on KWGT.

State | Meaning
---|---
READING / FETCHING / REFRESHING | Waiting for a response; not proof of a successful update
NO DATA | No usable response/snapshot; not a zero allowance
UNAVAILABLE | Source explicitly reports unavailable
INVALID DATA | Present data fails the preset's value validation
AGE UNKNOWN | Reading without a usable source timestamp
CLOCK SKEW | Source timestamp significantly ahead of the phone
STALE DATA | Valid snapshot older than 15 minutes
CACHED DATA | A prior snapshot is being shown; latest request not confirmed
LOW RESERVE | Valid remaining reserve below 10%
EXHAUSTED | A genuine 0%, distinct from unavailable
FULL | Exactly 100%, with valid recent non-fallback data

A stale or cached response does not tell us whether a PC is asleep, Tailscale is down, or an API failed. The widget does not claim to know the cause.

## Troubleshooting order

1. Verify Source is your URL, not the inert example URL. Do not put query strings or fragments into it; these presets add their own query parameters.
2. Open the URL from the phone browser using the same network/Tailscale connection. Check the source time and the field types.
3. In KWGT, tap Save, return home and tap the card body. The header reopens the editor.
4. Verify the collector actually advances `refreshedAt` after real measurements. Do not “fix” old data by rewriting only its timestamp.
5. Check KWGT's battery/network settings, but do not enable every-second rendering as a substitute for network updates.
6. For reports, include Android/KWGT version, launcher, theme, and a redacted sample payload. Never attach secrets or an unsanitized preset export.

Native shape/path rendering avoids the image-resource failures encountered during development. It is not a guarantee of identical behavior on every launcher, device, or future KWGT build.

Primary references:
- [Kustom WG](https://docs.kustom.rocks/docs/reference/functions/wg/)
- [Kustom native SVG paths](https://docs.kustom.rocks/docs/reference/svgpaths/)
- [Captured timestamp touch action](https://forum.kustom.rocks/t/creating-timestamps-on-button-press/7379)
- [Kustom developer on caching](https://forum.kustom.rocks/t/wg-wget-is-caching-the-request/779)
- [Kustom developer on refresh windows](https://forum.kustom.rocks/t/its-posible-to-lower-network-refresh-time-to-1-minute-or-so/1465)
- [Android Doze and standby](https://developer.android.com/training/monitoring-device-state/doze-standby)
