"""Generate PyInstaller's Windows executable metadata from the release version."""
from pathlib import Path

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable,
    VarFileInfo, VarStruct, VSVersionInfo,
)
from version import __version__


if __name__ == '__main__':
    version = tuple(map(int, __version__.split('.'))) + (0,)
    info = VSVersionInfo(
        ffi=FixedFileInfo(filevers=version, prodvers=version, fileType=1),
        kids=[
            StringFileInfo([StringTable('040904B0', [
                StringStruct('ProductName', 'Volume Mixer'),
                StringStruct('FileDescription', 'Volume Mixer'),
                StringStruct('FileVersion', __version__),
                StringStruct('ProductVersion', __version__),
                StringStruct('OriginalFilename', 'VolumeMixer.exe'),
            ])]),
            VarFileInfo([VarStruct('Translation', [1033, 1200])]),
        ],
    )
    target = Path(__file__).parent / 'build' / 'windows-version.txt'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(str(info), encoding='utf-8')
