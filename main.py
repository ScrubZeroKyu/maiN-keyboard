#!/usr/bin/env python3
"""
Virtual On-Screen Keyboard for KDE/Wayland

Runs under XWayland for better focus handling.
"""

import sys
import os
import json
import socket
import time

# Force XWayland mode for better focus handling
os.environ['QT_QPA_PLATFORM'] = 'xcb'
# Qt must not run the GLib main loop: the accessibility watcher runs its
# own in a background thread (see focus_watch.py)
os.environ['QT_NO_GLIB'] = '1'

CONFIG_FILE = os.path.expanduser('~/.config/osk/settings.json')

from PyQt6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout,
    QVBoxLayout, QLabel, QPushButton,
    QSystemTrayIcon, QMenu
)
from PyQt6.QtCore import Qt, QObject, QEvent, QRect, QTimer
from PyQt6.QtGui import QCursor, QMouseEvent, QGuiApplication, QIcon, QAction, QActionGroup, QColor, QPainter, QPen

from keyboard import KeyboardWidget, AVAILABLE_LAYOUTS, LAYOUT_NAMES
from options import OPACITY_LEVELS, OptionsDialog
from focus_watch import AccessibilityWatcher, ClickWatcher


def load_config():
    """Load settings from config file."""
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_config(config):
    """Save settings to config file."""
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)


