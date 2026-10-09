import tkinter as tk
from tkinter import ttk


class DeviceChoices(ttk.Frame):
    """A scrollable checkbox list that keeps choices keyed by endpoint ID."""
    def __init__(self, parent, height=160):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, height=height, bg='#1b2130', highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.inner = ttk.Frame(self.canvas, style='Card.TFrame', padding=8)
        self.window = self.canvas.create_window((0, 0), window=self.inner, anchor='nw')
        self.inner.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfigure(self.window, width=e.width))
        self.variables = {}

    def set_devices(self, devices, selected=None):
        chosen = set(self.selected_ids() if selected is None else selected)
        for child in self.inner.winfo_children():
            child.destroy()
        self.variables = {}
        for device in devices:
            variable = tk.BooleanVar(value=device.id in chosen)
            self.variables[device.id] = variable
            ttk.Checkbutton(self.inner, text=device.FriendlyName, variable=variable).pack(anchor='w', pady=3)

    def selected_ids(self):
        return tuple(key for key, value in self.variables.items() if value.get())
