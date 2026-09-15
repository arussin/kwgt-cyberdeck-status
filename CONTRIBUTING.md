# Contributing

Keep improvements small and preserve the working native-shape rendering path. Changes to Kustom formulas should include an actual phone test whenever possible; the Python tests do not execute KWGT.

## Local checks

```sh
python tools/build.py
python -m unittest discover -s tests -v
```

Edit `src/<theme>/preset.json` and rebuild the archives; do not edit generated binaries alone. Keep paths and labels editable. The default build resets Source and captured state for public distribution. Optional custom-label builds belong in the ignored `local/` folder.

## A useful report

Include the theme, KWGT version, Android version, launcher, widget dimensions, and whether the editor or home screen is affected. Replace real account readings and endpoints with a small synthetic payload before attaching an exported preset. Do not upload authentication files, private Tailscale names, full API responses, or phone screenshots with calendar/personal information.

For a collector/connector contribution, document its input, authentication location, normalized output, source timestamp behavior, rate limits, and failure handling. Add normalization tests. Keep credentials on the source machine; the widget should only read a small status payload.

## Attribution

Retain the existing project attribution and license notices. Identify upstream projects and licenses for any new copied code. Do not add Codex Usage Tray source, copied snippets, derivative patches, or binaries here. Submit all tray changes to the separate direct GitHub fork, preserving its original license and history. New original contributions use this project's MIT license.
