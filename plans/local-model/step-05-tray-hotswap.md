# Step 05 — Tray Hot-Swap Toggle

**Phase:** P4 (parallel with step-06)
**Depends on:** step-04

## Context

Working directory: `C:\dev\projects\voice-typing\voiceflow`
Branch: `feature/local-model`
Files to edit: `voiceflow/tray.py` AND `voiceflow/main.py`

Adds a tray menu item that shows the current backend and toggles it on click.
Label format: `"Backend: openai → switch"` or `"Backend: local (base) → switch"`

`tray.py` gets:
- new `on_backend_toggle` callback parameter
- new `_backend` state
- `set_backend(backend)` public method
- new menu item in `_build_menu`

`main.py` gets:
- `on_backend_toggle=self._toggle_backend` passed to `Tray(...)`
- `App._toggle_backend()` method
- `self._tray.set_backend(...)` call after Tray init

## Task

### Read files first

Read both files in full before editing:
- `C:\dev\projects\voice-typing\voiceflow\voiceflow\tray.py`
- `C:\dev\projects\voice-typing\voiceflow\voiceflow\main.py`

---

### tray.py changes

#### Change 1 — `__init__` signature: add `on_backend_toggle`

Current signature:
```python
    def __init__(self, on_quit=None, on_retry=None, on_open=None, on_settings=None,
                 on_paste_previous=None) -> None:
```

Replace with:
```python
    def __init__(self, on_quit=None, on_retry=None, on_open=None, on_settings=None,
                 on_paste_previous=None, on_backend_toggle=None) -> None:
```

#### Change 2 — `__init__` body: add `_backend` state and store callback

After the line `self._has_previous = False`, add:
```python
        self._backend: str = "openai"
```

After the line `self._on_paste_previous_cb = on_paste_previous`, add:
```python
        self._on_backend_toggle_cb = on_backend_toggle
```

#### Change 3 — add `set_backend` public method

Add this method in the `# ── public API` section, after `set_has_previous`:
```python
    def set_backend(self, backend: str) -> None:
        with self._lock:
            self._backend = backend
```

#### Change 4 — `_build_menu`: add backend toggle item

In `_build_menu`, read `_backend` from locked state at the top where other state is read:

Current locked read block:
```python
        with self._lock:
            state = self._state
            failed = self._failed_count
            has_prev = self._has_previous
```

Replace with:
```python
        with self._lock:
            state = self._state
            failed = self._failed_count
            has_prev = self._has_previous
            backend = self._backend
```

Then in the `items` list, add the backend toggle item after the "Settings…" item
and before `pystray.Menu.SEPARATOR`:

Current items list ends with:
```python
            pystray.MenuItem("Settings…", self._on_settings),
            pystray.Menu.SEPARATOR,
```

Replace with:
```python
            pystray.MenuItem("Settings…", self._on_settings),
            pystray.MenuItem(f"Backend: {backend} → switch", self._on_backend_toggle),
            pystray.Menu.SEPARATOR,
```

#### Change 5 — add `_on_backend_toggle` handler in `# ── internal` section

Add after `_on_settings`:
```python
    def _on_backend_toggle(self, icon, item) -> None:
        if self._on_backend_toggle_cb:
            self._on_backend_toggle_cb()
```

---

### main.py changes

#### Change 6 — pass `on_backend_toggle` to Tray

In `App.__init__`, find the `Tray(...)` constructor call:
```python
        self._tray = Tray(
            on_quit=self._quit,
            on_retry=self._trigger_retry,
            on_open=self._ui.show_window,
            on_settings=self._ui.open_settings,
            on_paste_previous=self._paste_previous,
        )
```

Replace with:
```python
        self._tray = Tray(
            on_quit=self._quit,
            on_retry=self._trigger_retry,
            on_open=self._ui.show_window,
            on_settings=self._ui.open_settings,
            on_paste_previous=self._paste_previous,
            on_backend_toggle=self._toggle_backend,
        )
```

#### Change 7 — set initial backend on tray after Tray init

After the `self._tray = Tray(...)` block, add:
```python
        self._tray.set_backend(self._cfg.get("backend", "openai"))
```

#### Change 8 — add `_toggle_backend` method to `App`

Add this method in the `# ── config` section of the class (near `_on_settings_saved`):
```python
    def _toggle_backend(self) -> None:
        current = self._cfg.get("backend", "openai")
        new_backend = "local" if current == "openai" else "openai"
        self._cfg["backend"] = new_backend
        config.save(self._cfg)
        self._apply_config_env()
        self._tray.set_backend(new_backend)
        if new_backend == "local":
            model = self._cfg.get("local_model", "base")
            self._ui.toast(f"Backend → local ({model})")
        else:
            self._ui.toast("Backend → openai")
```

## Acceptance Criteria

- `python -c "from voiceflow.tray import Tray; t = Tray(on_backend_toggle=lambda: None); print('OK')"` prints `OK`
- `python -c "from voiceflow.main import App"` imports without error
- Tray menu includes "Backend: openai → switch" item on startup (when default config)
