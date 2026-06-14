# PyInstaller spec — onedir, windowed Windows build.
# Build:  pyinstaller VoiceFlow.spec --noconfirm
#
# Native libs (PortAudio via sounddevice, libsndfile via soundfile) are NOT plain
# Python imports, so they must be collected explicitly or the exe crashes at
# runtime on a machine without them. Always test the result on a Python-free box.
#
# Local Whisper backend (optional): faster-whisper, ctranslate2, av, tokenizers,
# huggingface_hub are bundled so users can toggle to local transcription without
# a separate install. ~100-150 MB overhead. Model weights download on first use.
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files, collect_all

binaries = collect_dynamic_libs("soundfile") + collect_dynamic_libs("sounddevice")
datas = (
    collect_data_files("_sounddevice_data")
    + collect_data_files("soundfile")
    + [("assets/icon.ico", "assets")]
)
hiddenimports = ["pystray._win32"]

# faster-whisper local backend — collect all four dependency layers
for _pkg in ("faster_whisper", "ctranslate2", "av", "tokenizers", "huggingface_hub"):
    _d, _b, _h = collect_all(_pkg)
    datas += _d
    binaries += _b
    hiddenimports += _h

# Parakeet local engine (onnx-asr + onnxruntime) — ~42 MB. Model weights download
# on first use, like the Whisper models.
for _pkg in ("onnx_asr", "onnxruntime"):
    _d, _b, _h = collect_all(_pkg)
    datas += _d
    binaries += _b
    hiddenimports += _h

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