class TitleBar(QWidget):
    """Custom title bar with drag support and close button."""

    STYLE = """
        TitleBar {
            background-color: #131315;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
        }
        QLabel {
            color: #8e8e93;
            font-size: 12px;
            padding-left: 8px;
        }
        QPushButton {
            background-color: transparent;
            color: #8e8e93;
            border: none;
            font-size: 16px;
            padding: 4px 12px;
        }
        QPushButton:hover {
            background-color: #3a3a3c;
            color: white;
        }
        QPushButton#close_btn:hover {
            background-color: #c42b1c;
            border-top-right-radius: 8px;
        }
        QPushButton#options_btn {
            font-size: 16px;
            padding: 4px 8px;
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.window_parent = parent
        self._drag_pos = None

        self.setFixedHeight(32)
        self.setStyleSheet(self.STYLE)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title label
        self.title_label = QLabel("MaiN_Keyboard")
        self.title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.title_label)

        # Spacer
        spacer = QWidget()
        spacer.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        spacer.setSizePolicy(spacer.sizePolicy().Policy.Expanding, spacer.sizePolicy().Policy.Preferred)
        layout.addWidget(spacer)

        # Monitor switch buttons
        # Move the active window (the app being typed in) to another monitor
        self.mon_left_btn = QPushButton("<-")
        self.mon_left_btn.setFixedSize(40, 32)
        self.mon_left_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.mon_left_btn.setToolTip("Move the active window to the left monitor")
        self.mon_left_btn.clicked.connect(lambda: self._on_move_monitor('left'))
        layout.addWidget(self.mon_left_btn)

        self.mon_right_btn = QPushButton("->")
        self.mon_right_btn.setFixedSize(40, 32)
        self.mon_right_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.mon_right_btn.setToolTip("Move the active window to the right monitor")
        self.mon_right_btn.clicked.connect(lambda: self._on_move_monitor('right'))
        layout.addWidget(self.mon_right_btn)

        # Separator
        sep = QWidget()
        sep.setFixedWidth(10)
        layout.addWidget(sep)

        # Options button (layout, suggestions, word lists)
        self.options_btn = QPushButton("⚙")
        self.options_btn.setObjectName("options_btn")
        self.options_btn.setFixedSize(40, 32)
        self.options_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.options_btn.setToolTip("Options")
        self.options_btn.clicked.connect(lambda: self.window_parent.open_options())
        layout.addWidget(self.options_btn)

        # Close button
        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("close_btn")
        self.close_btn.setFixedSize(46, 32)
        self.close_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.close_btn.clicked.connect(self._on_close)
        layout.addWidget(self.close_btn)

    def _on_close(self):
        self.window_parent.hide()

    def _on_move_monitor(self, direction):
        if self.window_parent:
            self.window_parent.keyboard.move_window_to_monitor(direction)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.window_parent.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos:
            self.window_parent.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None


class EdgeResizer(QObject):
    """
    Lets the user resize the frameless window by dragging its edges or
    corners. The window bypasses the window manager, so KDE can't resize
    it for us. Installed as an application-wide event filter so it sees
    presses over child widgets too.
    """

    EDGE = 4  # px from the window border that count as a resize handle (= key margin)

    CURSORS = {
        Qt.Edge.LeftEdge: Qt.CursorShape.SizeHorCursor,
        Qt.Edge.RightEdge: Qt.CursorShape.SizeHorCursor,
        Qt.Edge.TopEdge: Qt.CursorShape.SizeVerCursor,
        Qt.Edge.BottomEdge: Qt.CursorShape.SizeVerCursor,
        Qt.Edge.LeftEdge | Qt.Edge.TopEdge: Qt.CursorShape.SizeFDiagCursor,
        Qt.Edge.RightEdge | Qt.Edge.BottomEdge: Qt.CursorShape.SizeFDiagCursor,
        Qt.Edge.RightEdge | Qt.Edge.TopEdge: Qt.CursorShape.SizeBDiagCursor,
        Qt.Edge.LeftEdge | Qt.Edge.BottomEdge: Qt.CursorShape.SizeBDiagCursor,
    }

    def __init__(self, window: QWidget, on_finished=None):
        super().__init__(window)
        self.window = window
        self.on_finished = on_finished
        self._edges = Qt.Edge(0)
        self._start_pos = None
        self._start_geo = None

    def _edges_at(self, global_pos) -> Qt.Edge:
        geo = self.window.frameGeometry()
        x = global_pos.x() - geo.x()
        y = global_pos.y() - geo.y()
        if not (0 <= x < geo.width() and 0 <= y < geo.height()):
            return Qt.Edge(0)
        edges = Qt.Edge(0)
        if x < self.EDGE:
            edges |= Qt.Edge.LeftEdge
        elif x >= geo.width() - self.EDGE:
            edges |= Qt.Edge.RightEdge
        if y < self.EDGE:
            edges |= Qt.Edge.TopEdge
        elif y >= geo.height() - self.EDGE:
            edges |= Qt.Edge.BottomEdge
        return edges

    def _resize_to(self, global_pos):
        dx = global_pos.x() - self._start_pos.x()
        dy = global_pos.y() - self._start_pos.y()
        g = QRect(self._start_geo)
        min_w = self.window.minimumWidth()
        min_h = self.window.minimumHeight()

        if self._edges & Qt.Edge.LeftEdge:
            g.setLeft(min(g.left() + dx, g.right() - min_w + 1))
        if self._edges & Qt.Edge.RightEdge:
            g.setRight(max(g.right() + dx, g.left() + min_w - 1))
        if self._edges & Qt.Edge.TopEdge:
            g.setTop(min(g.top() + dy, g.bottom() - min_h + 1))
        if self._edges & Qt.Edge.BottomEdge:
            g.setBottom(max(g.bottom() + dy, g.top() + min_h - 1))

        self.window.setGeometry(g)

    def eventFilter(self, obj, event):
        etype = event.type()
        if etype not in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove,
                         QEvent.Type.HoverMove, QEvent.Type.MouseButtonRelease):
            return False
        if not isinstance(obj, QWidget) or QWidget.window(obj) is not self.window:
            return False

        pos = event.globalPosition().toPoint()

        if self._start_pos is not None:
            if etype == QEvent.Type.MouseMove:
                self._resize_to(pos)
                return True
            if etype == QEvent.Type.MouseButtonRelease:
                self._start_pos = None
                self.window.unsetCursor()
                if self.on_finished:
                    self.on_finished()
                return True
            return etype == QEvent.Type.MouseButtonPress

        edges = self._edges_at(pos)

        if etype == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton and edges:
            self._edges = edges
            self._start_pos = pos
            self._start_geo = self.window.geometry()
            return True

        if etype in (QEvent.Type.MouseMove, QEvent.Type.HoverMove) and not event_has_buttons(event):
            if edges:
                self.window.setCursor(self.CURSORS[edges])
            else:
                self.window.unsetCursor()

        return False


class PressTracker(QObject):
    """Remembers when the keyboard window itself was last clicked or touched."""

    PRESS_EVENTS = (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick,
                    QEvent.Type.TouchBegin)

    def __init__(self, window: QWidget):
        super().__init__(window)
        self.window = window
        self.last_press = 0.0

    def eventFilter(self, obj, event):
        if (event.type() in self.PRESS_EVENTS and isinstance(obj, QWidget)
                and QWidget.window(obj) is self.window):
            self.last_press = time.monotonic()
        return False


def event_has_buttons(event) -> bool:
    """True if a mouse button is held during this event."""
    return hasattr(event, 'buttons') and event.buttons() != Qt.MouseButton.NoButton


class VirtualKeyboard(QWidget):
    """Main window for the virtual keyboard."""

    # Default size (the old "S" size); the smallest allowed is half of it
    BASE_WIDTH = 900
    BASE_HEIGHT = 348
    MIN_FACTOR = 0.5

    BACKGROUND = QColor('#131315')
    # Shows where the window can be grabbed to resize it
    OUTLINE = QColor(255, 255, 255, 200)
    OUTLINE_WIDTH = 1

    def __init__(self):
        super().__init__()

        # Window flags for OSK behavior under X11/XWayland
        self.setWindowFlags(
            Qt.WindowType.Tool |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.X11BypassWindowManagerHint
        )

        # Prevent focus stealing
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_X11DoNotAcceptFocus)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Load saved settings
        config = load_config()
        # Older versions saved a scale factor instead of a size
        old_scale = config.get('scale', 1.0)
        self._saved_width = config.get('width', int(self.BASE_WIDTH * old_scale))
        self._saved_height = config.get('height', int(self.BASE_HEIGHT * old_scale))
        self._current_layout = config.get('layout', 'de')
        self._current_opacity = config.get('opacity', 1.0)
        suggestion_count = config.get('suggestion_count', KeyboardWidget.SUGGESTION_COUNT)
        next_word = config.get('next_word', True)
        self._options_dialog = None
        self.click_reset_enabled = config.get('click_reset', True)
        self.accessibility_enabled = config.get('accessibility', True)
        self._click_watcher = None
        self._a11y_watcher = None

        # Main layout, inset so the outline painted around it stays visible
        layout = QVBoxLayout(self)
        w = self.OUTLINE_WIDTH
        layout.setContentsMargins(w, w, w, w)
        layout.setSpacing(0)

        # Title bar
        self.title_bar = TitleBar(self)
        layout.addWidget(self.title_bar)

        # Keyboard with saved layout
        self.keyboard = KeyboardWidget(layout=self._current_layout,
                                       suggestion_count=suggestion_count,
                                       next_word=next_word)
        self.keyboard.layout_changed.connect(self._on_layout_changed)
        layout.addWidget(self.keyboard)

        # Resizable by dragging the edges, down to half the default size
        self.setMinimumSize(int(self.BASE_WIDTH * self.MIN_FACTOR),
                            int(self.BASE_HEIGHT * self.MIN_FACTOR))
        self._resizer = EdgeResizer(self, on_finished=self._save_size)
        QApplication.instance().installEventFilter(self._resizer)
        self._press_tracker = PressTracker(self)
        QApplication.instance().installEventFilter(self._press_tracker)

        # Start a fresh word when the user goes to type somewhere else
        self._grab_press = None
        self._start_click_watcher()
        self.set_accessibility(self.accessibility_enabled, save=False)

        self._position_at_bottom()
        self.setWindowOpacity(self._current_opacity)

        # Tray menu actions (will be set by main())
        self.layout_actions = {}
        self.opacity_actions = {}

    def _on_layout_changed(self, layout_name: str):
        """Handle layout change from keyboard widget."""
        self._current_layout = layout_name
        self._enable_mouse_tracking()

        # Update tray menu checkmarks
        for name, action in self.layout_actions.items():
            action.setChecked(name == layout_name)

        self._save_setting('layout', layout_name)
        if self._options_dialog:
            # Each language has its own word lists
            self._options_dialog.refresh()

    def set_layout(self, name: str):
        """Set a specific layout."""
        self.keyboard.set_layout(name)

    def set_suggestion_count(self, count: int):
        self.keyboard.set_suggestion_count(count)
        self._enable_mouse_tracking()
        self._save_setting('suggestion_count', self.keyboard.suggestion_count)

    def set_next_word(self, enabled: bool):
        self.keyboard.set_next_word(enabled)
        self._save_setting('next_word', enabled)

    # How long after a click to wait for the app to report the new text
    # field (accessibility) before falling back to just starting fresh
    CLICK_SETTLE_MS = 250

    def set_click_reset(self, enabled: bool, save: bool = True):
        """Start a new word after any click or touch outside the keyboard."""
        self.click_reset_enabled = enabled
        if save:
            self._save_setting('click_reset', enabled)

    def _start_click_watcher(self):
        """Read clicks straight from the mouse (see focus_watch.py)."""
        self._click_watcher = ClickWatcher(self)
        self._click_watcher.clicked.connect(self._on_outside_click)
        self._click_watcher.primary.connect(self._on_primary_button)
        self._click_watcher.start()

    # --- Clicking the keyboard while a game has grabbed the mouse ---
    #
    # Fullscreen games (e.g. through Wine/Proton) can grab the mouse, so
    # every click goes to the game even over the keyboard. The mouse
    # device still tells us about the click and X still tells us where the
    # cursor is, so when a click on the keyboard never reaches it, the
    # keyboard passes the click on to the key itself. The game sees that
    # click too; nothing can take it away from the game.

    # How long the normal click may take to reach us before we stand in
    GRAB_CHECK_MS = 80

    def _on_primary_button(self, pressed: bool):
        if pressed:
            pos = QCursor.pos()
            if not self.isVisible() or not self.frameGeometry().contains(pos):
                return
            self._grab_press = {'time': time.monotonic(), 'pos': pos,
                                'released': False, 'target': None}
            QTimer.singleShot(self.GRAB_CHECK_MS, self._check_grabbed_press)
        elif self._grab_press:
            press = self._grab_press
            if press['target'] is not None:
                self._send_mouse(press['target'], QEvent.Type.MouseButtonRelease, press['pos'])
                self._grab_press = None
            else:
                # Released before the check ran; it finishes the click
                press['released'] = True

    def _check_grabbed_press(self):
        press = self._grab_press
        if press is None:
            return
        if self._press_tracker.last_press >= press['time'] - 0.15:
            # The keyboard got the click the normal way
            self._grab_press = None
            return
        target = self.childAt(self.mapFromGlobal(press['pos'])) or self
        press['target'] = target
        self._send_mouse(target, QEvent.Type.MouseButtonPress, press['pos'])
        if press['released']:
            self._send_mouse(target, QEvent.Type.MouseButtonRelease, press['pos'])
            self._grab_press = None

    @staticmethod
    def _send_mouse(widget: QWidget, etype: QEvent.Type, global_pos):
        buttons = (Qt.MouseButton.LeftButton if etype == QEvent.Type.MouseButtonPress
                   else Qt.MouseButton.NoButton)
        local = widget.mapFromGlobal(global_pos).toPointF()
        event = QMouseEvent(etype, local, global_pos.toPointF(), Qt.MouseButton.LeftButton,
                            buttons, Qt.KeyboardModifier.NoModifier)
        # Our own stand-in click must not count as the keyboard receiving one
        tracker = widget.window()._press_tracker
        last_press = tracker.last_press
        QApplication.sendEvent(widget, event)
        tracker.last_press = last_press

    def set_accessibility(self, enabled: bool, save: bool = True):
        """Follow text field focus and the text at the cursor through AT-SPI."""
        enabled = enabled and AccessibilityWatcher.available()
        self.accessibility_enabled = enabled
        if enabled and not self._a11y_watcher:
            watcher = AccessibilityWatcher(self)
            watcher.text_context.connect(self.keyboard.set_text_from_app)
            watcher.left_text.connect(self.keyboard.reset_text)
            watcher.start()
            self._a11y_watcher = watcher
        elif not enabled and self._a11y_watcher:
            self._a11y_watcher.text_context.disconnect()
            self._a11y_watcher.left_text.disconnect()
            self._a11y_watcher.stop()
            self._a11y_watcher = None
        if save:
            self._save_setting('accessibility', enabled)

    def _on_outside_click(self):
        if not self.click_reset_enabled:
            return
        # Clicks on the keyboard itself (also while a game has the mouse)
        if self.isVisible() and self.frameGeometry().contains(QCursor.pos()):
            return
        clicked_at = time.monotonic()
        QTimer.singleShot(self.CLICK_SETTLE_MS, lambda: self._after_click(clicked_at))

    def _after_click(self, clicked_at: float):
        # Clicks on the keyboard itself arrive here too
        if abs(self._press_tracker.last_press - clicked_at) < 0.5:
            return
        # The app already told us where the cursor is now
        if self.keyboard.app_text_time > clicked_at:
            return
        self.keyboard.reset_text()

    def open_options(self):
        """Show the options window above the keyboard."""
        if self._options_dialog is None:
            self._options_dialog = OptionsDialog(self, LAYOUT_NAMES)
        dialog = self._options_dialog
        dialog.refresh()
        dialog.adjustSize()
        geo = self.frameGeometry()
        screen = (self.screen() or QGuiApplication.primaryScreen()).availableGeometry()
        x = geo.x() + (geo.width() - dialog.width()) // 2
        y = geo.y() - dialog.height() - 40
        x = max(screen.left(), min(x, screen.right() - dialog.width()))
        y = max(screen.top(), y)
        dialog.move(x, y)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    @staticmethod
    def _save_setting(key, value):
        config = load_config()
        config[key] = value
        save_config(config)

    def paintEvent(self, event):
        """Background plus a thin outline that marks the resizable edge."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.BACKGROUND)
        pen = QPen(self.OUTLINE)
        pen.setWidth(self.OUTLINE_WIDTH)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        painter.setPen(pen)
        half = self.OUTLINE_WIDTH / 2
        painter.drawRect(self.rect().toRectF().adjusted(half, half, -half, -half))
        painter.end()

    def _position_at_bottom(self):
        """Position the keyboard at the bottom center of the screen."""
        screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            width = max(self.minimumWidth(), min(self._saved_width, geo.width() - 40))
            height = max(self.minimumHeight(), min(self._saved_height, geo.height() - 58))
            x = geo.x() + (geo.width() - width) // 2
            y = geo.y() + geo.height() - height - 58
            self.setGeometry(x, y, width, height)

    def resizeEvent(self, event):
        """Scale key labels with the window size."""
        factor = min(self.width() / self.BASE_WIDTH, self.height() / self.BASE_HEIGHT)
        self.keyboard.set_scale(max(self.MIN_FACTOR, factor))
        super().resizeEvent(event)

    def showEvent(self, event):
        self._enable_mouse_tracking()
        super().showEvent(event)

    def _enable_mouse_tracking(self):
        """Needed so hovering an edge shows the resize cursor."""
        self.setMouseTracking(True)
        for child in self.findChildren(QWidget):
            child.setMouseTracking(True)

    def _save_size(self):
        config = load_config()
        config['width'] = self.width()
        config['height'] = self.height()
        config.pop('scale', None)
        save_config(config)

    def set_opacity(self, opacity: float):
        """Set the window opacity and save to config."""
        self._current_opacity = opacity
        self.setWindowOpacity(opacity)
        # Update tray menu checkmarks
        for value, action in self.opacity_actions.items():
            action.setChecked(value == opacity)
        self._save_setting('opacity', opacity)
        if self._options_dialog:
            self._options_dialog.refresh()

    def shutdown(self):
        """Stop background watchers and save settings before quitting."""
        app = QApplication.instance()
        app.removeEventFilter(self._resizer)
        app.removeEventFilter(self._press_tracker)
        if self._click_watcher:
            self._click_watcher.stop()
        if self._a11y_watcher:
            self._a11y_watcher.stop()
        config = load_config()
        config['width'] = self.width()
        config['height'] = self.height()
        config['layout'] = self._current_layout
        save_config(config)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            QApplication.quit()
        else:
            super().keyPressEvent(event)

    def hideEvent(self, event):
        """Save settings when hiding."""
        config = load_config()
        config['width'] = self.width()
        config['height'] = self.height()
        config.pop('scale', None)
        config['layout'] = self._current_layout
        save_config(config)
        super().hideEvent(event)


