import logging
import os
import queue
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from audio import Audio
from bridge import Bridge
from device_choices import DeviceChoices
from pycaw.pycaw import AudioUtilities
from delay_controls import DelayControls
from delay_preferences import DelayPreferences
from calibration import PATTERNS
from calibration_controls import CalibrationControls

BG = "#10131c"
CARD = "#1b2130"
TEXT = "#edf1fa"
MUTED = "#9ba8bf"
ACCENT = "#79b8ff"


class Mixer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Volume Mixer")
        self.geometry("1060x780")
        self.minsize(860, 620)
        self.configure(bg=BG)
        self.audio = Audio()
        self.bridge = Bridge()
        settings_dir = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'VolumeMixer'
        self.delay_preferences = DelayPreferences(settings_dir / 'output-delays.json')
        for device_id, value in self.delay_preferences.values.items():
            self.bridge.set_delay(device_id, value)
        self.delay_variables = {}
        self.delay_save_job = None
        self.programs = []
        self.boost_route = None
        self.pending_boost = None
        self.bridge_outputs = ()
        self.bridge_name = ''
        self.calibration_selection = ()
        self.calibration_pattern = tk.StringVar(value=next(iter(PATTERNS)))
        self.calibration_level = tk.DoubleVar(value=20)
        self.calibration_tempo = tk.StringVar(value='90')
        self.calibration_audition = tk.StringVar(value='both')
        self.calibration_status = tk.StringVar(value='Choose two devices, a sound and a tempo, then play the test.')
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.style()
        header = ttk.Frame(self, padding=(26, 22))
        header.pack(fill="x")
        ttk.Label(header, text="Volume Mixer", font=("Segoe UI", 25, "bold")).pack(side="left")
        ttk.Button(header, text="Refresh devices & apps", command=self.refresh).pack(side="right", pady=8)
        ttk.Label(self, text="Your sound, program by program.", foreground=MUTED, padding=(26, 0)).pack(anchor="w")
        tabs = ttk.Notebook(self)
        self.tabs = tabs
        tabs.pack(fill="both", expand=True, padx=26, pady=18)
        self.apps_frame = self.scroll_tab(tabs, "Programs")
        self.devices_frame = self.scroll_tab(tabs, "Input & output")
        self.sync_frame = self.scroll_tab(tabs, 'Output sync')
        self.sync_tab_index = tabs.index('end') - 1
        self.boost_frame = self.scroll_tab(tabs, "200% boost")
        self.status = tk.StringVar(value="Ready")
        ttk.Label(self, textvariable=self.status, foreground=MUTED, wraplength=1000, padding=(26, 12)).pack(fill="x")
        self.build_boost()
        self.refresh()
        self.after(200, self.poll)

    def style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD)
        style.configure("Card.TLabel", background=CARD)
        style.configure("TButton", background="#29344a", foreground=TEXT, padding=(12, 8), borderwidth=0)
        style.map("TButton", background=[("active", "#3b5071")])
        style.configure("TCheckbutton", background=CARD)
        style.configure("TCombobox", fieldbackground="#29344a", background="#29344a", foreground=TEXT, padding=5)
        style.map("TCombobox", fieldbackground=[("readonly", "#29344a")], foreground=[("readonly", TEXT)])
        style.configure("Horizontal.TScale", background=CARD, troughcolor="#35415a")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(20, 12), background=CARD)
        style.map("TNotebook.Tab", background=[("selected", "#2b3b56")], foreground=[("selected", ACCENT)])
        self.option_add("*TCombobox*Listbox.background", CARD)
        self.option_add("*TCombobox*Listbox.foreground", TEXT)

    def scroll_tab(self, notebook, title):
        outer = ttk.Frame(notebook)
        notebook.add(outer, text=title)
        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = ttk.Frame(canvas, padding=(0, 12, 12, 12))
        window = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
        outer.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", lambda ev: canvas.yview_scroll(int(-ev.delta / 120), "units")))
        outer.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        return inner

    def action(self, callback, success=None):
        try:
            callback()
            if success:
                self.status.set(success)
        except Exception as exc:
            logging.exception("Audio operation failed")
            self.status.set(str(exc))
            messagebox.showerror("Audio operation failed", str(exc), parent=self)

    def refresh(self):
        self.action(self._refresh)

    def _refresh(self):
        self.programs = self.audio.refresh()
        for frame in (self.apps_frame, self.devices_frame, self.sync_frame):
            for child in frame.winfo_children():
                child.destroy()
        ttk.Label(self.apps_frame, text="Play audio in a program to make it appear here. Refresh after opening or closing programs.",
                  foreground=MUTED, wraplength=880).pack(anchor="w", padx=14, pady=(0, 12))
        if not self.programs:
            ttk.Label(self.apps_frame, text="No audio programs found.", font=("Segoe UI", 17)).pack(pady=36)
        for program in self.programs:
            self.program_card(program)
        for title, devices in (("OUTPUT DEVICES", self.audio.outputs), ("INPUT DEVICES", self.audio.inputs)):
            ttk.Label(self.devices_frame, text=title, foreground=ACCENT).pack(anchor="w", padx=14, pady=10)
            for device in devices:
                self.device_card(device)
        self.build_output_sync()
        self.boost_app["values"] = [f"{p.name} · PID {p.pid}" for p in self.programs if p.pid]
        self.boost_source["values"] = [d.FriendlyName for d in self.audio.outputs]
        self.boost_targets.set_devices(self.audio.outputs)
        self.mic_source["values"] = [d.FriendlyName for d in self.audio.inputs]
        self.boost_app.set("")
        self.boost_source.set("")
        self.mic_source.set("")
        self.status.set(f"{len(self.programs)} audio programs · {len(self.audio.outputs)} outputs · {len(self.audio.inputs)} inputs")
        if self.audio.routing_error:
            self.status.set("Volume controls are available. Per-program routing unavailable: " + self.audio.routing_error)

    def slider(self, parent, initial, callback, maximum=100):
        row = ttk.Frame(parent, style="Card.TFrame")
        row.pack(fill="x", pady=8)
        value = tk.DoubleVar(value=initial)
        label = ttk.Label(row, text=f"{initial:.0f}%", style="Card.TLabel", width=6, font=("Segoe UI", 12, "bold"))
        label.pack(side="right", padx=8)
        def changed(raw):
            number = round(float(raw))
            label.configure(text=f"{number}%")
            try:
                callback(number)
            except Exception as exc:
                self.status.set(str(exc))
        ttk.Scale(row, from_=0, to=maximum, variable=value, command=changed).pack(fill="x", expand=True, padx=4)
        value.trace_add('write', lambda *args: label.configure(text=f"{value.get():.0f}%"))
        return value

    def program_card(self, program):
        card = ttk.Frame(self.apps_frame, style="Card.TFrame", padding=18)
        card.pack(fill="x", padx=8, pady=5)
        top = ttk.Frame(card, style="Card.TFrame")
        top.pack(fill="x")
        ttk.Label(top, text=program.name, style="Card.TLabel", font=("Segoe UI", 13, "bold")).pack(side="left")
        mute = tk.BooleanVar(value=program.muted)
        ttk.Checkbutton(top, text="Mute", variable=mute,
                        command=lambda: self.action(lambda: program.set_mute(mute.get()))).pack(side="right")
        ttk.Label(card, text=f"{program.process_name} · PID {program.pid}", style="Card.TLabel",
                  foreground=MUTED).pack(anchor="w", pady=(4, 0))
        self.slider(card, program.volume, program.set_volume)
        row = ttk.Frame(card, style="Card.TFrame")
        row.pack(fill="x")
        self.route_choice(row, program, self.audio.outputs, 0, "Output")
        self.route_choice(row, program, self.audio.inputs, 1, "Input")
        if program.pid:
            sharing = ttk.Frame(card, style="Card.TFrame")
            sharing.pack(fill="x", pady=(12, 0))
            ttk.Button(sharing, text="Play on multiple outputs…",
                       command=lambda: self.multi_output_dialog(program)).pack(side="left")
            if self.boost_route and self.boost_route[0] == program.pid:
                ttk.Button(sharing, text="Stop & restore output",
                           command=lambda: self.action(self.stop_and_refresh)).pack(side="left", padx=12)
                ttk.Button(sharing, text='Adjust output delays', command=self.show_output_sync).pack(side='left')
                names = {d.id: d.FriendlyName for d in self.audio.outputs}
                ttk.Label(card, text="Playing on: " + ', '.join(names.get(i, i) for i in self.bridge_outputs),
                          style="Card.TLabel", foreground=ACCENT, wraplength=850).pack(anchor="w", pady=(10, 0))

    def route_choice(self, row, program, devices, flow, title):
        ttk.Label(row, text=title, style="Card.TLabel").pack(side="left", padx=(0, 8))
        names = ["Windows default"] + [d.FriendlyName for d in devices]
        ids = [""] + [d.id for d in devices]
        combo = ttk.Combobox(row, values=names, state="readonly", width=31)
        combo.pack(side="left", padx=(0, 16))
        combo.current(0)
        if not program.pid or not self.audio.routing:
            combo.configure(state="disabled")
            return
        try:
            current = self.audio.routing.get(program.pid, flow)
            if current in ids:
                combo.current(ids.index(current))
        except Exception:
            self.status.set("Some routing preferences could not be read.")
        previous = [combo.current()]
        def selected(event):
            try:
                bridged = self.boost_route or self.pending_boost
                if bridged and bridged[0] == program.pid and flow == 0:
                    raise RuntimeError("Stop this program's audio bridge before changing its output.")
                self.audio.route(program.pid, ids[combo.current()], flow)
                previous[0] = combo.current()
                self.status.set(f"{program.name}: {title.lower()} set. Some programs need playback restarted to switch devices.")
            except Exception as exc:
                combo.current(previous[0])
                messagebox.showerror("Routing failed", str(exc), parent=self)
        combo.bind("<<ComboboxSelected>>", selected)

    def device_card(self, device):
        card = ttk.Frame(self.devices_frame, style="Card.TFrame", padding=16)
        card.pack(fill="x", padx=8, pady=5)
        endpoint = device.EndpointVolume
        ttk.Label(card, text=device.FriendlyName, style="Card.TLabel", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.slider(card, endpoint.GetMasterVolumeLevelScalar() * 100,
                    lambda v: endpoint.SetMasterVolumeLevelScalar(v / 100, None))
        mute = tk.BooleanVar(value=bool(endpoint.GetMute()))
        ttk.Checkbutton(card, text="Mute device", variable=mute,
                        command=lambda: self.action(lambda: endpoint.SetMute(mute.get(), None))).pack(anchor="w")

    def delay_variable(self, device_id):
        if device_id not in self.delay_variables:
            variable = tk.IntVar(value=self.bridge.get_delay(device_id))
            self.delay_variables[device_id] = variable
            def changed(*args):
                value = variable.get()
                self.bridge.set_delay(device_id, value)
                self.delay_preferences.set(device_id, value)
                if self.delay_save_job:
                    self.after_cancel(self.delay_save_job)
                self.delay_save_job = self.after(500, self.save_output_delays)
            variable.trace_add('write', changed)
        return self.delay_variables[device_id]

    def save_output_delays(self):
        self.delay_save_job = None
        try:
            self.delay_preferences.save()
        except OSError as exc:
            logging.exception('Could not save output delays')
            self.status.set(f'Delay applied, but settings could not be saved: {exc}')

    def show_output_sync(self):
        self.tabs.select(self.sync_tab_index)

    def build_output_sync(self):
        frame = self.sync_frame
        ttk.Label(frame, text='Line up your speakers and headset', font=('Segoe UI', 20, 'bold')).pack(anchor='w', padx=14, pady=(0, 12))
        ttk.Label(frame, text='Add delay to the faster output until you hear both together. Changes apply live during shared or boosted playback and are remembered per device.\n\nExample: if Bluetooth is about 150 ms late, add 150 ms to your headset and leave Bluetooth at 0 ms. Presets are starting points; the best value depends on your devices.',
                  foreground=MUTED, wraplength=880, justify='left').pack(anchor='w', padx=14, pady=(0, 12))
        running = self.bridge.thread and self.bridge.thread.is_alive()
        candidates = [d for d in self.audio.outputs if not running or d.id in self.bridge.outputs]
        candidates.sort(key=lambda d: (self.is_cable(d), d.FriendlyName.lower()))
        available = {d.id for d in candidates}
        selected = tuple(i for i in self.calibration_selection if i in available)
        if len(selected) != 2:
            selected = tuple(i for i in self.bridge_outputs if i in available)[:2]
        if len(selected) != 2:
            selected = tuple(d.id for d in candidates[:2])
        self.calibration_selection = selected
        self.calibration_controls = CalibrationControls(
            frame, candidates, selected, self.calibration_pattern, self.calibration_level,
            self.calibration_audition, self.calibration_tempo, self.bridge.calibrating, self.calibration_status,
            self.start_alignment_test, self.stop_alignment_test, self.update_alignment_test,
            self.select_alignment_outputs)
        self.calibration_controls.pack(fill='x', padx=8, pady=(0, 16))
        ttk.Button(frame, text='Reset all output delays', command=self.reset_output_delays).pack(anchor='w', padx=14, pady=(0, 12))
        self.sync_devices_frame = ttk.Frame(frame)
        self.sync_devices_frame.pack(fill='x')
        self.build_sync_device_cards()

    def build_sync_device_cards(self):
        for child in self.sync_devices_frame.winfo_children():
            child.destroy()
        priority = self.calibration_selection or self.bridge_outputs
        devices = sorted(self.audio.outputs, key=lambda d: (d.id not in priority, d.id not in self.bridge_outputs, d.FriendlyName.lower()))
        for device in devices:
            card = ttk.Frame(self.sync_devices_frame, style='Card.TFrame', padding=16)
            card.pack(fill='x', padx=8, pady=5)
            heading = ttk.Frame(card, style='Card.TFrame')
            heading.pack(fill='x')
            ttk.Label(heading, text=device.FriendlyName, style='Card.TLabel', font=('Segoe UI', 12, 'bold')).pack(side='left')
            if device.id in self.calibration_selection:
                letter = 'A' if device.id == self.calibration_selection[0] else 'B'
                ttk.Label(heading, text=f'Output {letter}', style='Card.TLabel', foreground=ACCENT).pack(side='left', padx=12)
            if device.id in self.bridge_outputs:
                ttk.Label(heading, text='Playing now' if self.bridge.ready.is_set() and not self.bridge.error else 'Selected output',
                          style='Card.TLabel', foreground=ACCENT).pack(side='right')
            controls = DelayControls(card, self.delay_variable(device.id), self.status.set)
            controls.pack(fill='x', pady=(6, 0))

    def select_alignment_outputs(self, outputs):
        self.calibration_selection = tuple(outputs)
        self.build_sync_device_cards()

    def start_alignment_test(self, outputs, options):
        def start():
            if self.pending_boost:
                raise RuntimeError('Wait for the current bridge to finish starting.')
            if self.boost_route and not (self.bridge.thread and self.bridge.thread.is_alive()):
                raise RuntimeError('Stop and restore the failed audio bridge before starting a new test.')
            connected = {d.id for d in self.audio.outputs}
            if len(outputs) != 2 or any(i not in connected for i in outputs):
                raise ValueError('Choose two connected output devices.')
            self.bridge.start_calibration(outputs, **options)
            self.calibration_selection = tuple(outputs)
            if self.bridge.calibration_only:
                self.bridge_outputs = tuple(outputs)
                self.bridge_name = 'Alignment test'
            self.calibration_status.set('Playing the alignment sound. Delay the faster output until the two hits sound like one.')
            self.calibration_controls.set_running(True)
            self.build_sync_device_cards()
        self.action(start)

    def update_alignment_test(self, outputs, options):
        if self.bridge.calibrating:
            self.action(lambda: self.bridge.update_calibration(outputs, **options))

    def stop_alignment_test(self):
        def stop():
            standalone = self.bridge.calibration_only
            self.bridge.end_calibration()
            if standalone:
                self.bridge_outputs = ()
                self.bridge_name = ''
            self.calibration_status.set('Test stopped. Delay settings are saved.' + (' Shared audio resumed.' if not standalone else ''))
            self._refresh()
        self.action(stop)

    def reset_output_delays(self):
        ids = set(self.delay_variables) | set(self.delay_preferences.values)
        for device_id in ids:
            self.delay_variable(device_id).set(0)

    def build_boost(self):
        frame = self.boost_frame
        ttk.Label(frame, text="Audio bridge · up to 200%", font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(frame, text="Program boost needs a virtual audio cable such as VB-CABLE. Choose its playback endpoint (usually CABLE Input) as the source, and your speakers or headphones as the destination. Keep the cable dedicated to this program.\n\nMicrophone boost sends an amplified microphone to a virtual cable playback endpoint; choose the cable's recording endpoint (usually CABLE Output) as input in your calling or recording program.",
                  foreground=MUTED, wraplength=880, justify="left").pack(anchor="w", pady=16)
        self.mode = tk.StringVar(value="program")
        choices = ttk.Frame(frame)
        choices.pack(anchor="w", pady=6)
        ttk.Radiobutton(choices, text="Program output boost", variable=self.mode, value="program").pack(side="left", padx=(0, 24))
        ttk.Radiobutton(choices, text="Microphone input boost", variable=self.mode, value="microphone").pack(side="left")
        self.boost_app = self.field(frame, "Program (for output boost)")
        self.boost_source = self.field(frame, "Virtual cable playback endpoint (program boost source)")
        self.mic_source = self.field(frame, "Microphone (microphone boost source)")
        ttk.Label(frame, text="Outputs — select one or more (use virtual cable outputs for microphone boost)").pack(anchor="w", pady=(12, 6))
        self.boost_targets = DeviceChoices(frame)
        self.boost_targets.pack(fill="x")
        gain_card = ttk.Frame(frame, style="Card.TFrame", padding=12)
        gain_card.pack(fill="x", pady=14)
        self.gain_value = self.slider(gain_card, 100, lambda value: setattr(self.bridge, "gain", value), maximum=200)
        buttons = ttk.Frame(frame)
        buttons.pack(anchor="w")
        ttk.Button(buttons, text="Start boost", command=lambda: self.action(self.start_boost)).pack(side="left", padx=(0, 12))
        ttk.Button(buttons, text="Stop & restore output", command=lambda: self.action(self.stop_boost)).pack(side="left")
        ttk.Button(frame, text='Adjust output delays', command=self.show_output_sync).pack(anchor='w', pady=(12, 0))
        ttk.Label(frame, text="Use Output sync to delay faster devices and line them up with Bluetooth. One program or microphone bridge at a time. 200% doubles sample amplitude (+6 dB); overloaded peaks may distort. Keep this app open while sharing audio.",
                  foreground=MUTED, wraplength=880).pack(anchor="w", pady=14)

    @staticmethod
    def field(parent, text):
        ttk.Label(parent, text=text).pack(anchor="w", pady=(8, 4))
        combo = ttk.Combobox(parent, state="readonly", width=75)
        combo.pack(fill="x")
        return combo

    @staticmethod
    def is_cable(device):
        return any(token in device.FriendlyName.lower() for token in ("cable", "voicemeeter", "virtual"))

    def multi_output_dialog(self, program):
        dialog = tk.Toplevel(self)
        dialog.title(f"Outputs for {program.name}")
        dialog.configure(bg=BG)
        dialog.geometry("720x620")
        dialog.minsize(620, 580)
        dialog.transient(self)
        frame = ttk.Frame(dialog, padding=22)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=program.name, font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"{program.process_name} · PID {program.pid}", foreground=MUTED).pack(anchor="w", pady=(4, 12))
        ttk.Label(frame, text="Select your headset, Bluetooth speaker, or any other outputs to play them together. A dedicated virtual audio device carries this app's sound to the selected outputs.",
                  foreground=MUTED, wraplength=650).pack(anchor="w", pady=(0, 10))
        outputs = list(self.audio.outputs)
        choices = DeviceChoices(frame, height=230)
        choices.pack(fill="both", expand=True)
        selected = self.bridge_outputs if self.boost_route and self.boost_route[0] == program.pid else ()
        choices.set_devices(outputs, selected)
        cables = [d for d in outputs if self.is_cable(d)]
        source = self.field(frame, "Dedicated virtual audio device")
        source['values'] = [d.FriendlyName for d in cables]
        used = {i for p in self.programs if p.pid != program.pid for i in p.active_endpoints}
        default = AudioUtilities.GetSpeakers()
        available = [i for i, d in enumerate(cables) if d.id not in used and (not default or d.id != default.id)]
        if available:
            source.current(available[0])
        ttk.Label(frame, text="Use Output sync to delay faster outputs until they line up with Bluetooth. Use 100% gain for normal playback; adjust gain in the 200% boost tab if needed.",
                  foreground=MUTED, wraplength=650).pack(anchor="w", pady=12)
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x")
        def start():
            try:
                targets = choices.selected_ids()
                if len(targets) < 2:
                    raise ValueError("Select at least two output devices.")
                if source.current() < 0:
                    raise ValueError("Choose an unused virtual audio device. Install a virtual cable if none is available.")
                self.start_program_bridge(program, cables[source.current()], targets, reset_gain=True)
                dialog.destroy()
            except Exception as exc:
                messagebox.showerror("Could not start multiple outputs", str(exc), parent=dialog)
        ttk.Button(buttons, text="Start multiple outputs", command=start).pack(side="left")
        ttk.Button(buttons, text="Close", command=dialog.destroy).pack(side="right")
        def adjust_delays():
            self.show_output_sync()
            dialog.destroy()
        ttk.Button(buttons, text='Adjust delays', command=adjust_delays).pack(side='left', padx=10)
        if self.boost_route and self.boost_route[0] == program.pid:
            ttk.Button(buttons, text="Stop & restore output",
                       command=lambda: self.action(self.stop_and_refresh)).pack(side="left", padx=10)

    def start_program_bridge(self, program, source, targets, reset_gain=False):
        if self.pending_boost or self.boost_route or (self.bridge.thread and self.bridge.thread.is_alive()):
            raise RuntimeError("Stop the current audio bridge before starting another.")
        if not self.is_cable(source):
            raise ValueError("Choose a virtual audio device as source to keep this program isolated.")
        if not self.audio.routing:
            raise RuntimeError("Per-program routing is unavailable on this Windows version.")
        if source.id in targets:
            raise ValueError("The dedicated virtual device cannot also be a selected output.")
        default = AudioUtilities.GetSpeakers()
        if default and default.id == source.id:
            raise ValueError("The virtual device is your Windows default output. Choose a dedicated device so other apps aren't shared too.")
        live_programs = self.audio.refresh()
        if any(p.pid != program.pid and source.id in p.active_endpoints for p in live_programs):
            raise ValueError("Another program is playing through this virtual device. Choose an unused device.")
        connected = {d.id for d in self.audio.outputs}
        if not targets or any(target not in connected for target in targets) or source.id not in connected:
            raise ValueError("A selected device disconnected. Refresh and choose connected devices.")
        old_route = self.audio.routing.snapshot(program.pid)
        if reset_gain:
            self.bridge.gain = 100
            self.gain_value.set(100)
        self.pending_boost = (program.pid, old_route, source.id)
        self.bridge_outputs = tuple(targets)
        self.bridge_name = program.name
        try:
            self.bridge.start(source.id, targets)
        except Exception:
            self.pending_boost = None
            self.bridge_outputs = ()
            raise
        self.status.set(f"Starting audio for {program.name} on {len(targets)} output device(s)…")

    def start_boost(self):
        if self.pending_boost or self.boost_route or (self.bridge.thread and self.bridge.thread.is_alive()):
            raise RuntimeError("Stop the current bridge before starting another.")
        targets = self.boost_targets.selected_ids()
        if not targets:
            raise ValueError("Choose at least one output device.")
        if self.mode.get() == "program":
            apps = [p for p in self.programs if p.pid]
            i, j = self.boost_app.current(), self.boost_source.current()
            if i < 0 or j < 0:
                raise ValueError("Choose a program and a virtual cable source.")
            program, source = apps[i], self.audio.outputs[j]
            self.start_program_bridge(program, source, targets)
        else:
            i = self.mic_source.current()
            if i < 0:
                raise ValueError("Choose a microphone.")
            chosen = [d for d in self.audio.outputs if d.id in targets]
            if not all(self.is_cable(target) for target in chosen):
                raise ValueError("Choose virtual cable destinations for microphone boost.")
            self.bridge_outputs = targets
            self.bridge_name = 'Microphone'
            self.bridge.start(self.audio.inputs[i].id, targets, loopback=False)
        self.status.set("Starting the audio bridge…")

    def stop_boost(self):
        self.pending_boost = None
        # Restore the program first so stopping the bridge does not strand its audio.
        if self.boost_route:
            pid, old_route = self.boost_route
            self.audio.route(pid, old_route)
            self.boost_route = None
        self.bridge.stop()
        self.bridge_outputs = ()
        controls = self.__dict__.get('calibration_controls')
        if controls:
            controls.set_running(False)
            self.calibration_status.set('Test stopped. Your delay settings are kept.')
        self.status.set("Audio bridge stopped; original program output restored.")

    def stop_and_refresh(self):
        self.stop_boost()
        self._refresh()

    def poll(self):
        try:
            while True:
                kind, text = self.bridge.events.get_nowait()
                if kind == "ready" and self.pending_boost:
                    pid, old_route, cable = self.pending_boost
                    self.pending_boost = None
                    try:
                        self.audio.route(pid, cable)
                        self.boost_route = (pid, old_route)
                        text = f"{self.bridge_name} is playing on {len(self.bridge_outputs)} output device(s). Restart playback if the app hasn't switched yet."
                        self._refresh()
                    except Exception as exc:
                        try:
                            self.stop_boost()
                        except Exception as stop_error:
                            text = f"{exc}; stop failed: {stop_error}"
                            self.status.set(text)
                            continue
                        text = str(exc)
                if kind == "error":
                    self.pending_boost = None
                    try:
                        self.stop_boost()
                        self._refresh()
                    except Exception as exc:
                        text += " Restore/stop failed: " + str(exc)
                    calibration_status = self.__dict__.get('calibration_status')
                    if calibration_status:
                        calibration_status.set(text)
                elif kind == 'ready' and getattr(self.bridge, 'calibrating', False):
                    self.calibration_status.set('Test sound is playing. Delay the faster output until the two hits sound like one.')
                    self.build_sync_device_cards()
                self.status.set(text)
        except queue.Empty:
            pass
        self.after(200, self.poll)

    def close(self):
        try:
            self.stop_boost()
        except Exception as exc:
            messagebox.showerror("Unable to stop boost", str(exc), parent=self)
            return
        if self.audio.routing:
            self.audio.routing.close()
        if self.delay_save_job:
            self.after_cancel(self.delay_save_job)
        self.save_output_delays()
        self.destroy()


if __name__ == "__main__":
    import os
    log_dir = Path(os.environ.get("LOCALAPPDATA", ".")) / "VolumeMixer"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=log_dir / "mixer.log", level=logging.INFO)
    try:
        Mixer().mainloop()
    except Exception as exc:
        logging.exception("Startup failed")
        messagebox.showerror("Volume Mixer could not start", str(exc))
