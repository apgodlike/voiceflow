"""Clipboard-first paste — pyperclip always runs before pyautogui."""
import argparse
import logging
import sys
import time

import pyautogui
import pyperclip

logger = logging.getLogger(__name__)

_PASTE_KEY = "ctrl" if sys.platform != "darwin" else "command"

# Time to let the target app read the clipboard before we restore the prior
# contents (only used when preserve_clipboard is on).
RESTORE_DELAY_SEC = 0.3


def paste(text: str, *, preserve_clipboard: bool = False,
          restore_delay: float = RESTORE_DELAY_SEC) -> bool:
    """Copy ``text`` then simulate paste. With ``preserve_clipboard`` the
    caller's previous clipboard is restored after a short delay — but only on
    a successful paste, so a failed paste still leaves the text recoverable."""
    prior = None
    if preserve_clipboard:
        try:
            prior = pyperclip.paste()
        except Exception:
            prior = None  # non-text/empty clipboard — nothing to restore

    pyperclip.copy(text)
    try:
        pyautogui.hotkey(_PASTE_KEY, "v")
    except Exception as exc:
        logger.warning("Paste simulation failed (text still in clipboard): %s", exc)
        return False

    if preserve_clipboard and prior is not None:
        time.sleep(restore_delay)
        try:
            pyperclip.copy(prior)
        except Exception:
            pass
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("text")
    args = parser.parse_args()
    print("Sleeping 3 s — focus a text field...")
    time.sleep(3)
    ok = paste(args.text)
    print("Paste simulated." if ok else "Paste failed — text in clipboard.")