def acquire_single_instance_lock():
    """Acquire a lock to ensure only one instance runs. Returns socket or None."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        # Abstract socket (Linux) - auto-released on process exit
        sock.bind('\0main-keyboard-instance-lock')
        return sock
    except socket.error:
        return None


def main():
    # Single instance check
    lock_socket = acquire_single_instance_lock()
    if lock_socket is None:
        print("MaiN_Keyboard läuft bereits.")
        sys.exit(0)

    app = QApplication(sys.argv)
    app.setApplicationName('MaiN_Keyboard')
    app.setStyle('Fusion')
    app.setQuitOnLastWindowClosed(False)

    window = VirtualKeyboard()
    window.show()

    # Release held keys and modifiers before the uinput device goes away
    app.aboutToQuit.connect(window.keyboard.emitter.close)

    # System tray icon
    tray = QSystemTrayIcon()
    tray.setIcon(QIcon.fromTheme('input-keyboard'))
    tray.setToolTip('MaiN_Keyboard')

    # Tray menu
    menu = QMenu()

    options_action = QAction('Options…', menu)
    options_action.triggered.connect(window.open_options)
    menu.addAction(options_action)

    menu.addSeparator()

    show_action = QAction('Show', menu)
    show_action.triggered.connect(window.show)
    menu.addAction(show_action)

    hide_action = QAction('Hide', menu)
    hide_action.triggered.connect(window.hide)
    menu.addAction(hide_action)

    menu.addSeparator()

    # Layout submenu
    layout_menu = QMenu('Layout', menu)
    layout_group = QActionGroup(layout_menu)
    layout_group.setExclusive(True)

    for layout_id in AVAILABLE_LAYOUTS:
        layout_name = LAYOUT_NAMES.get(layout_id, layout_id.upper())
        action = QAction(layout_name, layout_menu)
        action.setCheckable(True)
        action.setChecked(layout_id == window._current_layout)
        action.triggered.connect(lambda checked, lid=layout_id: window.set_layout(lid))
        layout_group.addAction(action)
        layout_menu.addAction(action)
        window.layout_actions[layout_id] = action

    menu.addMenu(layout_menu)

    # Opacity submenu
    opacity_menu = QMenu('Opacity', menu)
    opacity_group = QActionGroup(opacity_menu)
    opacity_group.setExclusive(True)

    for opacity_value, opacity_name in OPACITY_LEVELS:
        action = QAction(opacity_name, opacity_menu)
        action.setCheckable(True)
        action.setChecked(opacity_value == window._current_opacity)
        action.triggered.connect(lambda checked, ov=opacity_value: window.set_opacity(ov))
        opacity_group.addAction(action)
        opacity_menu.addAction(action)
        window.opacity_actions[opacity_value] = action

    menu.addMenu(opacity_menu)

    menu.addSeparator()

    quit_action = QAction('Quit', menu)
    quit_action.triggered.connect(app.quit)
    menu.addAction(quit_action)

    tray.setContextMenu(menu)
    tray.activated.connect(lambda reason: window.setVisible(not window.isVisible()) if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
    tray.show()

    code = app.exec()
    window.shutdown()
    # Skip Python's own cleanup: it deletes Qt objects in an order that
    # can crash PyQt on exit. Everything worth keeping is saved by now.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)


if __name__ == '__main__':
    main()
