import logging
import os
import queue
import time
import psutil
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from audio import Audio
from bridge import Bridge
from pycaw.pycaw import AudioUtilities
from pycaw.constants import DEVICE_STATE
from delay_controls import DelayControls
from delay_preferences import DelayPreferences
from calibration import PATTERNS
from calibration_controls import CalibrationControls
from output_rows import OutputPlan, OutputRows

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
        self.output_plans = {}
        self.primary_output_id = ''
        self.share_check_at = 0
        self.shared_route = None
        self.pending_share = None
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
        self.scroll_canvases = {}
        # Widget class bindings run before bind_all and normally change values.
        # Handle their wheel events here, then stop the default value change.
        for widget_class in ('TCombobox', 'TSpinbox'):
            self.bind_class(widget_class, '<MouseWheel>', self.scroll_control)
        self.bind_all('<MouseWheel>', self.scroll_page, add='+')
        tabs.pack(fill="both", expand=True, padx=26, pady=18)
        self.apps_frame = self.scroll_tab(tabs, "Programs")
        self.devices_frame = self.scroll_tab(tabs, "Input & output")
        self.sync_frame = self.scroll_tab(tabs, 'Output sync')
        self.sync_tab_index = tabs.index('end') - 1
        self.status = tk.StringVar(value="Ready")
        ttk.Label(self, textvariable=self.status, foreground=MUTED, wraplength=1000, padding=(26, 12)).pack(fill="x")
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
        self.scroll_canvases[str(outer)] = canvas
        return inner

    def scroll_page(self, event):
        try:
            widget = self.winfo_containing(event.x_root, event.y_root)
        except KeyError:
            # Tk creates dropdown popups outside Python's widget registry.
            # Leave scrolling an open menu to its own listbox bindings.
            return
        if widget is None:
            return
        while widget is not None:
            canvas = self.scroll_canvases.get(str(widget))
            if canvas is not None:
                units = int(-event.delta / 120)
                if not units and event.delta:
                    units = -1 if event.delta > 0 else 1
                canvas.yview_scroll(units, 'units')
                return 'break'
            widget = getattr(widget, 'master', None)

    def scroll_control(self, event):
        self.scroll_page(event)
        return 'break'

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
        live_pids = {p.pid for p in self.programs}
        self.output_plans = {pid: plan for pid, plan in self.output_plans.items() if pid in live_pids}
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
        if program.pid:
            plan = self.program_output_plan(program)
            rows = OutputRows(card, plan, self.audio.outputs,
                              lambda row: self.route_choice(row, program, self.audio.inputs, 1, 'Input'),
                              lambda index: self.inline_output_changed(program, plan, index),
                              lambda index: self.remove_inline_output(program, plan, index),
                              lambda: self.apply_inline_outputs(program, plan),
                              lambda: self.stop_inline_outputs(program, plan), self.show_output_sync,
                              lambda: bool(self.shared_route and self.shared_route[0] == program.pid),
                              lambda: bool(self.pending_share and self.pending_share[0] == program.pid),
                              bool(self.audio.routing),
                              lambda: self.bridge_outputs)
            rows.pack(fill='x')
        else:
            row = ttk.Frame(card, style='Card.TFrame')
            row.pack(fill='x')
            self.route_choice(row, program, self.audio.outputs, 0, 'Output A')
            self.route_choice(row, program, self.audio.inputs, 1, 'Input')

    def program_output_plan(self, program):
        if program.pid not in self.output_plans:
            if self.shared_route and self.shared_route[0] == program.pid:
                self.output_plans[program.pid] = OutputPlan(list(self.bridge_outputs))
            else:
                try:
                    current = self.audio.routing.get(program.pid) if self.audio.routing else ''
                except Exception:
                    current = ''
                self.output_plans[program.pid] = OutputPlan([current])
        return self.output_plans[program.pid]

    def inline_output_changed(self, program, plan, index):
        if len(plan.outputs) == 1 and index == 0:
            return self.apply_inline_outputs(program, plan)
        return True

    def remove_inline_output(self, program, plan, index):
        before = list(plan.outputs)
        plan.remove(index)
        if len(plan.outputs) == 1 and not self.apply_inline_outputs(program, plan):
            plan.outputs = before

    def apply_inline_outputs(self, program, plan):
        try:
            if self.pending_share:
                raise RuntimeError('Wait for the current audio bridge to finish starting.')
            own_bridge = bool(self.shared_route and self.shared_route[0] == program.pid)
            if len(plan.outputs) == 1:
                if plan.outputs[0] is None:
                    raise ValueError('Choose a device for Output A.')
                if plan.outputs[0] and plan.outputs[0] not in {d.id for d in self.audio.outputs}:
                    raise ValueError('Output A disconnected. Choose a connected device.')
                desired = plan.outputs[0]
                if own_bridge:
                    self.stop_sharing()
                self.audio.route(program.pid, desired)
                plan.outputs = [desired]
                plan.note = 'Output A applied.'
            else:
                default = AudioUtilities.GetSpeakers()
                targets = plan.resolve(default.id if default else '')
                # Reject invalid drafts before stopping the existing stream.
                self.validate_program_outputs(program, targets)
                if own_bridge:
                    self.stop_sharing()
                self.start_program_bridge(program, targets)
                plan.note = 'Starting playback on the selected outputs…'
            self.status.set(plan.note)
            return True
        except Exception as exc:
            logging.exception('Could not apply inline outputs')
            plan.note = str(exc)
            self.status.set(plan.note)
            return False

    def stop_inline_outputs(self, program, plan):
        try:
            current = self.shared_route or self.pending_share
            if not current or current[0] != program.pid:
                plan.note = 'This app is not currently sharing audio.'
                return
            self.stop_sharing()
            plan.note = 'Sharing stopped; original output restored. Apply Outputs to share again.'
            self.status.set(plan.note)
        except Exception as exc:
            plan.note = str(exc)
            self.status.set(plan.note)

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
                bridged = self.shared_route or self.pending_share
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
        ttk.Label(frame, text='Add delay to the faster output until you hear both together. Output A plays directly and cannot be delayed. Put Bluetooth on A and adjust the faster copies on B/C. Settings are remembered per device.\n\nExample: if Bluetooth is about 150 ms late, add 150 ms to your headset and leave Bluetooth at 0 ms. Presets are starting points; the best value depends on your devices.',
                  foreground=MUTED, wraplength=880, justify='left').pack(anchor='w', padx=14, pady=(0, 12))
        running = self.bridge.thread and self.bridge.thread.is_alive()
        candidates = [d for d in self.audio.outputs if not running or d.id in self.bridge_outputs]
        candidates.sort(key=lambda d: d.FriendlyName.lower())
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
            if (self.shared_route or self.pending_share) and device.id == self.primary_output_id:
                ttk.Label(card, text='Output A ? direct playback ? no added delay', style='Card.TLabel', foreground=MUTED).pack(anchor='w', pady=(8, 0))
            else:
                controls = DelayControls(card, self.delay_variable(device.id), self.status.set)
                controls.pack(fill='x', pady=(6, 0))

    def select_alignment_outputs(self, outputs):
        self.calibration_selection = tuple(outputs)
        self.build_sync_device_cards()

    def start_alignment_test(self, outputs, options):
        def start():
            if self.pending_share:
                raise RuntimeError('Wait for the current bridge to finish starting.')
            if self.shared_route:
                raise RuntimeError('Stop sharing and pause the program before playing the alignment test. Then apply outputs again and fine-tune B/C while listening to the program.')
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

    def validate_program_outputs(self, program, targets):
        from process_capture import ensure_supported
        ensure_supported()
        if not program.pid:
            raise ValueError('Choose an application to share.')
        if not self.audio.routing:
            raise RuntimeError('Per-program routing is unavailable on this Windows version.')
        connected = {d.id for d in self.audio.outputs}
        if len(targets) < 2 or any(target not in connected for target in targets):
            raise ValueError('Choose at least two connected output devices.')
        if len(set(targets)) != len(targets):
            raise ValueError('Choose different devices for each output.')

    def start_program_bridge(self, program, targets):
        if self.pending_share or self.shared_route or (self.bridge.thread and self.bridge.thread.is_alive()):
            raise RuntimeError('Stop the current audio bridge before starting another.')
        self.validate_program_outputs(program, targets)
        old_route = self.audio.routing.snapshot(program.pid)
        self.pending_share = (program.pid, old_route, targets[0])
        self.bridge_outputs = tuple(targets)
        self.bridge_name = program.name
        try:
            # Output A is native playback: never write a second copy to it.
            self.bridge.start_process(program.pid, targets[1:])
        except Exception:
            self.pending_share = None
            self.bridge_outputs = ()
            raise
        self.primary_output_id = targets[0]
        plans = self.__dict__.get('output_plans')
        if plans is not None:
            plan = plans.setdefault(program.pid, OutputPlan())
            plan.outputs = list(targets)
            plan.note = 'Starting playback on the selected outputs?'
        self.status.set(f'Starting audio for {program.name} on {len(targets)} output devices?')

    def stop_sharing(self):
        prior = self.shared_route or self.pending_share
        self.pending_share = None
        # Restore the program first so stopping the bridge does not strand its audio.
        if self.shared_route:
            pid, old_route = self.shared_route
            self.audio.route(pid, old_route)
            self.shared_route = None
        self.bridge.stop()
        self.bridge_outputs = ()
        self.primary_output_id = ''
        plans = self.__dict__.get('output_plans', {})
        if prior and prior[0] in plans:
            plan = plans[prior[0]]
            if len(plan.outputs) == 1:
                plan.outputs = [prior[1][1]]
                plan.note = 'Sharing stopped; original output restored.'
            else:
                plan.note = 'Sharing stopped; original output restored. Apply Outputs to share again.'
        controls = self.__dict__.get('calibration_controls')
        if controls:
            controls.set_running(False)
            self.calibration_status.set('Test stopped. Your delay settings are kept.')
        self.status.set("Audio bridge stopped; original program output restored.")

    def stop_and_refresh(self):
        self.stop_sharing()
        self._refresh()

    def check_shared_playback(self):
        if not self.shared_route:
            return
        now = time.monotonic()
        if now < self.__dict__.get('share_check_at', 0):
            return
        self.share_check_at = now + 2
        pid = self.shared_route[0]
        outputs = AudioUtilities.GetAllDevices(data_flow=0, device_state=DEVICE_STATE.ACTIVE.value)
        connected = {device.id for device in outputs}
        if not psutil.pid_exists(pid) or self.primary_output_id not in connected:
            self.bridge.events.put(('error', 'Sharing stopped: the application closed or Output A disconnected.'))

    def poll(self):
        try:
            self.check_shared_playback()
        except Exception:
            logging.exception('Could not check the primary output')
        try:
            while True:
                kind, text = self.bridge.events.get_nowait()
                if kind == "ready" and self.pending_share:
                    pid, old_route, primary = self.pending_share
                    self.pending_share = None
                    try:
                        self.audio.route(pid, primary)
                        self.shared_route = (pid, old_route)
                        plans = self.__dict__.get('output_plans', {})
                        if pid in plans:
                            plans[pid].note = 'Playing on the selected outputs.'
                        text = f"{self.bridge_name} is playing on {len(self.bridge_outputs)} output device(s). Restart playback if the app hasn't switched yet."
                        self._refresh()
                    except Exception as exc:
                        try:
                            self.stop_sharing()
                        except Exception as stop_error:
                            text = f"{exc}; stop failed: {stop_error}"
                            self.status.set(text)
                            continue
                        text = str(exc)
                if kind == "error":
                    failed = self.pending_share or self.shared_route
                    self.pending_share = None
                    try:
                        self.stop_sharing()
                    except Exception as exc:
                        text += " Restore/stop failed: " + str(exc)
                    plans = self.__dict__.get('output_plans', {})
                    if failed and failed[0] in plans:
                        plans[failed[0]].note = text
                    try:
                        self._refresh()
                    except Exception as exc:
                        text += ' Refresh failed: ' + str(exc)
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
            self.stop_sharing()
        except Exception as exc:
            messagebox.showerror("Unable to stop sharing", str(exc), parent=self)
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
