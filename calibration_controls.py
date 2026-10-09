import tkinter as tk
from tkinter import ttk
from calibration import PATTERNS


class CalibrationControls(ttk.Frame):
    def __init__(self, parent, devices, selected, pattern, level, audition, running, status,
                 on_start, on_stop, on_update, on_selection):
        super().__init__(parent, style='Card.TFrame', padding=16)
        self.devices = list(devices)
        self.pattern = pattern
        self.level = level
        self.audition = audition
        self.on_update = on_update
        self.on_selection = on_selection
        ttk.Label(self, text='Listen and line up', style='Card.TLabel', font=('Segoe UI', 15, 'bold')).pack(anchor='w')
        ttk.Label(self, text='Choose two outputs, play the clicks, and add delay to the faster device until the double tap sounds like one. Listen from your usual position; pause other audio for a clearer comparison.',
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
        ttk.Label(settings, text='Test volume', style='Card.TLabel').pack(side='left', padx=(20, 10))
        ttk.Scale(settings, from_=0, to=100, variable=level, command=lambda raw: self.update()).pack(side='left', fill='x', expand=True)
        modes = ttk.Frame(self, style='Card.TFrame')
        modes.pack(anchor='w', pady=(0, 12))
        for text, value in (('Both together', 'both'), ('A only', 'a'), ('B only', 'b')):
            ttk.Radiobutton(modes, text=text, variable=audition, value=value, command=self.update).pack(side='left', padx=(0, 18))
        transport = ttk.Frame(self, style='Card.TFrame')
        transport.pack(fill='x')
        self.start = ttk.Button(transport, text='Play alignment clicks', command=lambda: on_start(self.selected(), self.options()))
        self.start.pack(side='left')
        self.stop = ttk.Button(transport, text='Stop test / resume audio', command=on_stop)
        self.stop.pack(side='left', padx=12)
        ttk.Label(self, textvariable=status, style='Card.TLabel', foreground='#79b8ff', wraplength=850).pack(anchor='w', pady=(10, 0))
        ttk.Label(self, text='Clicks repeat every 2 seconds. Use −5/+5 ms to get close, then −1/+1 ms to fine-tune. A single perceived click is an approximate ear match, not a measured delay.',
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
        return {'pattern': PATTERNS[self.pattern.get()], 'level': float(self.level.get()), 'audition': self.audition.get()}

    def update(self):
        self.on_update(self.selected(), self.options())

    def set_running(self, running):
        self.start.configure(state='disabled' if running else 'normal')
        self.stop.configure(state='normal' if running else 'disabled')
        for combo in (self.a, self.b):
            combo.configure(state='disabled' if running else 'readonly')
