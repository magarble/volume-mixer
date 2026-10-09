import json
from pathlib import Path
from delay import validate_delay


class DelayPreferences:
    def __init__(self, path):
        self.path = Path(path)
        self.values = {}
        self.dirty = False
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            for device, value in data.get('output_delays', {}).items():
                if isinstance(device, str):
                    try:
                        self.values[device] = validate_delay(value)
                    except (TypeError, ValueError):
                        pass
        except (OSError, ValueError, TypeError, AttributeError):
            pass

    def set(self, device, value):
        value = validate_delay(value)
        if self.values.get(device, 0) != value:
            self.values[device] = value
            self.dirty = True

    def save(self):
        if not self.dirty:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps({'version': 1, 'output_delays': self.values}, indent=2), encoding='utf-8')
        temporary.replace(self.path)
        self.dirty = False
