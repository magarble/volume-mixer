# Volume Mixer 1.0.2

Adjust Output A and Output B independently with device-volume sliders directly
on each application's card. Extra outputs get their own sliders too.

## Download and run

1. Download `VolumeMixer-1.0.2-windows-x64.zip` below.
2. Extract the ZIP to a folder you can write to.
3. Open `VolumeMixer` and run `VolumeMixer.exe`. Keep the entire folder together.

Python and additional audio drivers are not required. The executable is unsigned;
Windows may display a publisher warning. A SHA-256 checksum accompanies the ZIP.

## Changes

- Individual device-volume sliders under Output A, B, and extra output rows.
- Volume changes take effect immediately without applying outputs again.
- Windows default controls the current default output device.
- Missing devices display a message instead of an active slider.

Device volume affects all audio on the selected Windows device. The program's
volume slider remains separate. Refresh after changing the Windows default.

## Validation

All 51 automated tests passed. UI callback checks confirmed that adjusting A
does not change B, with Windows-default and missing-device controls checked too.

## Requirements and limitations

- Windows 10/11, x64. Sharing requires Windows build 20348 or later.
- One app can be shared at a time; Output A cannot be delayed during sharing.
- Some apps need playback restarted after changing their device preference.
- Protected, exclusive, or offloaded audio may not be capturable.
- Bluetooth synchronization is manual and can need readjustment.
- Routing uses an internal Windows interface and may be affected by updates.
