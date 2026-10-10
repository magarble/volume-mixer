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
    # Collect Tk variables on the UI thread before starting audio workers.
    import gc
    del root
    gc.collect()
    audio.routing.close()
    print("UI smoke test passed.")

    # Capture a separate silent helper process so playback cannot feed back.
    import subprocess
    import sys
    helper_code = """
import comtypes
import soundcard as sc
import numpy as np
with sc.get_speaker(__import__('sys').argv[1]).player(samplerate=48000, channels=2, blocksize=960) as player:
    print('ready', flush=True)
    for _ in range(1500):
        player.play(np.zeros((960, 2), dtype=np.float32))
"""
    physical = [d for d in audio.outputs if not any(word in d.FriendlyName.lower() for word in ('virtual', 'broadcast', 'cable'))]
    if len(physical) >= 2:
        helper = subprocess.Popen([sys.executable, '-c', helper_code, physical[0].id], stdout=subprocess.PIPE, text=True)
        bridge = Bridge()
        try:
            assert helper.stdout.readline().strip() == 'ready'
            bridge.set_delay(physical[1].id, 150)
            bridge.start_process(helper.pid, (physical[1].id,))
            assert bridge.ready.wait(15), 'Process capture startup timed out'
            assert not bridge.error, bridge.error
            time.sleep(.3)
            bridge.set_delay(physical[1].id, 100)
            time.sleep(.2)
            assert not bridge.error, bridge.error
            assert bridge.get_delay(physical[1].id) == 100
        finally:
            try:
                bridge.stop()
            finally:
                helper.terminate()
                helper.wait(timeout=5)
        print('Driver-free process capture, physical extra output, live delay adjustment, and shutdown passed with a silent source.')
    else:
        print('Driver-free playback smoke skipped: two connected physical outputs required.')


if __name__ == '__main__':
    main()
