# Volume Mixer 1.0.0

A portable Windows desktop mixer with per-program volume, device routing,
driver-free multi-output playback, and manual output alignment.

## Download and run

1. Download `VolumeMixer-1.0.0-windows-x64.zip` from this release.
2. Extract the ZIP to a folder you can write to.
3. Open `VolumeMixer` and run `VolumeMixer.exe`. Keep the entire folder together.

Python and additional audio drivers are not required. The executable is unsigned;
Windows may display a publisher warning. A SHA-256 checksum accompanies the ZIP.

## Included

- Friendly app names, volume and mute, and input/output preferences.
- Multiple output rows for sharing one app to several devices.
- Saved per-output delay settings and six alignment sounds with tempo controls.
- Mouse-wheel scrolling without accidental dropdown or numeric changes.

## Requirements and limitations

- Windows 10/11, x64. Sharing requires Windows build 20348 or later.
- One app can be shared at a time; Output A cannot be delayed during sharing.
- Some apps need playback restarted after changing their device preference.
- Protected, exclusive, or offloaded audio may not be capturable.
- Bluetooth synchronization is manual and can need readjustment.
- Routing uses an internal Windows interface and may be affected by updates.

## Validation before publishing

Automated tests and packaging checks run in GitHub Actions. Run `smoke_test.py`
on Windows to verify routing, UI startup, and silent capture to a second physical
output. Listen to a wired/Bluetooth pair to verify alignment. Keep the release
as a draft until these hardware checks pass.
