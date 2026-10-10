# Third-party notices

Volume Mixer's own code is licensed under the MIT licence in `LICENSE`.
Bundled third-party components retain their respective licences and copyright
notices. The application licence does not replace those terms.

The `licenses/` folder accompanies both the source repository and Windows ZIP.
It contains verbatim notices collected from the installed distributions and
upstream runtime sources. `licenses/inventory.json` records the package versions
and notice paths; `licenses/native/sources.json` records native versions and sources.

| Component | Notices |
| --- | --- |
| Pycaw, SoundCard, NumPy, comtypes, psutil, CFFI, pycparser | `licenses/packages/` |
| NumPy native OpenBLAS, LAPACK, and GCC runtime with its exception | NumPy's full wheel licence and nested notices in `licenses/packages/numpy/` |
| setuptools and its vendored components included by packaging hooks | `licenses/packages/setuptools/` |
| CPython and its bundled components, including libffi and Microsoft runtime conditions | `licenses/native/python.txt` |
| OpenSSL 3.0.18 | `licenses/native/openssl.txt` |
| Tcl/Tk 8.6.15 | `licenses/native/tcl.txt`, `licenses/native/tk.txt` |
| Expat 2.7.3 | `licenses/native/expat.txt` |
| zlib and zlib-ng | `licenses/native/zlib.txt`, `licenses/native/zlib-ng.txt` |

The Python Windows distribution includes Microsoft runtime code. Its additional
distribution conditions are retained in `licenses/native/python.txt`. The mixer
and its bundled Windows runtime are distributed for Windows only.

PyInstaller is the build tool. Its licence includes a bootloader exception that
permits distributing the generated application under its own licence, subject
to the dependency licences. Its original text is retained under
`licenses/packages/pyinstaller/` for reference.

## API references and acknowledgements

The Windows audio-policy interface layout was checked against
[EarTrumpet's interface definitions](https://github.com/File-New-Project/EarTrumpet/tree/master/EarTrumpet/Interop/MMDeviceAPI).
The process-loopback implementation uses the system COM APIs demonstrated by
[Microsoft's application-loopback sample](https://github.com/microsoft/Windows-classic-samples/tree/main/Samples/ApplicationLoopback).
Neither project's executable or library is bundled. Microsoft's sample licence
is retained in `licenses/native/microsoft-sample.txt` as an acknowledgement.

## Updating a release

`collect_licenses.py` copies the installed package notices before each build and
rejects an unaudited native runtime. When changing dependency or Python versions,
review upstream licence changes, update the native notices where necessary, and
check the resulting executable's DLLs and PyInstaller analysis for new components.
Keep all notice files with redistributed copies of the Windows package.
