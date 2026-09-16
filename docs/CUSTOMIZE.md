# Customize a theme

The current themes draw their pixel lettering with native shapes. **“CODEX WEEKLY” is artwork, not a normal text field or a Title setting in Globals.** Changing the title while keeping that lettering currently requires the Python tool below.

| Change | Current method |
|---|---|
| Feed URL | In KWGT, change **Globals → Source**, then **Save**. |
| Colors, shapes and placement | Edit the relevant items in KWGT; keep a copy first. |
| Main pixel title | Rebuild with `--label` below. |
| “PC DATA” footer label | Rebuild with `--source-label` below. |
| What the percentage measures | Supply another feed using the [existing JSON fields](CUSTOM_CONNECTORS.md). |
| Field names, units, low/full rules or reset wording | Advanced source/formula changes; these are not exposed as simple Globals controls. |

## Change the pixel title

Download the repository and use Python 3.10+:

```sh
python tools/build.py --label "API RESERVE" --source-label "SOURCE" --output local/presets
```

Import a file from `local/presets` and set its **Globals → Source** URL. The tool makes all six themes with the new title and replaces supported secondary period labels with neutral wording.

Titles support up to 20 characters from the preset's pixel alphabet. Source labels support 1–7 letters, digits or spaces. Labels are converted to uppercase. Check the result on your phone; preview thumbnails are not regenerated.

## Change the data

Each widget displays one **remaining percentage**: higher is better, below 10 is low, and a fresh 100 is full. The feed's `weekly` field can hold another reserve metric, such as battery charge, API allowance or free storage. Its name does not require a weekly schedule.

Keep that JSON format, or use the [connector adapter](CONNECTOR_REFERENCE.md), to avoid editing the widget's formulas. A temperature, CPU load or arbitrary service state needs changes to units and display rules as well as labels.

## Edit the source

Definitions are in `src/<theme>/preset.json`. Rebuild and test with:

```sh
python tools/build.py
python -m unittest discover -s tests -v
```

The normal build retains the existing artwork and logic. Python checks do not establish Android rendering or behavior.

[Connector reference](CONNECTOR_REFERENCE.md) · [Contributing](../CONTRIBUTING.md)
