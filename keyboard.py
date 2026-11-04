"""Virtual keyboard widget with PyQt6."""

import importlib
import time

from PyQt6.QtWidgets import (
    QWidget, QPushButton, QSizePolicy, QVBoxLayout, QHBoxLayout
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter
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

    LABEL_COLOR = QColor('#ffffff')
    SECONDARY_COLOR = QColor('#b0b0b5')

    def __init__(self, normal: str, shifted: str, keycode: int, modifier_keys: set,
                 fn_key: tuple[str, int] | None = None, parent=None):
        # Labels are painted by paintEvent, not by QPushButton
        super().__init__('', parent)
        self.normal_label = normal
        self.shifted_label = shifted
        self.keycode = keycode
        self.is_modifier = keycode in modifier_keys
        # (label, keycode) used while Fn is on, e.g. ('F1', KEY_F1)
        self.fn_key = fn_key
        self.fn_active = False
        self.shift_shown = False

        font = QFont()
        font.setPointSize(14)
        self.setFont(font)

        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def current_keycode(self) -> int:
        """Keycode to send, taking Fn into account."""
        if self.fn_active and self.fn_key:
            return self.fn_key[1]
        return self.keycode

    def update_label(self, shift_active: bool, fn_active: bool = False):
        """Update button label based on shift and Fn state."""
        self.fn_active = fn_active
        self.shift_shown = shift_active and not self.is_modifier
        self.update()

    def labels(self) -> tuple[str, str]:
        """(main label, small top-left label) as currently shown."""
        if self.fn_active and self.fn_key:
            return self.fn_key[0], ''
        normal, shifted = self.normal_label, self.shifted_label
        is_symbol_pair = (len(normal) == 1 and len(shifted) == 1
                          and normal != shifted and not normal.isalpha())
        if is_symbol_pair:
            # Like a real keycap: the other character small in the corner
            return (shifted, normal) if self.shift_shown else (normal, shifted)
        return (shifted if self.shift_shown else normal), ''

    def paintEvent(self, event):
        super().paintEvent(event)  # background from the style sheet

        main, small = self.labels()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        rect = self.rect()
        font = self.font()
        px = max(1, font.pixelSize())
        pad = max(2, int(px * 0.35))

        if small:
            small_font = QFont(font)
            small_font.setPixelSize(max(6, int(px * 0.7)))
            painter.setFont(small_font)
            painter.setPen(self.SECONDARY_COLOR)
            painter.drawText(rect.adjusted(pad, pad // 2, 0, 0),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, small)
            # Main character sits a little lower, below the small one
            main_rect = rect.adjusted(0, int(rect.height() * 0.2), 0, 0)
            align = Qt.AlignmentFlag.AlignCenter
        elif len(main) > 1 and main != 'Space' and not (self.fn_active and self.fn_key):
            # Word keys (Tab, Shift, Enter, Home, ...) are left-aligned
            main_rect = rect.adjusted(pad, 0, 0, 0)
            align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        else:
            main_rect = rect
            align = Qt.AlignmentFlag.AlignCenter

        # Shrink labels that don't fit the key (e.g. "AltGr" on a 1x key)
        available = main_rect.width() - pad
        text_w = QFontMetrics(font).horizontalAdvance(main)
        if text_w > available > 0:
            font = QFont(font)
            font.setPixelSize(max(6, int(px * available / text_w)))

        painter.setFont(font)
        painter.setPen(self.LABEL_COLOR)
        painter.drawText(main_rect, align, main)
        painter.end()


class KeyArea(QWidget):
    """
    Places keys at exact positions measured in key units, so rows line
    up like a real keyboard and keys can span several rows.
    """

    def __init__(self, margin: int, gap: int, on_resized=None, parent=None):
        super().__init__(parent)
        self.margin = margin
        self.gap = gap
        self.on_resized = on_resized
        # (button, x, row, width, height) in key units / rows
        self.placements: list[tuple[QPushButton, float, int, float, int]] = []
        self.total_units = 1.0
        self.total_rows = 1
        self.unit_w = 0.0
        self.row_h = 0.0

    def place(self, button, x: float, row: int, width: float, height: int = 1):
        button.setParent(self)
        self.placements.append((button, x, row, width, height))
        self.total_units = max(self.total_units, x + width)
        self.total_rows = max(self.total_rows, row + height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        m, gap = self.margin, self.gap
        # One gap per key is taken off its right/bottom edge
        self.unit_w = (self.width() - 2 * m + gap) / self.total_units
        self.row_h = (self.height() - 2 * m + gap) / self.total_rows
        for button, x, row, width, height in self.placements:
            left = round(m + x * self.unit_w)
            right = round(m + (x + width) * self.unit_w) - gap
            top = round(m + row * self.row_h)
            bottom = round(m + (row + height) * self.row_h) - gap
            button.setGeometry(left, top, max(1, right - left), max(1, bottom - top))
        if self.on_resized:
            self.on_resized()


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
        QWidget {
            background-color: #131315;
        }
        KeyButton {
            background-color: #4a4a4c;
            color: #ffffff;
            border: none;
            border-radius: 0px;
            padding: 0px;
            margin: 0px;
        }
        KeyButton:hover {
            background-color: #5a5a5c;
        }
        KeyButton:pressed {
            background-color: #1f3a70;
        }
        KeyButton[active="true"] {
            background-color: #6a8fba;
        }
        SuggestionButton {
            background-color: transparent;
            color: #ffffff;
            border: none;
            border-radius: 0px;
            padding: 2px 8px;
        }
        SuggestionButton:hover {
            background-color: #3a3a3c;
        }
        SuggestionButton:pressed {
            background-color: #2a2a2c;
        }
        SuggestionButton#add_word {
            color: #8e8e93;
        }
    """

    KEY_GAP = 3      # px between keys
    KEY_MARGIN = 4   # px around the key area (matches the window resize zone)
    LABEL_RATIO = 0.45  # label height relative to key height
    SUGGESTION_COUNT = 3
    SUGGESTION_BAR_HEIGHT = 36

    # A key held this long may have been repeated by the system, so we can
    # no longer tell how many characters it typed.
    REPEAT_GUARD_SECONDS = 0.5

    # Keys that end the current word
    WORD_BREAK_KEYS = {ecodes.KEY_SPACE, ecodes.KEY_ENTER, ecodes.KEY_TAB}

    # Modifiers held on the virtual device until the next regular key
    STICKY_MODIFIERS = {
        ecodes.KEY_LEFTCTRL, ecodes.KEY_RIGHTCTRL,
        ecodes.KEY_LEFTALT, ecodes.KEY_RIGHTALT,
        ecodes.KEY_LEFTMETA,
    }

    SIDE_BLOCK_GAP = 0.5  # units between the main keys and the side block

    def __init__(self, layout='de', parent=None):
        super().__init__(parent)

        self.emitter = InputEmitter()
        self.shift_active = False
        self.caps_active = False
        self.fn_active = False
        self.buttons: list[KeyButton] = []
        self.current_layout = layout
        self._current_scale = 1.0

        # Word currently being typed. None means unknown (e.g. after the
        # cursor moved), in which case nothing is suggested until the next
        # word break.
        self.current_word: str | None = ''
        self._char_map: dict[str, tuple[int, bool]] = {}
        # button keycode -> (typed char, press time, modified, sent keycode)
        self._press_state: dict[int, tuple[str | None, float, bool, int]] = {}
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
        self.TALL_KEYS = getattr(module, 'TALL_KEYS', {})
        self.SIDE_BLOCK = getattr(module, 'SIDE_BLOCK', [])
        self.SIDE_WIDE_KEYS = getattr(module, 'SIDE_WIDE_KEYS', {})
        self.FN_KEYS = getattr(module, 'FN_KEYS', {})

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
            self._container.hide()
            self._container.deleteLater()
            self._container = None

        self.buttons.clear()
        self.shift_active = False
        self.caps_active = False
        self.fn_active = False

        # Build new keyboard
        self._build_keyboard()
        self.set_scale(self._current_scale)

    def _build_suggestion_bar(self):
        """Build the row of word suggestions above the keys."""
        self._suggestion_bar = QWidget()
        self._suggestion_bar.setFixedHeight(self.SUGGESTION_BAR_HEIGHT)
        bar_layout = QHBoxLayout(self._suggestion_bar)
        bar_layout.setContentsMargins(self.KEY_MARGIN, self.KEY_MARGIN, self.KEY_MARGIN, 0)
        bar_layout.setSpacing(self.KEY_GAP)

        self.suggestion_buttons: list[SuggestionButton] = []
        for _ in range(self.SUGGESTION_COUNT):
            btn = SuggestionButton()
            btn.clicked.connect(lambda checked, b=btn: self._on_suggestion_clicked(b))
            bar_layout.addWidget(btn)
            self.suggestion_buttons.append(btn)

        # Shown while typing a word that isn't in the word list
        self.add_word_button = SuggestionButton()
        self.add_word_button.setObjectName('add_word')
        self.add_word_button.setToolTip('Add this word to the suggestions')
        self.add_word_button.clicked.connect(self._on_add_word_clicked)
        bar_layout.addWidget(self.add_word_button)

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

        self._container = KeyArea(self.KEY_MARGIN, self.KEY_GAP, on_resized=self._fit_labels)

        main_width = self._place_rows(self.LAYOUT, self.WIDE_KEYS, x_offset=0.0)
        if self.SIDE_BLOCK:
            self._place_rows(self.SIDE_BLOCK, self.SIDE_WIDE_KEYS,
                             x_offset=main_width + self.SIDE_BLOCK_GAP)

        self._main_layout.addWidget(self._container)

    def _place_rows(self, rows, wide_keys: dict, x_offset: float) -> float:
        """
        Place rows of keys left to right, skipping space taken by keys
        from rows above (like a two-row Enter). Rows shorter than the
        widest row are stretched to the same width. Returns that width.
        """
        # Per row: list of (start, end) units already taken by tall keys
        taken: dict[int, list[tuple[float, float]]] = {}
        rows_placed = []

        for row_idx, row_data in enumerate(rows):
            x = 0.0
            keys = []
            for normal, shifted, keycode in row_data:
                for start, end in sorted(taken.get(row_idx, [])):
                    if abs(x - start) < 1e-6:
                        x = end
                width = wide_keys.get(keycode, 1.0)
                height = self.TALL_KEYS.get(keycode, 1)
                keys.append((normal, shifted, keycode, x, width, height))
                for extra in range(1, height):
                    taken.setdefault(row_idx + extra, []).append((x, x + width))
                x += width
            row_end = max([x] + [end for _, end in taken.get(row_idx, [])])
            rows_placed.append((row_idx, keys, row_end))

        full_width = max(end for _, _, end in rows_placed)

        for row_idx, keys, row_end in rows_placed:
            stretch = full_width / row_end if row_end else 1.0
            for normal, shifted, keycode, x, width, height in keys:
                btn = KeyButton(normal, shifted, keycode, self.MODIFIER_KEYS,
                                fn_key=self.FN_KEYS.get(keycode))
                if btn.is_modifier:
                    btn.clicked.connect(lambda checked, b=btn: self._on_modifier_clicked(b))
                else:
                    btn.pressed.connect(lambda b=btn: self._on_key_pressed(b))
                    btn.released.connect(lambda b=btn: self._on_key_released(b))
                self._container.place(btn, x_offset + x * stretch, row_idx,
                                      width * stretch, height)
                self.buttons.append(btn)

        return full_width

    def set_scale(self, factor: float):
        """Scale the suggestion bar height with the window."""
        self._current_scale = factor
        self._suggestion_bar.setFixedHeight(int(self.SUGGESTION_BAR_HEIGHT * factor))
        self._fit_labels()

    def _fit_labels(self):
        """Size labels from the actual key size so small keyboards stay readable."""
        if not self._container:
            return
        area = self._container
        key = min(area.row_h, area.unit_w) - area.gap
        px = max(8, int(key * self.LABEL_RATIO))
        bar_px = max(8, int(self._suggestion_bar.height() * 0.5))
        for btn in self.buttons:
            self._set_pixel_size(btn, px)
        for btn in self.suggestion_buttons + [self.add_word_button]:
            self._set_pixel_size(btn, bar_px)

    @staticmethod
    def _set_pixel_size(widget, px: int):
        font = widget.font()
        if font.pixelSize() != px:
            font.setPixelSize(px)
            widget.setFont(font)

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

        if keycode == ecodes.KEY_FN:
            self.fn_active = not self.fn_active
            self._update_modifier_state(button, self.fn_active)
            self._update_all_labels()
            return

        if keycode in self.STICKY_MODIFIERS:
            is_active = self.emitter.toggle_modifier(keycode)
            self._update_modifier_state(button, is_active)

    def _on_key_pressed(self, button: KeyButton):
        """Send key-down for a regular key."""
        if button.normal_label.isalpha() and len(button.normal_label) == 1:
            apply_shift = self.shift_active != self.caps_active
        else:
            apply_shift = self.shift_active

        sent = button.current_keycode()
        label = button.shifted_label if apply_shift else button.normal_label
        is_char = len(label) == 1 and button.normal_label != button.shifted_label
        typed = label if is_char and sent == button.keycode else None
        modified = any(self.emitter.is_modifier_active(k) for k in self.STICKY_MODIFIERS)
        self._press_state[button.keycode] = (typed, time.monotonic(), modified, sent)

        self.emitter.key_down(sent, with_shift=apply_shift)

    def _on_key_released(self, button: KeyButton):
        """Send key-up for a regular key, then clear one-shot modifiers."""
        state = self._press_state.get(button.keycode)
        self.emitter.key_up(state[3] if state else button.keycode)
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
        typed, pressed_at, modified, _ = state
        repeated = time.monotonic() - pressed_at >= self.REPEAT_GUARD_SECONDS
        word = self.current_word

        if keycode in self.WORD_BREAK_KEYS:
            if word:
                self._word_list.record_use(word)
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
            if word:
                self._word_list.record_use(word)
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

        word = self.current_word
        can_add = bool(word) and len(word) >= 2 and not self._word_list.is_known(word)
        self.add_word_button.word = word if can_add else ''
        self.add_word_button.setText(f'+ {word}' if can_add else '')
        self.add_word_button.setVisible(can_add)

    def _on_add_word_clicked(self):
        """Save the word being typed so it gets suggested from now on."""
        if self.add_word_button.word:
            self._word_list.add_word(self.add_word_button.word)
            self._update_suggestions()

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
        self._word_list.record_use(button.word)

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
            if btn.keycode in self.STICKY_MODIFIERS:
                is_active = self.emitter.is_modifier_active(btn.keycode)
                self._update_modifier_state(btn, is_active)

    def _update_all_labels(self):
        """Update all button labels based on current shift/caps state."""
        for btn in self.buttons:
            if btn.normal_label.isalpha() and len(btn.normal_label) == 1:
                show_shifted = self.shift_active != self.caps_active
            else:
                show_shifted = self.shift_active
            btn.update_label(show_shifted, self.fn_active)

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
