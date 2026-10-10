# Contributing

Bug reports and focused pull requests are welcome. For feature ideas, describe
the audio setup and the problem the feature would solve.

## Setup

Use Windows 10/11 and Python 3.14.0 x64 for the audited release environment.

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Keep changes small and explain the resulting behaviour and how you checked it.
Add tests for meaningful audio, routing, or state-management changes. UI text
and documentation changes usually need a manual check rather than new tests.

## Audio changes

Run `.\.venv\Scripts\python.exe smoke_test.py` on Windows. It temporarily changes
and restores only its own process's audio preferences. The capture/playback
check requires two connected physical outputs. Check startup, stopping, device
disconnects, and route restoration when changing playback behaviour.

For delay or calibration changes, also listen to a wired/Bluetooth output pair.
Verify at a slow tempo to avoid mistaking a whole-beat offset for alignment.
Record any hardware checks you could not perform in the pull request.

## Releases and licensing

Update `version.py`, `CHANGELOG.md`, and `RELEASE_NOTES.md` together. Run
`build.ps1` to test, collect licences, and package the ZIP and checksum.
Review dependency notices and native versions when changing the build environment;
see `THIRD_PARTY_NOTICES.md`. Do not silently remove upstream copyright notices.

Contributions to this project are provided under its MIT licence. Preserve the
terms and attribution of any third-party code you introduce and identify its
source in the pull request.
