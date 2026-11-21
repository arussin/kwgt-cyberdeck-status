# Ember Dual: two meters in one card

**Experimental.** One widget shows the five-hour reserve above the weekly reserve, each with its own percentage, status word, 20-cell meter and reset time.

![Ember Dual layout with sample data](../previews/Ember_Dual_Layout_Preview.png)

*Layout preview drawn offline from sample data by `tools/preview.py`. It is not a phone screenshot.*

## What it needs

A feed with both a `fiveHour` and a `weekly` object, plus `refreshedAt`:

```json
{
  "fiveHour": { "available": true, "remaining": 32, "resetsAt": "2026-01-01T18:20:00-05:00" },
  "weekly": { "available": true, "remaining": 94, "resetsAt": "2026-01-04T10:00:00-05:00" },
  "refreshedAt": "2026-01-01T15:20:00-05:00"
}
```

Each object follows the [existing contract](CONNECTOR_REFERENCE.md#the-stable-contract). The [Windows tray](https://github.com/arussin/codex-usage) writes this shape for Codex (`usage.json`) and, when its Claude numbers are switched on, for Claude (`claude.json`). A row whose object is missing or unavailable shows `--%` and UNAVAILABLE; the other row still works.

## Build and load it

Use Python 3.10+:

```sh
python tools/dual.py --label CLAUDE --output local/dual
```

Import `local/dual/Ember_Dual_CLAUDE.kwgt` into KWGT, set **Globals → Source** to your feed URL without query strings, and **Save**. Tap the body to refresh; tap the header to edit. The header takes up to 20 characters from the pixel alphabet. `--palette phosphor` keeps the mint Phosphor Classic colours instead of the warm Ember ones.

To review a layout change without a phone:

```sh
python tools/preview.py --design dual --label CLAUDE --output local/dual
```

That writes two SVG files with sample readings, one normal and one with a low and a full row.

## How it is made

`tools/dual.py` writes no Kustom logic of its own. It takes modules from the Phosphor Classic source, the theme checked on a phone, and changes only three things:

| Change | Detail |
|---|---|
| Position and size | Each module gets new coordinates in the same 1440 × 600 design space and scaling formula. |
| Colours | A fixed table maps each Phosphor colour to an Ember colour by role. Low reserve is yellow so it cannot be mistaken for the coral meter cells. |
| The upper row's data | Its formulas read `.fiveHour.` in place of `.weekly.`, and its own slots of the saved snapshot. The five-hour reset line uses a shorter `EEE h:mm A` format. |

Both rows share one request URL and one source timestamp, so the card makes the same single download as the other themes. The body tap still runs one action. That action is the theme's own formula followed by a copy of its per-metric steps for the five-hour object, and it saves eight fields instead of five: request marker, weekly reading, source time, five-hour reading.

[Freshness, states and troubleshooting](REFRESH.md) apply unchanged. Each row has its own status word. The status mark and case colour follow the weekly row.

## What is verified

The offline tests check that the weekly row's formulas are identical to Phosphor Classic's, that the five-hour row differs only in the three ways listed above, that the tap action is the theme's formula plus the copied steps with no undefined variable, that nothing overlaps or leaves the card, and that the archive is reproducible and carries no private endpoint.

They do not run Kustom. **On-device behaviour of this layout has not been confirmed yet.** The parts most worth checking on a phone are the eight-field snapshot after a tap, and how the card performs with about 150 live modules where the other themes have about 100.
