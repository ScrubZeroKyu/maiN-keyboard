"""Options window: layout, opacity, suggestions and the user's word lists."""

from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QLineEdit, QListWidget, QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette

OPACITY_LEVELS = [
    (1.0, '100%'),
    (0.9, '90%'),
    (0.8, '80%'),
    (0.7, '70%'),
    (0.6, '60%'),
    (0.5, '50%'),
]

STYLE = """
    QGroupBox {
        border: 1px solid #3a3a3c;
        border-radius: 6px;
        margin-top: 14px;
        padding: 8px;
        font-weight: bold;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 8px;
        color: #8e8e93;
    }
    QLabel, QCheckBox {
        color: #ffffff;
    }
    QPushButton {
        background-color: #4a4a4c;
        color: #ffffff;
        border: none;
        border-radius: 4px;
        padding: 5px 12px;
    }
    QPushButton:hover {
        background-color: #5a5a5c;
    }
    QPushButton:pressed {
        background-color: #1f3a70;
    }
"""


def dark_palette() -> QPalette:
    """Dark colors for the standard widgets (keeps their arrows and checkmarks)."""
    palette = QPalette()
    colors = {
        QPalette.ColorRole.Window: '#1c1c1e',
        QPalette.ColorRole.WindowText: '#ffffff',
        QPalette.ColorRole.Base: '#2c2c2e',
        QPalette.ColorRole.AlternateBase: '#3a3a3c',
        QPalette.ColorRole.Text: '#ffffff',
        QPalette.ColorRole.PlaceholderText: '#8e8e93',
        QPalette.ColorRole.Button: '#3a3a3c',
        QPalette.ColorRole.ButtonText: '#ffffff',
        QPalette.ColorRole.Highlight: '#1f3a70',
        QPalette.ColorRole.HighlightedText: '#ffffff',
    }
    for role, color in colors.items():
        palette.setColor(role, QColor(color))
    return palette


