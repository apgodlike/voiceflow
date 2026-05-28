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


def _type_text(text: str) -> bool:
    """Type text character-by-character via pynput. Supports Unicode.

    Used when the target app blocks Ctrl+V clipboard paste (e.g. some terminals
    or remote-desktop sessions). Does not touch the clipboard at all.
    """
    try:
        from pynput.keyboard import Controller  # already a dep via hotkey.py
        Controller().type(text)
        return True
    except Exception as exc:
        logger.warning("Type simulation failed: %s", exc)
        return False


def paste(text: str, *, preserve_clipboard: bool = False,
          paste_mode: str = "clipboard",
          restore_delay: float = RESTORE_DELAY_SEC) -> bool:
    """Deliver ``text`` to the focused window.

    ``paste_mode="clipboard"`` (default) copies to clipboard then Ctrl+V.
    ``paste_mode="type"`` types characters one by one (for apps blocking Ctrl+V);
    in this mode ``preserve_clipboard`` is ignored since the clipboard is untouched.

    On clipboard mode failure the text stays in the clipboard so it is recoverable.
    """
    if paste_mode == "type":
        return _type_text(text)

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
