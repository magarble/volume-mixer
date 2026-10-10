"""Preserve installed dependency licence texts for source and binary releases."""
import importlib.metadata as metadata
import json
from pathlib import Path
import pyexpat
import shutil
import ssl
import sys
import tkinter
import zlib

ROOT = Path(__file__).resolve().parent
PACKAGES = ('pycaw', 'SoundCard', 'numpy', 'comtypes', 'psutil', 'cffi',
            'pycparser', 'setuptools', 'pyinstaller')


def collect():
    native = json.loads((ROOT / 'licenses/native/sources.json').read_text(encoding='utf-8'))
    actual = {
        'python': sys.version.split()[0],
        'openssl': ssl.OPENSSL_VERSION.split()[1],
        'tcl': tkinter.Tcl().eval('info patchlevel'),
        'expat': pyexpat.EXPAT_VERSION.removeprefix('expat_'),
        'zlib': zlib.ZLIB_RUNTIME_VERSION,
    }
    if actual != native['runtime']:
        raise RuntimeError('Native runtime changed. Audit and update licenses/native before packaging: ' + repr(actual))
    inventory = []
    for name in PACKAGES:
        distribution = metadata.distribution(name)
        copied = []
        for entry in distribution.files or ():
            if not any(word in entry.name.lower() for word in ('license', 'copying', 'notice')):
                continue
            source = Path(distribution.locate_file(entry))
            if not source.is_file():
                continue
            # Retain nested NumPy and setuptools vendor notices, without local paths.
            relative = Path(*entry.parts)
            target = ROOT / 'licenses/packages' / name.lower() / relative
            if '..' in relative.parts or relative.is_absolute():
                raise ValueError('Unsafe licence path: ' + str(relative))
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            copied.append(target.relative_to(ROOT).as_posix())
        if not copied:
            raise RuntimeError('No licence text found for ' + name)
        info = distribution.metadata
        inventory.append({'name': name, 'version': distribution.version,
                          'license': info.get('License-Expression') or info.get('License'),
                          'files': sorted(copied)})
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    shutil.copyfile(python_license, ROOT / 'licenses/native/python.txt')
    (ROOT / 'licenses/inventory.json').write_text(
        json.dumps({'runtime': actual, 'packages': inventory}, indent=2) + '\n', encoding='utf-8')
    print(f'Collected notices for {len(inventory)} distributions and the audited native runtime.')


if __name__ == '__main__':
    collect()