class OptionsDialog(QDialog):
    """
    Changes apply right away. `main_window` is the VirtualKeyboard; its
    keyboard widget owns the word list being edited.
    """

    def __init__(self, main_window, layout_names: dict[str, str]):
        super().__init__(None)
        self.main_window = main_window
        self.setWindowTitle('MaiN_Keyboard Options')
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        self.setPalette(dark_palette())
        self.setStyleSheet(STYLE)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_general(layout_names))
        layout.addWidget(self._build_suggestions())

        words_row = QHBoxLayout()
        words_row.addWidget(self._build_user_words())
        words_row.addWidget(self._build_blocked_words())
        layout.addLayout(words_row)

        close_btn = QPushButton('Close')
        close_btn.clicked.connect(self.close)
        bottom = QHBoxLayout()
        bottom.addStretch()
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

        # With a style sheet set, children don't pick up the dialog's palette
        for child in self.findChildren(QWidget):
            child.setPalette(self.palette())

        self.refresh()

    @property
    def keyboard(self):
        return self.main_window.keyboard

    # --- Sections ---

    def _build_general(self, layout_names: dict[str, str]) -> QGroupBox:
        box = QGroupBox('Keyboard')
        form = QFormLayout(box)

        self.layout_combo = QComboBox()
        for layout_id, name in layout_names.items():
            self.layout_combo.addItem(name, layout_id)
        self.layout_combo.currentIndexChanged.connect(
            lambda: self.main_window.set_layout(self.layout_combo.currentData()))
        form.addRow('Layout', self.layout_combo)

        self.opacity_combo = QComboBox()
        for value, name in OPACITY_LEVELS:
            self.opacity_combo.addItem(name, value)
        self.opacity_combo.currentIndexChanged.connect(
            lambda: self.main_window.set_opacity(self.opacity_combo.currentData()))
        form.addRow('Opacity', self.opacity_combo)
        return box

    def _build_suggestions(self) -> QGroupBox:
        box = QGroupBox('Suggestions')
        form = QFormLayout(box)

        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, self.keyboard.MAX_SUGGESTIONS)
        self.count_spin.valueChanged.connect(self.main_window.set_suggestion_count)
        form.addRow('Number of suggestions', self.count_spin)

        self.next_word_check = QCheckBox('Suggest the next word after a space')
        self.next_word_check.toggled.connect(self.main_window.set_next_word)
        form.addRow(self.next_word_check)

        self.click_reset_check = QCheckBox('Start a new word when I click or touch outside the keyboard')
        self.click_reset_check.toggled.connect(self.main_window.set_click_reset)
        form.addRow(self.click_reset_check)

        self.a11y_check = QCheckBox('Follow text fields through accessibility (AT-SPI)')
        self.a11y_check.setToolTip(
            'Apps report which text field is active and the text before the cursor,\n'
            'so suggestions stay right after clicking around. Password fields are\n'
            'never learned from. Qt/KDE apps opened before this was on need a restart.')
        self.a11y_check.toggled.connect(self.main_window.set_accessibility)
        form.addRow(self.a11y_check)

        forget_btn = QPushButton('Forget learned word usage')
        forget_btn.setToolTip('Reset how often you used each word and which words you type together')
        forget_btn.clicked.connect(self._on_forget)
        form.addRow(forget_btn)
        return box

    def _build_user_words(self) -> QGroupBox:
        box = QGroupBox('Your added words')
        col = QVBoxLayout(box)
        self.user_list = QListWidget()
        self.user_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        col.addWidget(self.user_list)
        remove_btn = QPushButton('Remove')
        remove_btn.clicked.connect(self._on_remove_user_words)
        col.addWidget(remove_btn)
        return box

    def _build_blocked_words(self) -> QGroupBox:
        box = QGroupBox('Never suggest')
        col = QVBoxLayout(box)
        self.blocked_list = QListWidget()
        self.blocked_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        col.addWidget(self.blocked_list)

        add_row = QHBoxLayout()
        self.block_edit = QLineEdit()
        self.block_edit.setPlaceholderText('word')
        self.block_edit.returnPressed.connect(self._on_block)
        add_row.addWidget(self.block_edit)
        add_btn = QPushButton('Add')
        add_btn.clicked.connect(self._on_block)
        add_row.addWidget(add_btn)
        col.addLayout(add_row)

        remove_btn = QPushButton('Remove')
        remove_btn.clicked.connect(self._on_unblock)
        col.addWidget(remove_btn)
        return box

    # --- State ---

    def refresh(self):
        """Show the current settings and word lists."""
        for combo, value in ((self.layout_combo, self.keyboard.current_layout),
                             (self.opacity_combo, self.main_window.windowOpacity())):
            combo.blockSignals(True)
            idx = combo.findData(value)
            if idx < 0 and combo is self.opacity_combo:
                # windowOpacity() may come back slightly rounded
                idx = min(range(combo.count()),
                          key=lambda i: abs(combo.itemData(i) - value))
            combo.setCurrentIndex(idx)
            combo.blockSignals(False)

        self.count_spin.blockSignals(True)
        self.count_spin.setValue(self.keyboard.suggestion_count)
        self.count_spin.blockSignals(False)
        self.next_word_check.blockSignals(True)
        self.next_word_check.setChecked(self.keyboard.next_word_enabled)
        self.next_word_check.blockSignals(False)

        for check, value in ((self.click_reset_check, self.main_window.click_reset_enabled),
                             (self.a11y_check, self.main_window.accessibility_enabled)):
            check.blockSignals(True)
            check.setChecked(value)
            check.blockSignals(False)

        words = self.keyboard.word_list
        self.user_list.clear()
        self.user_list.addItems(words.user_words())
        self.blocked_list.clear()
        self.blocked_list.addItems(words.blocked_words())

    def _selected(self, widget: QListWidget) -> list[str]:
        return [item.text() for item in widget.selectedItems()]

    def _on_remove_user_words(self):
        for word in self._selected(self.user_list):
            self.keyboard.word_list.remove_user_word(word)
        self._changed()

    def _on_block(self):
        for word in self.block_edit.text().split():
            self.keyboard.word_list.block_word(word)
        self.block_edit.clear()
        self._changed()

    def _on_unblock(self):
        for word in self._selected(self.blocked_list):
            self.keyboard.word_list.unblock_word(word)
        self._changed()

    def _on_forget(self):
        answer = QMessageBox.question(
            self, 'Forget learned usage',
            'Forget how often you used each word and which words you type together?')
        if answer == QMessageBox.StandardButton.Yes:
            self.keyboard.word_list.forget_learning()
            self._changed()

    def _changed(self):
        self.keyboard.refresh_suggestions()
        self.refresh()
