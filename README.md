# Volume Mixer

A Windows desktop mixer with friendly application names, per-program volume and mute, input/output preferences, simultaneous playback on multiple devices, microphone/speaker volume. Volume controls range from 0 to 100%.

## Run

Double-click `dist-no-boost/VolumeMixer/VolumeMixer.exe` after building. Keep the entire `VolumeMixer` folder together; the executable does not need a separate Python installation.

For development, install Python 3.11 or newer on Windows 10/11, then run:

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

Build the desktop executable:

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

## Normal mixing

Start playback in a program and click **Refresh devices & apps**. The Programs tab groups that process's sessions across all active output devices. Adjust its volume, mute it, or choose its output and input devices. **Windows default** clears that program's preference. Some programs explicitly choose their own device or require restarting playback before preferences take effect. System sounds can be adjusted but cannot be routed per process.

Cards show the friendly application name above the executable name and PID. Names come from Windows product metadata, common application/helper names, or the audio-session name, with a readable filename fallback. Separate processes remain separate cards, even if their friendly names match.

The Input & output tab adjusts each physical or virtual endpoint's volume and mute. Microphone volume applies to the microphone device, affecting programs using it. Windows does not expose a universal independent capture-volume slider for every other program.

Refresh reads current Windows levels. Sliders do not automatically track changes made outside the app. New/closed programs and hotplugged devices appear on refresh. Applications using exclusive audio mode may bypass shared-session controls.

## Play one app on multiple outputs

1. On the application's card, choose your first device in **Output A**. The input selector stays beside it.
2. Click **Add Extra Output** to create **Output B** directly underneath. Pick your second device, such as a Bluetooth speaker. Add further rows for **Output C**, **D**, and so on.
3. The inline **Virtual audio device** selector preselects an unused dedicated playback device when available. Install a virtual cable if needed; keep the source separate from your chosen outputs and your Windows default output.
4. Click **Apply Outputs**. The app first opens all selected outputs, then routes the program to the virtual device. Some programs need playback restarted to switch devices.
5. The card lists the devices playing the app. **Stop sharing** restores its previous output preference. Closing the mixer also restores that preference.

All output configuration stays on the application's card. Extra rows can be removed; labels update automatically. Output selections and unfinished rows survive Refresh during the current app session. Changing a multi-output draft does not alter playback until you click Apply Outputs. Missing or duplicate devices produce an inline message, leaving a valid existing stream playing.

While sharing, edit the rows and apply them to reconfigure that same app. Removing the final extra row stops sharing and routes directly to Output A. A single direct output changes immediately from its dropdown. Sharing still needs a dedicated virtual device and supports one application bridge at a time.

Each output has an independent playback worker with a bounded queue, so a slower output does not hold up the others or accumulate a long backlog. Per-output delay supports manual alignment of Bluetooth and wired devices. Different device clocks and changing wireless latency may require readjustment. A disconnected/failed output stops the bridge and restores the app's original route. One program bridge is supported at a time; all ordinary volume controls remain available.

## Output sync: adjust each device's delay

Open **Output sync**, or use **Adjust output delays** on the currently shared program. Playing outputs appear first. Each output has:

- A **0–1,000 ms** slider, updated live while sharing audio.
- A millisecond entry, plus **−5/+5 ms** and **−1/+1 ms** buttons for coarse and fine adjustment.
- Starting presets at **0, 50, 100, 150, 200, 250, 300, and 500 ms**.
- A per-device **Reset** button and **Reset all output delays**.

Add delay to the faster device. For example, if the Bluetooth speaker sounds 150 ms later than the headset, set the headset to **150 ms** and leave Bluetooth at **0 ms**. Increase or decrease the headset delay until the echo disappears. The preset values are convenient starting points, not measured profiles for particular Bluetooth models or codecs.

Delay is implemented with a bounded audio sample buffer at 48 kHz, independently for each output. Adjusting the slider changes the delay tap with a short crossfade; it may briefly blend two moments of the audio while you adjust. Initial delay introduces silence until the buffer fills. These controls apply to the mixer's shared playback path. Ordinary direct Windows routing uses the destination device's native timing.

Settings are remembered by Windows endpoint ID at `%LOCALAPPDATA%\VolumeMixer\output-delays.json`. If a device is reinstalled and Windows assigns it a new endpoint ID, configure its delay again. Automatic latency measurement and long-term clock synchronization are not implemented.

