# Volume Mixer

A Windows desktop mixer with friendly application names, per-program volume and mute, input/output preferences, simultaneous playback on multiple devices, microphone/speaker volume, and real audio gain up to 200%.

## Run

Double-click `dist-calibration/VolumeMixer/VolumeMixer.exe` after building. Keep the entire `VolumeMixer` folder together; the executable does not need a separate Python installation.

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

1. On the application's card, click **Play on multiple outputs…**.
2. Check two or more outputs, for example your headset and Bluetooth speaker.
3. Choose a dedicated virtual audio playback device. The dialog preselects an unused one if available. Install a virtual cable if needed; keep the source separate from your selected outputs and your Windows default output.
4. Click **Start multiple outputs**. The app first opens all selected outputs, then routes the program to the virtual device. Some programs need playback restarted to switch devices.
5. The card lists the devices playing the app. Use **Stop & restore output** to return it to its previous output preference. Closing the mixer also restores that preference.

Sharing starts at normal 100% gain. You can adjust gain in the **200% boost** tab while sharing. Its Outputs checkboxes also support multiple destinations for program boost.

Each output has an independent playback worker with a bounded queue, so a slower output does not hold up the others or accumulate a long backlog. Per-output delay supports manual alignment of Bluetooth and wired devices. Different device clocks and changing wireless latency may require readjustment. A disconnected/failed output stops the bridge and restores the app's original route. One program or microphone bridge is supported at a time; all ordinary volume controls remain available.

## Output sync: adjust each device's delay

Open **Output sync**, or use **Adjust output delays** on the currently shared program. Playing outputs appear first. Each output has:

- A **0–1,000 ms** slider, updated live while sharing or boosting audio.
- A millisecond entry, plus **−5/+5 ms** and **−1/+1 ms** buttons for coarse and fine adjustment.
- Starting presets at **0, 50, 100, 150, 200, 250, 300, and 500 ms**.
- A per-device **Reset** button and **Reset all output delays**.

Add delay to the faster device. For example, if the Bluetooth speaker sounds 150 ms later than the headset, set the headset to **150 ms** and leave Bluetooth at **0 ms**. Increase or decrease the headset delay until the echo disappears. The preset values are convenient starting points, not measured profiles for particular Bluetooth models or codecs.

Delay is implemented with a bounded audio sample buffer at 48 kHz, independently for each output. Adjusting the slider changes the delay tap with a short crossfade; it may briefly blend two moments of the audio while you adjust. Initial delay introduces silence until the buffer fills. These controls apply to the mixer's shared/boosted playback path. Ordinary direct Windows routing uses the destination device's native timing.

Settings are remembered by Windows endpoint ID at `%LOCALAPPDATA%\VolumeMixer\output-delays.json`. If a device is reinstalled and Windows assigns it a new endpoint ID, configure its delay again. Automatic latency measurement and long-term clock synchronization are not implemented.

## Line up outputs by ear

The **Listen and line up** panel in Output sync plays identical test sounds through the same per-output delay buffers used for shared audio.

1. Select **Output A** (usually your faster headset) and **Output B** (usually your slower Bluetooth speaker).
2. Choose **Short click (recommended)** and click **Play alignment clicks**. The initial test level is 20%; increase the test volume only as needed to hear both devices clearly.
3. Use **A only** and **B only** to identify each output. Switch back to **Both together** for alignment.
4. Listen from your usual position. Adjust the faster output using the slider/5 ms steps, then use the 1 ms buttons to make the double tap sound as close to one tap as possible.
5. Pause and restart the test to re-check your match. Stop with **Stop test / resume audio**. Delay settings stay saved.

Clicks repeat every 2 seconds, with a short initial settling interval. The alternate **Soft noise burst** uses a longer transient if the click is difficult to hear. Both devices receive the same waveform and sample timing; their individual delays still apply. Calibration volume bypasses normal boost and peaks are bounded separately.

Standalone testing opens the chosen outputs directly and needs no virtual cable or microphone. During an existing shared/boosted stream, choose two of its active outputs: the test temporarily replaces the source sound and silences unselected outputs. Stopping resumes the original stream and gain without changing the program's output preference. Starting a test while a bridge is still opening is blocked until it is ready.

