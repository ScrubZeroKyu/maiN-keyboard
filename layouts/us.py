"""US QWERTY keyboard layout definition."""

from evdev import ecodes

from layouts.common import (
    BOTTOM_ROW, COMMON_WIDE_KEYS, FN_KEYS, MODIFIER_KEYS, SIDE_BLOCK, SIDE_WIDE_KEYS,
)

# Key definitions: (normal_char, shift_char, keycode)
# For special keys, normal_char is the display label.
# Every row is 15.5 units wide so the arrow keys line up.

LAYOUT = [
    # Row 1: Number row
    [
        ('Esc', 'Esc', ecodes.KEY_ESC),
        ('`', '~', ecodes.KEY_GRAVE),
        ('1', '!', ecodes.KEY_1),
        ('2', '@', ecodes.KEY_2),
        ('3', '#', ecodes.KEY_3),
        ('4', '$', ecodes.KEY_4),
        ('5', '%', ecodes.KEY_5),
        ('6', '^', ecodes.KEY_6),
        ('7', '&', ecodes.KEY_7),
        ('8', '*', ecodes.KEY_8),
        ('9', '(', ecodes.KEY_9),
        ('0', ')', ecodes.KEY_0),
        ('-', '_', ecodes.KEY_MINUS),
        ('=', '+', ecodes.KEY_EQUAL),
        ('⌫', '⌫', ecodes.KEY_BACKSPACE),
    ],
    # Row 2: QWERTY top row
    [
        ('Tab', 'Tab', ecodes.KEY_TAB),
        ('q', 'Q', ecodes.KEY_Q),
        ('w', 'W', ecodes.KEY_W),
        ('e', 'E', ecodes.KEY_E),
        ('r', 'R', ecodes.KEY_R),
        ('t', 'T', ecodes.KEY_T),
        ('y', 'Y', ecodes.KEY_Y),
        ('u', 'U', ecodes.KEY_U),
        ('i', 'I', ecodes.KEY_I),
        ('o', 'O', ecodes.KEY_O),
        ('p', 'P', ecodes.KEY_P),
        ('[', '{', ecodes.KEY_LEFTBRACE),
        (']', '}', ecodes.KEY_RIGHTBRACE),
        ('\\', '|', ecodes.KEY_BACKSLASH),
    ],
    # Row 3: Home row
    [
        ('Caps', 'Caps', ecodes.KEY_CAPSLOCK),
        ('a', 'A', ecodes.KEY_A),
        ('s', 'S', ecodes.KEY_S),
        ('d', 'D', ecodes.KEY_D),
        ('f', 'F', ecodes.KEY_F),
        ('g', 'G', ecodes.KEY_G),
        ('h', 'H', ecodes.KEY_H),
        ('j', 'J', ecodes.KEY_J),
        ('k', 'K', ecodes.KEY_K),
        ('l', 'L', ecodes.KEY_L),
        (';', ':', ecodes.KEY_SEMICOLON),
        ("'", '"', ecodes.KEY_APOSTROPHE),
        ('Enter', 'Enter', ecodes.KEY_ENTER),
    ],
    # Row 4: Bottom letter row
    [
        ('Shift', 'Shift', ecodes.KEY_LEFTSHIFT),
        ('z', 'Z', ecodes.KEY_Z),
        ('x', 'X', ecodes.KEY_X),
        ('c', 'C', ecodes.KEY_C),
        ('v', 'V', ecodes.KEY_V),
        ('b', 'B', ecodes.KEY_B),
        ('n', 'N', ecodes.KEY_N),
        ('m', 'M', ecodes.KEY_M),
        (',', '<', ecodes.KEY_COMMA),
        ('.', '>', ecodes.KEY_DOT),
        ('/', '?', ecodes.KEY_SLASH),
        ('↑', '↑', ecodes.KEY_UP),
        ('Shift', 'Shift', ecodes.KEY_RIGHTSHIFT),
    ],
    # Row 5: Bottom row with space
    BOTTOM_ROW,
]

# Keys that should have wider buttons (units; 1.0 if missing)
WIDE_KEYS = {
    **COMMON_WIDE_KEYS,
    ecodes.KEY_TAB: 1.5,
    ecodes.KEY_BACKSLASH: 2.0,
    ecodes.KEY_ENTER: 2.75,
    ecodes.KEY_LEFTSHIFT: 2.5,
    ecodes.KEY_RIGHTSHIFT: 2.0,
}
