# Volume Mixer 1.0.1

This maintenance release adds licensing and documentation to the portable
Windows mixer. Audio features are unchanged from 1.0.0.

## Download and run

1. Download `VolumeMixer-1.0.1-windows-x64.zip` below.
2. Extract the ZIP to a folder you can write to.
3. Open `VolumeMixer` and run `VolumeMixer.exe`. Keep the entire folder together.

Python and additional audio drivers are not required. The executable is unsigned;
Windows may display a publisher warning. A SHA-256 checksum accompanies the ZIP.

## Changes

- MIT licence for Volume Mixer and original notices for bundled dependencies.
- Licence collection and audited runtime checks in the release build.
- Screenshots, troubleshooting, and clearer download instructions in the README.
- Contribution guidance and a feature-request form on GitHub.
- Documentation, screenshots, and licences included with the Windows download.

## Requirements and limitations

- Windows 10/11, x64. Sharing requires Windows build 20348 or later.
- One app can be shared at a time; Output A cannot be delayed during sharing.
- Some apps need playback restarted after changing their device preference.
- Protected, exclusive, or offloaded audio may not be capturable.
- Bluetooth synchronization is manual and can need readjustment.
- Routing uses an internal Windows interface and may be affected by updates.
