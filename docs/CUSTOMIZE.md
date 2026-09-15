# Change the look

**In KWGT:** tap the widget header to edit. Change shapes, colors, or layout, then save. Keep your own copy before editing.

**For a different pixel title:** download the repository and run this with Python 3.10+:

```sh
python tools/build.py --label "API RESERVE" --source-label "SOURCE" --output local/presets
```

Import a file from `local/presets` and set its **Globals → Source** URL. Titles are up to 20 characters; source labels are up to 8, using the supported pixel alphabet. Check custom labels on your phone; previews are not regenerated.

**For developers:** editable definitions are in `src/<theme>/preset.json`. Rebuild and test with:

```sh
python tools/build.py
python -m unittest discover -s tests -v
```

The normal build retains the existing artwork and logic. Python checks are not Android/KWGT execution.

[Connector reference](CONNECTOR_REFERENCE.md) · [Contributing](../CONTRIBUTING.md)
