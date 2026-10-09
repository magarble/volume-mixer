import tkinter as tk
from tkinter import ttk
from delay import MAX_DELAY_MS, DELAY_PRESETS, validate_delay


class DelayControls(ttk.Frame):
    def __init__(self, parent, variable, on_error):
        super().__init__(parent, style='Card.TFrame')
        self.variable = variable
        self.on_error = on_error
        self.updating = False
        self.slider_value = tk.DoubleVar(value=variable.get())
        self.entry_value = tk.StringVar(value=str(variable.get()))
        line = ttk.Frame(self, style='Card.TFrame')
        line.pack(fill='x', pady=(6, 8))
        ttk.Label(line, text='Added delay', style='Card.TLabel').pack(side='left', padx=(0, 12))
        self.scale = ttk.Scale(line, from_=0, to=MAX_DELAY_MS, variable=self.slider_value, command=self.slide)
        self.scale.pack(side='left', fill='x', expand=True)
        self.entry = ttk.Spinbox(line, from_=0, to=MAX_DELAY_MS, increment=1,
                                 textvariable=self.entry_value, width=6, command=self.commit)
        self.entry.pack(side='left', padx=(12, 4))
        self.entry.bind('<Return>', lambda event: self.commit())
        self.entry.bind('<FocusOut>', lambda event: self.commit())
        ttk.Label(line, text='ms', style='Card.TLabel').pack(side='left')
        buttons = ttk.Frame(self, style='Card.TFrame')
        buttons.pack(fill='x')
        ttk.Button(buttons, text='−5 ms', command=lambda: self.adjust(-5)).pack(side='left')
        ttk.Button(buttons, text='+5 ms', command=lambda: self.adjust(5)).pack(side='left', padx=6)
        ttk.Button(buttons, text='−1 ms', command=lambda: self.adjust(-1)).pack(side='left', padx=(0, 6))
        ttk.Button(buttons, text='+1 ms', command=lambda: self.adjust(1)).pack(side='left', padx=(0, 6))
        ttk.Button(buttons, text='Reset', command=lambda: self.variable.set(0)).pack(side='left', padx=(0, 14))
        self.preset = ttk.Combobox(buttons, values=list(DELAY_PRESETS), state='readonly', width=24)
        self.preset.pack(side='left')
        self.preset.set('Choose a starting preset')
        self.preset.bind('<<ComboboxSelected>>', lambda event: self.variable.set(DELAY_PRESETS[self.preset.get()]))
        self.trace = variable.trace_add('write', self.sync)
        self.sync()

    def sync(self, *args):
        self.updating = True
        try:
            value = self.variable.get()
            self.slider_value.set(value)
            self.entry_value.set(str(value))
            self.preset.set(next((name for name, delay in DELAY_PRESETS.items() if delay == value), 'Custom delay'))
        finally:
            self.updating = False

    def slide(self, raw):
        if not self.updating:
            self.variable.set(validate_delay(raw))

    def commit(self):
        try:
            self.variable.set(validate_delay(self.entry_value.get()))
        except (ValueError, TypeError):
            self.entry_value.set(str(self.variable.get()))
            self.on_error(f'Enter a delay from 0 to {MAX_DELAY_MS} ms.')

    def adjust(self, amount):
        self.variable.set(max(0, min(MAX_DELAY_MS, self.variable.get() + amount)))

    def destroy(self):
        self.variable.trace_remove('write', self.trace)
        super().destroy()
