# PyInstaller spec — onedir, windowed Windows build.
# Build:  pyinstaller VoiceFlow.spec --noconfirm
#
# Native libs (PortAudio via sounddevice, libsndfile via soundfile) are NOT plain
# Python imports, so they must be collected explicitly or the exe crashes at
# runtime on a machine without them. Always test the result on a Python-free box.
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files

binaries = collect_dynamic_libs("soundfile") + collect_dynamic_libs("sounddevice")
datas = (
    collect_data_files("_sounddevice_data")
    + collect_data_files("soundfile")
    + [("assets/icon.ico", "assets")]
)
hiddenimports = ["pystray._win32"]

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VoiceFlow",
    console=False,
    icon="assets/icon.ico",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="VoiceFlow",
)
