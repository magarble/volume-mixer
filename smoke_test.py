"""Read devices/UI and verify routing using only this process's silent session."""
import os
import time
from audio import Audio
from app import Mixer
from bridge import Bridge
from pycaw.pycaw import AudioUtilities
import numpy as np
import soundcard as sc


def main():
    audio = Audio()
    programs = audio.refresh()
    print(f"Detected {len(programs)} programs, {len(audio.outputs)} outputs, {len(audio.inputs)} inputs.")
    if not audio.routing:
        raise RuntimeError(audio.routing_error)
    pid = os.getpid()
    with sc.default_speaker().player(samplerate=48000, channels=2) as player:
        player.play(np.zeros((960, 2), dtype=np.float32))
        for session in AudioUtilities.GetAllSessions():
            if session.ProcessId == pid:
                volume = session.SimpleAudioVolume
                original = volume.GetMasterVolume()
                try:
                    volume.SetMasterVolume(.5, None)
                    assert abs(volume.GetMasterVolume() - .5) < .001
                finally:
                    volume.SetMasterVolume(original, None)
                print("Temporary session volume change and restoration passed.")
        for flow, devices in ((0, audio.outputs), (1, audio.inputs)):
            original = audio.routing.snapshot(pid, flow)
            try:
                audio.routing.set(pid, devices[0].id, flow)
                assert audio.routing.snapshot(pid, flow) == (devices[0].id,) * 3
                audio.routing.set(pid, '', flow)
                assert audio.routing.snapshot(pid, flow) == ('',) * 3
            finally:
                if audio.routing.snapshot(pid, flow) != original:
                    audio.routing.set(pid, original, flow)
            print(f"Routing and restoration passed for flow {flow}.")
    root = Mixer()
    root.update()
    assert root.winfo_width() >= 860
    root.close()
    audio.routing.close()
    print("UI smoke test passed.")

    # Only use unused virtual playback endpoints. Never capture a live microphone.
    used = {endpoint for program in programs for endpoint in program.active_endpoints}
    virtual = [d for d in audio.outputs if 'voicemeeter' in d.FriendlyName.lower() and d.id not in used]
    if len(virtual) >= 3:
        bridge = Bridge()
        bridge.set_delay(virtual[1].id, 150)
        with sc.get_speaker(virtual[0].id).player(samplerate=48000, channels=2) as player:
            player.play(np.zeros((960, 2), dtype=np.float32))
            try:
                bridge.start(virtual[0].id, [virtual[1].id, virtual[2].id])
                assert bridge.ready.wait(timeout=5), 'Bridge startup timed out'
                if bridge.error:
                    raise RuntimeError(bridge.error)
                for index in range(10):
                    player.play(np.zeros((960, 2), dtype=np.float32))
                    if index == 5:
                        bridge.set_delay(virtual[1].id, 100)
                assert bridge.get_delay(virtual[1].id) == 100
                assert bridge.get_delay(virtual[2].id) == 0
                time.sleep(.2)
                if bridge.error:
                    raise RuntimeError(bridge.error)
            finally:
                bridge.stop()
        print('Two-output silent streaming at 200%, independent delays, live delay adjustment, and shutdown passed.')
        test = Bridge()
        test.set_delay(virtual[1].id, 150)
        try:
            test.start_calibration((virtual[1].id, virtual[2].id), level=0)
            assert test.ready.wait(timeout=5), 'Calibration startup timed out'
            if test.error:
                raise RuntimeError(test.error)
            time.sleep(.6)
            for pattern, bpm in (('ding', 120), ('bell', 180), ('bass', 240), ('woodblock', 90), ('burst', 60)):
                test.update_calibration((virtual[1].id, virtual[2].id), pattern=pattern, level=0, audition='a', bpm=bpm)
                time.sleep(.1)
            if test.error:
                raise RuntimeError(test.error)
        finally:
            test.end_calibration()
        print('Standalone calibration sounds, live tempo switching, solo and shutdown passed at zero test volume.')
    else:
        print('Bridge hardware smoke test skipped: three unused virtual endpoints required.')


if __name__ == '__main__':
    main()
