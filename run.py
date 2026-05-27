"""Frozen-app entry point — keeps package imports working under PyInstaller."""
from voiceflow.main import main

if __name__ == "__main__":
    main()
