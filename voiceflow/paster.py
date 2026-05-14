"""Clipboard-first paste — pyperclip always runs before pyautogui."""
import argparse
import logging
import sys
import time

import pyautogui
import pyperclip

logger = logging.getLogger(__name__)

_PASTE_KEY = "ctrl" if sys.platform != "darwin" else "command"


def paste(text: str) -> bool:
    pyperclip.copy(text)
    try:
        pyautogui.hotkey(_PASTE_KEY, "v")
        return True
    except Exception as exc:
        logger.warning("Paste simulation failed (text still in clipboard): %s", exc)
        return False


def copy_only(text: str) -> None:
    pyperclip.copy(text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("text")
    args = parser.parse_args()
    print("Sleeping 3 s — focus a text field...")
    time.sleep(3)
    ok = paste(args.text)
    print("Paste simulated." if ok else "Paste failed — text in clipboard.")
