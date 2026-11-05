"""
Notice when the user moves to another place to type, so word suggestions
start fresh instead of continuing the old word.

ClickWatcher: any mouse click or screen touch (read straight from the
input devices, so it works with every app).

AccessibilityWatcher: text field focus and cursor moves reported by apps
over AT-SPI (GTK, Qt/KDE, Firefox, ...). It also gives the text before
the cursor, and tells us when a password field is focused.
"""

import os
import select
import threading

from PyQt6.QtCore import QObject, pyqtSignal

import evdev
from evdev import ecodes

# Our own virtual keyboard device (see input_emitter.py)
OWN_DEVICE_NAME = 'Virtual-OSK'


class ClickWatcher(QObject):
    """
    Emits `clicked` for every mouse button press or screen touch, and
    `primary(pressed)` for each press and release of the left button or a
    touch (used to click the keyboard when a game has grabbed the mouse).
    """

    clicked = pyqtSignal()
    primary = pyqtSignal(bool)

    PRIMARY = {ecodes.BTN_LEFT, ecodes.BTN_TOUCH}

    RESCAN_SECONDS = 5  # look for newly plugged-in mice this often
    BUTTONS = {ecodes.BTN_LEFT, ecodes.BTN_RIGHT, ecodes.BTN_MIDDLE}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name='click-watcher', daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()

    @classmethod
    def _watched_keys(cls, device: evdev.InputDevice) -> set[int]:
        """Key codes of this device that count as a click, if any."""
        if device.name == OWN_DEVICE_NAME:
            return set()
        keys = set(device.capabilities().get(ecodes.EV_KEY, []))
        watched = keys & cls.BUTTONS
        # Touchscreens report touches as BTN_TOUCH. Touchpads do too, but
        # for every finger on the pad, so only their buttons count.
        if ecodes.INPUT_PROP_DIRECT in device.input_props() and ecodes.BTN_TOUCH in keys:
            watched.add(ecodes.BTN_TOUCH)
        return watched

    def _open_devices(self, devices: dict) -> dict:
        """Open devices that appeared since the last scan, drop vanished ones."""
        paths = set(evdev.list_devices())  # only lists devices we may read
        for fd, (device, _) in list(devices.items()):
            if device.path not in paths:
                device.close()
                del devices[fd]
        known = {device.path for device, _ in devices.values()}
        for path in paths - known:
            try:
                device = evdev.InputDevice(path)
            except OSError:
                continue
            watched = self._watched_keys(device)
            if watched:
                devices[device.fd] = (device, watched)
            else:
                device.close()
        return devices

    def _run(self):
        devices: dict[int, tuple[evdev.InputDevice, set[int]]] = {}
        while not self._stop.is_set():
            self._open_devices(devices)
            try:
                ready, _, _ = select.select(list(devices), [], [], self.RESCAN_SECONDS)
            except (OSError, ValueError):
                devices.clear()
                continue
            for fd in ready:
                device, watched = devices[fd]
                try:
                    events = list(device.read())
                except OSError:
                    # Unplugged; the next scan drops it
                    continue
                for e in events:
                    if e.type != ecodes.EV_KEY or e.code not in watched or e.value == 2:
                        continue
                    if e.value == 1:
                        self.clicked.emit()
                    if e.code in self.PRIMARY:
                        self.primary.emit(e.value == 1)
        for device, _ in devices.values():
            device.close()


class AccessibilityWatcher(QObject):
    """
    Emits `text_context(text, truncated, private)` when a text field gets
    focus or its cursor moves: `text` is what comes before the cursor,
    `truncated` says there is more text before that, `private` marks
    password fields (text is then empty). Emits `left_text()` when focus
    moves to something that isn't a text field.

    Needs QT_NO_GLIB=1 (set in main.py), because AT-SPI runs its own
    GLib main loop in a background thread.
    """

    text_context = pyqtSignal(str, bool, bool)
    left_text = pyqtSignal()

    TEXT_BEFORE_CURSOR = 200  # characters to read
    TIMEOUT_MS = 500          # don't wait long on a busy app

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = threading.Thread(target=self._run, name='atspi-watcher', daemon=True)
        self._loop = None
        self._focused = None

    @staticmethod
    def available() -> bool:
        try:
            import gi
            gi.require_version('Atspi', '2.0')
            from gi.repository import Atspi  # noqa: F401
            return True
        except (ImportError, ValueError):
            return False

    def start(self):
        self._thread.start()

    def stop(self):
        if self._loop:
            self._loop.quit()

    def _run(self):
        import gi
        gi.require_version('Atspi', '2.0')
        from gi.repository import Atspi, GLib
        self.Atspi = Atspi

        self._enable_accessibility()
        Atspi.init()
        Atspi.set_timeout(self.TIMEOUT_MS, -1)

        self._listener = Atspi.EventListener.new(self._on_event)
        self._listener.register('object:state-changed:focused')
        self._listener.register('object:text-caret-moved')

        self._loop = GLib.MainLoop()
        self._loop.run()

    @staticmethod
    def _enable_accessibility():
        """
        Ask apps to report to AT-SPI. GTK apps always do; Qt/KDE apps only
        when this is on (it applies to apps started after this).
        """
        try:
            from gi.repository import Gio, GLib
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            bus.call_sync(
                'org.a11y.Bus', '/org/a11y/bus', 'org.freedesktop.DBus.Properties', 'Set',
                GLib.Variant('(ssv)', ('org.a11y.Status', 'IsEnabled', GLib.Variant('b', True))),
                None, Gio.DBusCallFlags.NONE, 1000, None)
        except Exception:
            pass

    def _on_event(self, event):
        try:
            self._handle(event)
        except Exception:
            # An app went away mid-call or answered too slowly
            pass

    def _handle(self, event):
        Atspi = self.Atspi
        source = event.source
        if source is None or source.get_process_id() == os.getpid():
            return

        if event.type.startswith('object:state-changed:focused'):
            if not event.detail1:
                return
            states = source.get_state_set()
            role = source.get_role()
            is_password = role == Atspi.Role.PASSWORD_TEXT
            if not (states.contains(Atspi.StateType.EDITABLE) or is_password):
                self._focused = None
                self.left_text.emit()
                return
            self._focused = source
        elif event.type.startswith('object:text-caret-moved'):
            # Only the field being typed in (some apps also move hidden carets)
            if self._focused is None or source != self._focused:
                return
        else:
            return

        if source.get_role() == Atspi.Role.PASSWORD_TEXT:
            self.text_context.emit('', False, True)
            return

        if source.get_text_iface() is None:
            self.left_text.emit()
            return
        caret = Atspi.Text.get_caret_offset(source)
        start = max(0, caret - self.TEXT_BEFORE_CURSOR)
        text = Atspi.Text.get_text(source, start, caret) if caret > 0 else ''
        self.text_context.emit(text, start > 0, False)
