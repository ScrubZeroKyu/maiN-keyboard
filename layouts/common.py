"""Parts shared by the full-size layouts (UK, US)."""

from evdev import ecodes

# Keys that toggle on tap. Ctrl/Alt/AltGr/Win stay held until the next
# regular key; Fn swaps the number row for F1-F12 until tapped again.
MODIFIER_KEYS = {
    ecodes.KEY_FN,
    ecodes.KEY_LEFTSHIFT,
    ecodes.KEY_RIGHTSHIFT,
    ecodes.KEY_LEFTCTRL,
    ecodes.KEY_RIGHTCTRL,
    ecodes.KEY_LEFTALT,
    ecodes.KEY_RIGHTALT,
    ecodes.KEY_LEFTMETA,
    ecodes.KEY_CAPSLOCK,
}

# What the number row sends while Fn is on
FN_KEYS = {
    ecodes.KEY_1: ('F1', ecodes.KEY_F1),
    ecodes.KEY_2: ('F2', ecodes.KEY_F2),
    ecodes.KEY_3: ('F3', ecodes.KEY_F3),
    ecodes.KEY_4: ('F4', ecodes.KEY_F4),
    ecodes.KEY_5: ('F5', ecodes.KEY_F5),
    ecodes.KEY_6: ('F6', ecodes.KEY_F6),
    ecodes.KEY_7: ('F7', ecodes.KEY_F7),
    ecodes.KEY_8: ('F8', ecodes.KEY_F8),
    ecodes.KEY_9: ('F9', ecodes.KEY_F9),
    ecodes.KEY_0: ('F10', ecodes.KEY_F10),
    ecodes.KEY_MINUS: ('F11', ecodes.KEY_F11),
    ecodes.KEY_EQUAL: ('F12', ecodes.KEY_F12),
}

# Bottom row, identical for UK and US (15.5 units wide)
BOTTOM_ROW = [
    ('Fn', 'Fn', ecodes.KEY_FN),
    ('Ctrl', 'Ctrl', ecodes.KEY_LEFTCTRL),
    ('Win', 'Win', ecodes.KEY_LEFTMETA),
    ('Alt', 'Alt', ecodes.KEY_LEFTALT),
    ('Space', 'Space', ecodes.KEY_SPACE),
    ('AltGr', 'AltGr', ecodes.KEY_RIGHTALT),
    ('Ctrl', 'Ctrl', ecodes.KEY_RIGHTCTRL),
    ('←', '←', ecodes.KEY_LEFT),
    ('↓', '↓', ecodes.KEY_DOWN),
    ('→', '→', ecodes.KEY_RIGHT),
    ('☰', '☰', ecodes.KEY_COMPOSE),
]

# Block to the right of the main keys
SIDE_BLOCK = [
    [('Home', 'Home', ecodes.KEY_HOME), ('End', 'End', ecodes.KEY_END)],
    [('Insert', 'Insert', ecodes.KEY_INSERT), ('Del', 'Del', ecodes.KEY_DELETE)],
    [('PrtScn', 'PrtScn', ecodes.KEY_SYSRQ), ('ScrLk', 'ScrLk', ecodes.KEY_SCROLLLOCK)],
    [('Pause', 'Pause', ecodes.KEY_PAUSE)],
]

# For layouts that have Del in the main block (US)
SIDE_BLOCK_NO_DEL = [
    [('Home', 'Home', ecodes.KEY_HOME), ('End', 'End', ecodes.KEY_END)],
    [('PgUp', 'PgUp', ecodes.KEY_PAGEUP), ('PgDn', 'PgDn', ecodes.KEY_PAGEDOWN)],
    [('Insert', 'Insert', ecodes.KEY_INSERT), ('PrtScn', 'PrtScn', ecodes.KEY_SYSRQ)],
    [('ScrLk', 'ScrLk', ecodes.KEY_SCROLLLOCK), ('Pause', 'Pause', ecodes.KEY_PAUSE)],
]

SIDE_WIDE_KEYS = {
    ecodes.KEY_HOME: 1.5, ecodes.KEY_END: 1.5,
    ecodes.KEY_INSERT: 1.5, ecodes.KEY_DELETE: 1.5,
    ecodes.KEY_SYSRQ: 1.5, ecodes.KEY_SCROLLLOCK: 1.5,
    ecodes.KEY_PAGEUP: 1.5, ecodes.KEY_PAGEDOWN: 1.5,
    ecodes.KEY_PAUSE: 3.0,
}

# Widths shared by both layouts
COMMON_WIDE_KEYS = {
    ecodes.KEY_BACKSPACE: 1.5,
    ecodes.KEY_CAPSLOCK: 1.75,
    ecodes.KEY_SPACE: 5.5,
}
