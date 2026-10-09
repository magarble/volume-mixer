import os
from dataclasses import dataclass, field
from pycaw.pycaw import AudioUtilities, AudioSession
from pycaw.constants import DEVICE_STATE
from pycaw.api.audiopolicy import IAudioSessionControl2
from routing import Routing
from app_names import friendly_name


@dataclass
class Program:
    pid: int
    name: str
    sessions: list
    endpoints: set
    active_endpoints: set = field(default_factory=set)
    process_name: str = ''

    @property
    def volume(self):
        return round(self.sessions[0].SimpleAudioVolume.GetMasterVolume() * 100)

    @property
    def muted(self):
        return bool(self.sessions[0].SimpleAudioVolume.GetMute())

    def set_volume(self, value):
        for session in self.sessions:
            session.SimpleAudioVolume.SetMasterVolume(float(value) / 100, None)

    def set_mute(self, muted):
        for session in self.sessions:
            session.SimpleAudioVolume.SetMute(bool(muted), None)


class Audio:
    def __init__(self):
        self.routing_error = None
        try:
            self.routing = Routing()
        except Exception as exc:
            self.routing = None
            self.routing_error = str(exc)
        self.outputs = []
        self.inputs = []

    def refresh(self):
        self.outputs = AudioUtilities.GetAllDevices(data_flow=0, device_state=DEVICE_STATE.ACTIVE.value)
        self.inputs = AudioUtilities.GetAllDevices(data_flow=1, device_state=DEVICE_STATE.ACTIVE.value)
        programs = {}
        for device in self.outputs:
            manager = device.AudioSessionManager
            sessions = manager.GetSessionEnumerator()
            for i in range(sessions.GetCount()):
                control = sessions.GetSession(i)
                if control is None:
                    continue
                session = AudioSession(control.QueryInterface(IAudioSessionControl2))
                if session.State == 2:
                    continue
                pid = session.ProcessId
                if pid == os.getpid():
                    continue
                if pid not in programs:
                    process_name, executable = f"Process {pid}", ''
                    try:
                        process = session.Process
                        if process:
                            process_name = process.name()
                            executable = process.exe()
                    except Exception:
                        pass
                    name = friendly_name(process_name, executable, session.DisplayName) if pid else 'System sounds'
                    programs[pid] = Program(pid, name, [], set(), process_name=process_name if pid else 'Windows system audio')
                programs[pid].sessions.append(session)
                programs[pid].endpoints.add(device.id)
                if session.State == 1:
                    programs[pid].active_endpoints.add(device.id)
        return sorted(programs.values(), key=lambda p: p.name.lower())

    def route(self, pid, endpoint, flow=0):
        if not self.routing:
            raise RuntimeError(self.routing_error or "Routing is unavailable on this Windows version.")
        if not pid:
            raise ValueError("System sounds cannot have a per-program route.")
        self.routing.set(pid, endpoint, flow)
