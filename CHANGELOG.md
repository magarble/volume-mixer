# Changelog

## 1.0.0

First packaged release of Volume Mixer for Windows.

- Per-program volume and mute with friendly application names.
- Input/output device preferences and endpoint volume controls.
- Share one application's audio to multiple outputs without an extra driver.
- Independent delays for copied outputs, saved per device.
- Six alignment sounds, adjustable tempo, and individual output auditioning.
- Inline output rows that preserve drafts during refresh.
- Page scrolling that leaves dropdown selections and numeric values unchanged.
- Portable Windows ZIP with version information and SHA-256 checksum.

### Compatibility

Normal controls support Windows 10/11. Application audio sharing requires
Windows build 20348 or later, including Windows 11. One application can be
shared at a time. Output A plays directly and cannot be delayed during sharing.
Bluetooth timing requires manual listening checks and may drift over time.
Internal Windows routing APIs may change after Windows updates.
