# Changelog

## 1.0.2

- Add individual device-volume sliders beneath Output A, B, and extra outputs.
- Adjust selected Windows devices immediately, independently of each other.
- Show unavailable controls for missing devices and clarify that device volume
  affects all audio on that device.

## 1.0.1

- Add the MIT licence and bundled third-party copyright and licence notices.
- Collect dependency notices during builds and check the audited native runtime.
- Add real-interface screenshots with example data, quick download instructions,
  troubleshooting, contribution guidance, and a feature-request form.
- Include documentation and licence files in the portable Windows ZIP.

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
