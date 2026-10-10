"""Per-program output drafts and their inline controls."""
from dataclasses import dataclass, field
import tkinter as tk
from tkinter import ttk


def output_letter(index):
    result = ''
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


@dataclass
class OutputPlan:
    outputs: list = field(default_factory=lambda: [''])
    note: str = ''

    def add(self):
        self.outputs.append(None)
        self.note = 'Choose the extra output, then apply your outputs.'

    def remove(self, index):
        if not 0 < index < len(self.outputs):
            raise ValueError('Output A cannot be removed.')
        self.outputs.pop(index)
        self.note = 'Changes are not applied yet. Apply Outputs to update playback.'

    def resolve(self, default_id):
        if not self.outputs or any(value is None for value in self.outputs):
            raise ValueError('Choose a device for every output row.')
        targets = tuple(default_id if value == '' else value for value in self.outputs)
        if not all(targets):
            raise ValueError('Windows has no default output. Choose a specific device for Output A.')
        if len(set(targets)) != len(targets):
            raise ValueError('Choose different devices for each output. Windows default may be one of the selected devices.')
        return targets


class OutputRows(ttk.Frame):
    def __init__(self, parent, plan, devices, render_input, on_change, on_remove,
                 on_apply, on_stop, on_delay, active, pending, editable, playing,
                 render_volume=None):
        super().__init__(parent, style='Card.TFrame')
        self.plan, self.devices = plan, list(devices)
        self.render_input = render_input
        self.on_change, self.on_remove = on_change, on_remove
        self.on_apply, self.on_stop, self.on_delay = on_apply, on_stop, on_delay
        self.active, self.pending, self.editable = active, pending, editable
        self.playing = playing
        self.render_volume = render_volume
        self.combos = []
        self.remove_buttons = []
        self.render()

    def render(self):
        for child in self.winfo_children():
            child.destroy()
        self.combos, self.remove_buttons = [], []
        disabled = not self.editable or self.pending()
        for index, chosen in enumerate(self.plan.outputs):
            row = ttk.Frame(self, style='Card.TFrame')
            row.pack(fill='x', pady=(0, 8))
            ttk.Label(row, text=f'Output {output_letter(index)}', style='Card.TLabel', width=9).pack(side='left', padx=(0, 8))
            names = (['Windows default'] if index == 0 else []) + [d.FriendlyName for d in self.devices]
            ids = ([''] if index == 0 else []) + [d.id for d in self.devices]
            combo = ttk.Combobox(row, values=names, state='disabled' if disabled else 'readonly', width=31)
            combo.pack(side='left', padx=(0, 16))
            if chosen in ids:
                combo.current(ids.index(chosen))
            else:
                combo.set('Choose output device…' if chosen is None else 'Disconnected — choose another device')
            def selected(event, number=index, selector=combo, endpoints=ids):
                if selector.current() < 0:
                    return
                before = self.plan.outputs[number]
                self.plan.outputs[number] = endpoints[selector.current()]
                if len(self.plan.outputs) > 1:
                    self.plan.note = 'Changes are not applied yet. Apply Outputs to update playback.'
                if not self.on_change(number):
                    self.plan.outputs[number] = before
                self.render()
            combo.bind('<<ComboboxSelected>>', selected)
            self.combos.append(combo)
            if index == 0:
                self.render_input(row)
            else:
                remove = ttk.Button(row, text='Remove', state='disabled' if disabled else 'normal',
                                    command=lambda number=index: self.remove(number))
                remove.pack(side='left')
                self.remove_buttons.append(remove)
            if self.render_volume:
                self.render_volume(self, chosen)
        if self.render_volume:
            ttk.Label(self, text='Device volume affects all audio on the selected device.',
                      style='Card.TLabel', foreground='#9ba8bf', wraplength=850).pack(anchor='w', pady=(0, 8))
        actions = ttk.Frame(self, style='Card.TFrame')
        actions.pack(fill='x', pady=(4, 0))
        self.add_button = ttk.Button(actions, text='Add Extra Output', state='disabled' if disabled else 'normal', command=self.add)
        self.add_button.pack(side='left')
        if len(self.plan.outputs) > 1:
            self.apply_button = ttk.Button(actions, text='Apply Outputs', state='disabled' if disabled else 'normal', command=self.apply)
            self.apply_button.pack(side='left', padx=10)
        if self.active() or self.pending():
            ttk.Button(actions, text='Stop sharing', command=self.stop).pack(side='left', padx=(0, 10))
            ttk.Button(actions, text='Adjust output delays', command=self.on_delay).pack(side='left')
        if len(self.plan.outputs) > 1:
            ttk.Label(self, text='Output A plays directly. Use Bluetooth here; delay the faster copies on B/C in Output sync.',
                      style='Card.TLabel', foreground='#9ba8bf', wraplength=850).pack(anchor='w', pady=(10, 0))
        if self.plan.note:
            ttk.Label(self, text=self.plan.note, style='Card.TLabel', foreground='#9ba8bf', wraplength=850).pack(anchor='w', pady=(10, 0))
        if self.active():
            names = {d.id: d.FriendlyName for d in self.devices}
            ttk.Label(self, text='Playing on: ' + ', '.join(names.get(i, 'Disconnected output') for i in self.playing()),
                      style='Card.TLabel', foreground='#79b8ff', wraplength=850).pack(anchor='w', pady=(10, 0))

    def add(self):
        self.plan.add()
        self.on_change(None)
        self.render()

    def remove(self, index):
        self.on_remove(index)
        self.render()

    def apply(self):
        self.on_apply()
        self.render()

    def stop(self):
        self.on_stop()
        self.render()