## Line up outputs by ear

The **Listen and line up** panel in Output sync plays identical test sounds through the same per-output delay buffers used for shared audio.

1. Select **Output A** (usually your faster headset) and **Output B** (usually your slower Bluetooth speaker).
2. Choose a sound and tempo, then click **Play alignment sound**. The default is **Short click** at **90 BPM**. The initial test level is 20%; increase it as needed to hear both devices clearly.
3. Use **A only** and **B only** to identify each output. Switch back to **Both together** for alignment.
4. Listen from your usual position. Adjust the faster output using the slider/5 ms steps, then use the 1 ms buttons to make the double tap sound as close to one tap as possible.
5. Pause and restart the test to re-check your match. Stop with **Stop test / resume audio**. Delay settings stay saved.

Choose **Short click**, **Woodblock**, **Bright ding**, **Soft bell**, **Bass bump**, or **Soft noise burst**. The synthesized sounds have a short attack and tapered ending. Bell/ding provide pitched alternatives; bass bump is a short descending kick-like tone. Short click remains the default for judging closely spaced hits.

Tempo can be set from **30 to 240 BPM**, with presets at **30, 60, 90, 120, 150, 180, and 240 BPM**. At 90 BPM a hit repeats about every 667 ms; 120 BPM gives 500 ms and 240 BPM gives 250 ms. Sound, volume and tempo can all change while the test plays. Tempo changes use a brief settling interval before restarting the beat.

Use a slower tempo when aligning large delays: an offset equal to one whole beat can sound synchronized at fast tempos. Check the result at 30 BPM before keeping it. Both devices receive the same waveform and sample timing; their individual delays still apply. Calibration volume controls the test sound independently.

Standalone testing opens the chosen outputs directly and needs no virtual cable or microphone. During an existing shared stream, choose two of its active outputs: the test temporarily replaces the source sound and silences unselected outputs. Stopping resumes the original stream without changing the program's output preference. Starting a test while a bridge is still opening is blocked until it is ready.

The default is our practical recommendation inferred from research on brief transient sounds, not a claim that one test sound is universally optimal. [Research on the precedence effect](https://pmc.ncbi.nlm.nih.gov/articles/PMC4032431/) uses brief broadband noise bursts to examine perception of delayed sounds; [click-rate experiments](https://pubmed.ncbi.nlm.nih.gov/2762101/) also show that repetition affects echo perception. Hearing one event can therefore still hide a small residual delay. This is approximate listening calibration; objective alignment needs a microphone and timing reference, as in [miniDSP's REW alignment procedure](https://www.minidsp.com/applications/rew/speaker-time-alignment).

## Compatibility and validation

Output/input preferences use Windows' internal AudioPolicyConfig interface, with fallbacks for current and older Windows builds. Windows updates may affect compatibility; ordinary volume controls remain usable if routing is unavailable. The interface layout was checked against [EarTrumpet's implementation](https://github.com/File-New-Project/EarTrumpet/tree/master/EarTrumpet/Interop/MMDeviceAPI). Audio endpoints and sessions use [Pycaw](https://andremiras.github.io/pycaw/); streaming uses [SoundCard](https://soundcard.readthedocs.io/en/latest/).

Run tests with `.\.venv\Scripts\python.exe -m unittest discover -s tests`. Logs are stored at `%LOCALAPPDATA%\VolumeMixer\mixer.log`.

Validated on this Windows 11 PC: device/program detection, routing/restoration, per-output delay, calibration controls, and inline output UI interactions. Automated tests cover adding/removing output drafts, default-device resolution, duplicate rejection, reconfiguration with original routes preserved, all six sounds, beat spacing, live tempo changes, channel mapping, and the existing mixer behavior. UI checks cover A/B/C rows, dropdown selection, refresh persistence, Apply Outputs, pending controls, last-extra removal, and absence of configuration popups. Hardware smoke tests use unused virtual endpoints and zero-volume calibration so they do not play audible test sounds on your devices. Sound preferences and by-ear Bluetooth alignment still need listening tests on your chosen devices.

`smoke_test.py` runs those integration checks using its own silent session and unused virtual endpoints. Routing writes require running outside a restricted sandbox. If Voicemeeter's audio engine is required for your installed virtual endpoints, keep it running while using them.