The default is our practical recommendation inferred from research on brief transient sounds, not a claim that one test sound is universally optimal. [Research on the precedence effect](https://pmc.ncbi.nlm.nih.gov/articles/PMC4032431/) uses brief broadband noise bursts to examine perception of delayed sounds; [click-rate experiments](https://pubmed.ncbi.nlm.nih.gov/2762101/) also show that repetition affects echo perception. Hearing one event can therefore still hide a small residual delay. This is approximate listening calibration; objective alignment needs a microphone and timing reference, as in [miniDSP's REW alignment procedure](https://www.minidsp.com/applications/rew/speaker-time-alignment).

## 200% program boost

Windows session volume stops at 100%. Boost uses WASAPI audio capture, sample gain, and playback instead of relabelling that slider.

1. Install a virtual audio cable separately, such as [VB-CABLE](https://vb-audio.com/Cable/). The app does not install drivers or change the system default device. Leave cable endpoint volume at 100% and turn off Windows “Listen to this device” for that cable.
2. Keep the cable dedicated to the program being boosted. Do not use it as your Windows default output. All audio sent to this cable passes through the same gain bridge; only one bridge is available in this version.
3. In **200% boost**, choose **Program output boost**, the program, the cable's playback endpoint (usually **CABLE Input**), and check your physical output device(s).
4. Click **Start boost**, restart the program's playback if necessary, and adjust the gain up to 200%.
5. **Stop & restore output** restores its previous output preference. Normal closing also restores it. Force termination or a crash cannot perform restoration; use the Programs tab or Windows volume mixer to restore the program's output if that happens.

200% means twice the audio sample amplitude, approximately +6.02 dB. It does not mean twice the perceived loudness. A hard clipper keeps samples between -1 and 1; overloaded peaks may distort. Device/session attenuation still affects the final loudness. The bridge adds latency and requires the mixer to remain running. Dedicated virtual cables would be needed for simultaneous independent program boosts.

## 200% microphone boost

Choose **Microphone input boost**, your physical microphone, and a virtual cable playback endpoint as destination. Start boost. Choose the cable's recording endpoint (usually **CABLE Output**) as input in the calling/recording program or its input preference in the Programs tab. Adjust gain up to 200%. This processes microphone samples before other programs capture them. Do not send the cable's own recording endpoint back into itself, and do not enable monitoring on that cable. Stop the bridge and restore the calling program's physical microphone when finished.

## Compatibility and validation

Output/input preferences use Windows' internal AudioPolicyConfig interface, with fallbacks for current and older Windows builds. Windows updates may affect compatibility; ordinary volume controls remain usable if routing is unavailable. The interface layout was checked against [EarTrumpet's implementation](https://github.com/File-New-Project/EarTrumpet/tree/master/EarTrumpet/Interop/MMDeviceAPI). Audio endpoints and sessions use [Pycaw](https://andremiras.github.io/pycaw/); streaming uses [SoundCard](https://soundcard.readthedocs.io/en/latest/).

Run gain tests with `.\.venv\Scripts\python.exe -m unittest discover -s tests`. Logs are stored at `%LOCALAPPDATA%\VolumeMixer\mixer.log`.

Validated on this Windows 11 PC: device/program detection, routing/restoration, per-output delay, and calibration UI controls. Thirty-seven automated tests cover click timing and chunk continuity, level bounds, solo listening, independent output delays, standalone operation without capture, and resumption of shared audio with routing/gain preserved, alongside the existing mixer tests. Hardware smoke tests use unused virtual endpoints and zero-volume calibration so they do not play audible clicks on your devices. Microphone boost, audible distortion, and by-ear Bluetooth alignment still need listening tests on your chosen devices.

`smoke_test.py` runs those integration checks using its own silent session and unused virtual endpoints. Routing writes require running outside a restricted sandbox. If Voicemeeter's audio engine is required for your installed virtual endpoints, keep it running while using them.
