"""Virtual keyboard widget with PyQt6."""

import importlib
import time

from PyQt6.QtWidgets import (
    QWidget, QPushButton, QSizePolicy, QVBoxLayout, QHBoxLayout
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QFont
from evdev import ecodes

from input_emitter import InputEmitter
from suggestions import WordList

AVAILABLE_LAYOUTS = ['de', 'uk', 'us']

LAYOUT_NAMES = {
    'de': 'Deutsch (DE)',
    'uk': 'English UK',
    'us': 'English US',
}


class KeyButton(QPushButton):
    """A single key button on the virtual keyboard."""

    def __init__(self, normal: str, shifted: str, keycode: int, modifier_keys: set, wide_keys: dict, parent=None):
        super().__init__(normal, parent)
        self.normal_label = normal
        self.shifted_label = shifted
        self.keycode = keycode
        self.is_modifier = keycode in modifier_keys

        base_width = 50
        width_multiplier = wide_keys.get(keycode, 1.0)
        self.key_width = int(base_width * width_multiplier)

        self.setMinimumSize(QSize(self.key_width, 50))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        font = QFont()
        font.setPointSize(14)
        self.setFont(font)

        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def update_label(self, shift_active: bool):
        """Update button label based on shift state."""
        if not self.is_modifier:
            label = self.shifted_label if shift_active else self.normal_label
            # Qt interprets single '&' as a mnemonic; escape it to '&&' to display literal text.
            self.setText(label.replace("&", "&&"))


class SuggestionButton(QPushButton):
    """A word suggestion in the bar above the keys."""

    def __init__(self, parent=None):
        super().__init__('', parent)
        self.word = ''
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def set_word(self, word: str):
        self.word = word
        self.setText(word)
        self.setEnabled(bool(word))


class KeyboardWidget(QWidget):
    """The main virtual keyboard widget."""

    layout_changed = pyqtSignal(str)

    BASE_STYLE = """
        KeyButton {
            background-color: #4a4a4c;
            color: #ffffff;
            border: none;
            border-bottom: 3px solid #2a2a2c;
            border-radius: 8px;
            padding: 5px;
            margin: 2px;
        }
        KeyButton:hover {
            background-color: #5a5a5c;
        }
        KeyButton:pressed {
            background-color: #3a3a3c;
            border-bottom: 1px solid #2a2a2c;
            margin-top: 4px;
        }
        KeyButton[active="true"] {
            background-color: #6a8fba;
            border-bottom: 3px solid #4a6f9a;
        }
        SuggestionButton {
            background-color: transparent;
            color: #ffffff;
            border: none;
            border-radius: 6px;
            padding: 2px 8px;
        }
        SuggestionButton:hover {
            background-color: #3a3a3c;
        }
        SuggestionButton:pressed {
            background-color: #2a2a2c;
        }
        QWidget {
            background-color: #131315;
        }
    """

    BASE_FONT_SIZE = 14
    SUGGESTION_COUNT = 3
    SUGGESTION_BAR_HEIGHT = 36

    # A key held this long may have been repeated by the system, so we can
    # no longer tell how many characters it typed.
    REPEAT_GUARD_SECONDS = 0.5

    # Keys that end the current word
    WORD_BREAK_KEYS = {ecodes.KEY_SPACE, ecodes.KEY_ENTER, ecodes.KEY_TAB}

    def __init__(self, layout='de', parent=None):
        super().__init__(parent)

        self.emitter = InputEmitter()
        self.shift_active = False
        self.caps_active = False
        self.buttons: list[KeyButton] = []
        self.current_layout = layout
        self._current_scale = 1.0

        # Word currently being typed. None means unknown (e.g. after the
        # cursor moved), in which case nothing is suggested until the next
        # word break.
        self.current_word: str | None = ''
        self._char_map: dict[str, tuple[int, bool]] = {}
        self._press_state: dict[int, tuple[str | None, float, bool]] = {}
        self._word_list = WordList.for_layout(layout)

        # Main layout holds the keyboard container
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        self._build_suggestion_bar()

        # Container widget for keyboard keys
        self._container = None

        self._load_layout(layout)
        self._build_keyboard()
        self.setStyleSheet(self.BASE_STYLE)

    def _load_layout(self, name: str):
        """Load layout data from the specified layout module."""
        module = importlib.import_module(f'layouts.{name}')
        self.LAYOUT = module.LAYOUT
        self.MODIFIER_KEYS = module.MODIFIER_KEYS
        self.WIDE_KEYS = module.WIDE_KEYS

    def set_layout(self, name: str):
        """Change to a different keyboard layout."""
        if name == self.current_layout:
            return

        self.current_layout = name
        self._load_layout(name)
        self._word_list = WordList.for_layout(name)
        self._rebuild_keyboard()
        self._set_current_word('')
        self.layout_changed.emit(name)

    def _rebuild_keyboard(self):
        """Rebuild the keyboard with the current layout."""
        self.release_held_keys()

        # Remove old container
        if self._container:
            self._main_layout.removeWidget(self._container)
            self._container.deleteLater()
            self._container = None

        self.buttons.clear()
        self.shift_active = False
        self.caps_active = False

        # Build new keyboard
        self._build_keyboard()
        self.set_scale(self._current_scale)

    def _build_suggestion_bar(self):
        """Build the row of word suggestions above the keys."""
        self._suggestion_bar = QWidget()
        self._suggestion_bar.setFixedHeight(self.SUGGESTION_BAR_HEIGHT)
        bar_layout = QHBoxLayout(self._suggestion_bar)
        bar_layout.setContentsMargins(8, 4, 8, 0)
        bar_layout.setSpacing(4)

        self.suggestion_buttons: list[SuggestionButton] = []
        for _ in range(self.SUGGESTION_COUNT):
            btn = SuggestionButton()
            btn.clicked.connect(lambda checked, b=btn: self._on_suggestion_clicked(b))
            bar_layout.addWidget(btn)
            self.suggestion_buttons.append(btn)

        self._main_layout.addWidget(self._suggestion_bar)
        self._update_suggestions()

    def _build_char_map(self):
        """Map each typeable character to its (keycode, needs_shift)."""
        self._char_map = {' ': (ecodes.KEY_SPACE, False)}
        for row_data in self.LAYOUT:
            for normal, shifted, keycode in row_data:
                # Character keys have different shifted labels; special
                # keys (Tab, arrows, ...) don't.
                if keycode in self.MODIFIER_KEYS or normal == shifted:
                    continue
                if len(normal) == 1:
                    self._char_map.setdefault(normal, (keycode, False))
                if len(shifted) == 1:
                    self._char_map.setdefault(shifted, (keycode, True))

    def _build_keyboard(self):
        """Build the keyboard UI in a container widget."""
        self._build_char_map()

        self._container = QWidget()
        container_layout = QVBoxLayout(self._container)
        container_layout.setSpacing(4)
        container_layout.setContentsMargins(8, 8, 8, 8)

        for row_data in self.LAYOUT:
            row_layout = QHBoxLayout()
            row_layout.setSpacing(4)

            for normal, shifted, keycode in row_data:
                btn = KeyButton(normal, shifted, keycode, self.MODIFIER_KEYS, self.WIDE_KEYS)
                if btn.is_modifier:
                    btn.clicked.connect(lambda checked, b=btn: self._on_modifier_clicked(b))
                else:
                    btn.pressed.connect(lambda b=btn: self._on_key_pressed(b))
                    btn.released.connect(lambda b=btn: self._on_key_released(b))
                row_layout.addWidget(btn)
                self.buttons.append(btn)

            container_layout.addLayout(row_layout)

        self._main_layout.addWidget(self._container)

    def set_scale(self, factor: float):
        """Scale the font size of all buttons."""
        self._current_scale = factor
        new_size = int(self.BASE_FONT_SIZE * factor)
        self._suggestion_bar.setFixedHeight(int(self.SUGGESTION_BAR_HEIGHT * factor))
        for btn in self.buttons + self.suggestion_buttons:
            font = btn.font()
            font.setPointSize(new_size)
            btn.setFont(font)

    def _on_modifier_clicked(self, button: KeyButton):
        """Toggle Shift, Caps, Ctrl or Alt."""
        keycode = button.keycode

        if keycode in (ecodes.KEY_LEFTSHIFT, ecodes.KEY_RIGHTSHIFT):
            self.shift_active = not self.shift_active
            self._update_modifier_state(button, self.shift_active)
            self._update_all_labels()
            return

        if keycode == ecodes.KEY_CAPSLOCK:
            self.caps_active = not self.caps_active
            self._update_modifier_state(button, self.caps_active)
            self._update_all_labels()
            return

        if keycode in (ecodes.KEY_LEFTCTRL, ecodes.KEY_LEFTALT, ecodes.KEY_RIGHTALT):
            is_active = self.emitter.toggle_modifier(keycode)
            self._update_modifier_state(button, is_active)

    def _on_key_pressed(self, button: KeyButton):
        """Send key-down for a regular key."""
        if button.normal_label.isalpha() and len(button.normal_label) == 1:
            apply_shift = self.shift_active != self.caps_active
        else:
            apply_shift = self.shift_active

        label = button.shifted_label if apply_shift else button.normal_label
        typed = label if len(label) == 1 and button.normal_label != button.shifted_label else None
        modified = any(self.emitter.is_modifier_active(k)
                       for k in (ecodes.KEY_LEFTCTRL, ecodes.KEY_LEFTALT, ecodes.KEY_RIGHTALT))
        self._press_state[button.keycode] = (typed, time.monotonic(), modified)

        self.emitter.key_down(button.keycode, with_shift=apply_shift)

    def _on_key_released(self, button: KeyButton):
        """Send key-up for a regular key, then clear one-shot modifiers."""
        self.emitter.key_up(button.keycode)
        self._track_word(button.keycode)

        if self.shift_active:
            self.shift_active = False
            self._update_shift_buttons(False)
            self._update_all_labels()

        self.emitter.release_all_modifiers()
        self._update_ctrl_alt_buttons()

    def _track_word(self, keycode: int):
        """Update the current word after a key was typed."""
        state = self._press_state.pop(keycode, None)
        if state is None:
            return
        typed, pressed_at, modified = state
        repeated = time.monotonic() - pressed_at >= self.REPEAT_GUARD_SECONDS
        word = self.current_word

        if keycode in self.WORD_BREAK_KEYS:
            word = ''
        elif modified or repeated:
            # Shortcut (Ctrl+V, AltGr chars, ...) or possibly repeated key
            word = None
        elif keycode == ecodes.KEY_BACKSPACE:
            # Deleting past the start of the word lands in unknown text
            word = word[:-1] if word else None
        elif typed is not None and typed.isalpha():
            if word is not None:
                word += typed
        elif typed is not None:
            # Digits and punctuation end the word
            word = ''
        else:
            # Arrows and other navigation keys move the cursor
            word = None

        self._set_current_word(word)

    def _set_current_word(self, word: str | None):
        self.current_word = word
        self._update_suggestions()

    def _update_suggestions(self):
        """Refresh the suggestion bar for the current word."""
        words = []
        if self.current_word:
            words = self._word_list.complete(
                self.current_word, set(self._char_map), self.SUGGESTION_COUNT)
        for i, btn in enumerate(self.suggestion_buttons):
            btn.set_word(words[i] if i < len(words) else '')

    def _on_suggestion_clicked(self, button: SuggestionButton):
        """Type the rest of the suggested word plus a space."""
        prefix = self.current_word
        if not button.word or not prefix or not button.word.startswith(prefix):
            return

        # Sticky Ctrl/Alt would turn the letters into shortcuts
        self.emitter.release_all_modifiers()
        self._update_ctrl_alt_buttons()

        for ch in button.word[len(prefix):] + ' ':
            keycode, with_shift = self._char_map[ch]
            self.emitter.send_key(keycode, with_shift=with_shift)

        if self.shift_active:
            self.shift_active = False
            self._update_shift_buttons(False)
            self._update_all_labels()

        self._set_current_word('')

    def _update_modifier_state(self, button: KeyButton, active: bool):
        """Update visual state of a modifier button."""
        button.setProperty('active', active)
        button.style().unpolish(button)
        button.style().polish(button)

    def _update_shift_buttons(self, active: bool):
        """Update all shift button states."""
        for btn in self.buttons:
            if btn.keycode in (ecodes.KEY_LEFTSHIFT, ecodes.KEY_RIGHTSHIFT):
                self._update_modifier_state(btn, active)

    def _update_ctrl_alt_buttons(self):
        """Update ctrl/alt button states based on emitter state."""
        for btn in self.buttons:
            if btn.keycode in (ecodes.KEY_LEFTCTRL, ecodes.KEY_LEFTALT, ecodes.KEY_RIGHTALT):
                is_active = self.emitter.is_modifier_active(btn.keycode)
                self._update_modifier_state(btn, is_active)

    def _update_all_labels(self):
        """Update all button labels based on current shift/caps state."""
        for btn in self.buttons:
            if btn.normal_label.isalpha() and len(btn.normal_label) == 1:
                show_shifted = self.shift_active != self.caps_active
            else:
                show_shifted = self.shift_active
            btn.update_label(show_shifted)

    def move_window_to_monitor(self, direction: str):
        """Move the active window to another monitor using Win+Shift+Arrow."""
        arrow_key = ecodes.KEY_LEFT if direction == 'left' else ecodes.KEY_RIGHT

        self.emitter.device.write(ecodes.EV_KEY, ecodes.KEY_LEFTMETA, 1)
        self.emitter.device.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, 1)
        self.emitter.device.syn()

        self.emitter.device.write(ecodes.EV_KEY, arrow_key, 1)
        self.emitter.device.syn()
        self.emitter.device.write(ecodes.EV_KEY, arrow_key, 0)
        self.emitter.device.syn()

        self.emitter.device.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, 0)
        self.emitter.device.write(ecodes.EV_KEY, ecodes.KEY_LEFTMETA, 0)
        self.emitter.device.syn()

    def release_held_keys(self):
        """Release any key still held so it can't get stuck repeating."""
        for btn in self.buttons:
            if btn.isDown() and not btn.is_modifier:
                btn.setDown(False)
                self._on_key_released(btn)
        self.emitter.release_all_keys()

    def hideEvent(self, event):
        """Release held keys when the keyboard is hidden."""
        self.release_held_keys()
        super().hideEvent(event)

    def closeEvent(self, event):
        """Clean up when widget is closed."""
        self.emitter.close()
        super().closeEvent(event)
