import tkinter as tk
from tkinter import ttk
from calibration import PATTERNS, TEMPO_PRESETS, validate_tempo


class CalibrationControls(ttk.Frame):
    def __init__(self, parent, devices, selected, pattern, level, audition, tempo, running, status,
                 on_start, on_stop, on_update, on_selection):
        super().__init__(parent, style='Card.TFrame', padding=16)
        self.devices = list(devices)
        self.pattern = pattern
        self.level = level
        self.audition = audition
        self.tempo = tempo
        self.status = status
        self.last_tempo = validate_tempo(tempo.get())
        self.on_update = on_update
        self.on_selection = on_selection
        ttk.Label(self, text='Listen and line up', style='Card.TLabel', font=('Segoe UI', 15, 'bold')).pack(anchor='w')
        ttk.Label(self, text='Choose two outputs and a sound, then delay the faster device until the two hits sound like one. Listen from your usual position; pause other audio for a clearer comparison.',
                  style='Card.TLabel', foreground='#9ba8bf', wraplength=850).pack(anchor='w', pady=(8, 12))
        outputs = ttk.Frame(self, style='Card.TFrame')
        outputs.pack(fill='x')
        self.a = self.output_field(outputs, 'Output A — adjust the faster one', selected[0] if selected else '', 0)
        self.b = self.output_field(outputs, 'Output B — reference', selected[1] if len(selected) > 1 else '', 1)
        settings = ttk.Frame(self, style='Card.TFrame')
        settings.pack(fill='x', pady=12)
        ttk.Label(settings, text='Sound', style='Card.TLabel').pack(side='left', padx=(0, 8))
        sound = ttk.Combobox(settings, values=list(PATTERNS), textvariable=pattern, state='readonly', width=28)
        sound.pack(side='left')
        sound.bind('<<ComboboxSelected>>', lambda event: self.update())
        self.sound = sound
        ttk.Label(settings, text='Test volume', style='Card.TLabel').pack(side='left', padx=(20, 10))
        ttk.Scale(settings, from_=0, to=100, variable=level, command=lambda raw: self.update()).pack(side='left', fill='x', expand=True)
        pace = ttk.Frame(self, style='Card.TFrame')
        pace.pack(fill='x', pady=(0, 12))
        ttk.Label(pace, text='Tempo', style='Card.TLabel').pack(side='left', padx=(0, 8))
        self.tempo_entry = ttk.Spinbox(pace, from_=30, to=240, increment=5, textvariable=tempo, width=6, command=self.update)
        self.tempo_entry.pack(side='left')
        self.tempo_entry.bind('<Return>', lambda event: self.update())
        self.tempo_entry.bind('<FocusOut>', lambda event: self.update())
        ttk.Label(pace, text='BPM', style='Card.TLabel').pack(side='left', padx=(4, 12))
        for value in TEMPO_PRESETS:
            ttk.Button(pace, text=str(value), padding=(8, 5), command=lambda bpm=value: self.set_tempo(bpm)).pack(side='left', padx=(0, 4))
        modes = ttk.Frame(self, style='Card.TFrame')
        modes.pack(anchor='w', pady=(0, 12))
        for text, value in (('Both together', 'both'), ('A only', 'a'), ('B only', 'b')):
            ttk.Radiobutton(modes, text=text, variable=audition, value=value, command=self.update).pack(side='left', padx=(0, 18))
        transport = ttk.Frame(self, style='Card.TFrame')
        transport.pack(fill='x')
        self.start = ttk.Button(transport, text='Play alignment sound', command=lambda: on_start(self.selected(), self.options()))
        self.start.pack(side='left')
        self.stop = ttk.Button(transport, text='Stop test / resume audio', command=on_stop)
        self.stop.pack(side='left', padx=12)
        ttk.Label(self, textvariable=status, style='Card.TLabel', foreground='#79b8ff', wraplength=850).pack(anchor='w', pady=(10, 0))
        ttk.Label(self, text='Change sound and tempo live. Use slower tempos for large delays: a whole-beat offset can sound aligned. Short clicks or woodblock give a clear attack; bell and bass are gentler alternatives. Fine-tune with −1/+1 ms.',
                  style='Card.TLabel', foreground='#9ba8bf', wraplength=850).pack(anchor='w', pady=(8, 0))
        self.set_running(running)

    def output_field(self, parent, title, chosen, column):
        box = ttk.Frame(parent, style='Card.TFrame')
        box.grid(row=0, column=column, sticky='ew', padx=(0, 16) if column == 0 else 0)
        parent.columnconfigure(column, weight=1)
        ttk.Label(box, text=title, style='Card.TLabel').pack(anchor='w', pady=(0, 4))
        combo = ttk.Combobox(box, values=[d.FriendlyName for d in self.devices], state='readonly', width=30)
        combo.pack(fill='x')
        index = next((i for i, d in enumerate(self.devices) if d.id == chosen), column if len(self.devices) > column else -1)
        if index >= 0:
            combo.current(index)
        combo.bind('<<ComboboxSelected>>', lambda event: self.on_selection(self.selected()))
        return combo

    def selected(self):
        return tuple(self.devices[c.current()].id if c.current() >= 0 else '' for c in (self.a, self.b))

    def options(self):
        try:
            self.last_tempo = validate_tempo(self.tempo.get())
        except (ValueError, TypeError):
            self.tempo.set(f'{self.last_tempo:g}')
            self.status.set('Enter a tempo between 30 and 240 BPM.')
        return {'pattern': PATTERNS[self.pattern.get()], 'level': float(self.level.get()), 'audition': self.audition.get(), 'bpm': self.last_tempo}

    def set_tempo(self, bpm):
        self.tempo.set(str(bpm))
        self.update()

    def update(self):
        self.on_update(self.selected(), self.options())

    def set_running(self, running):
        self.start.configure(state='disabled' if running else 'normal')
        self.stop.configure(state='normal' if running else 'disabled')
        for combo in (self.a, self.b):
            combo.configure(state='disabled' if running else 'readonly')
