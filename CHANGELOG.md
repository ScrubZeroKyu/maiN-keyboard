# Changelog

## v1.3.0 (2026-11-06)

A big step towards the Windows 10/11 On-Screen Keyboard.

### Added
- **English UK and US layouts** with layout switching (DE stays available)
- **Windows-style keys (UK/US)**: Esc, Fn, Win, right Ctrl, Menu key, and a side block with Home, End, Insert, Del, PrtScn, ScrLk, Pause (plus PgUp/PgDn on US)
- **Windows-style arrow keys**: ↑ above ↓ next to right Shift; UK Enter spans two rows
- **Fn key**: turns the number row into F1-F12 until tapped again
- **Sticky Win key**: tap Win then a key for a shortcut, tap twice to open the launcher
- **Keycap labels**: shifted symbols shown small in the key corner (`!` above `1`), word keys left-aligned, labels shrink to fit
- **Word suggestions** above the keys, with a 20,000-word English list (FrequencyWords, CC-BY-SA-4.0) and a small German list
- **Text chaining**: after a space, the bar guesses the next word from words you usually type together
- **Learns your words**: words you use often come first; **+ word** adds a new word
- **Fresh suggestions in a new text field**: after a click or touch outside the keyboard, and through accessibility (AT-SPI) in GTK, Qt/KDE and Firefox apps; password fields are never learned from
- **Options window**: layout, opacity, number of suggestions, next-word guessing, click/accessibility tracking, forget learned words, remove added words, block words
- **Options key** under ScrLk and Pause (UK/US), like on Windows
- **Key repeat**: hold a key to repeat it, using KDE's repeat settings
- **Drag-to-resize**: drag any edge or corner (down to half the default size); the size is saved
- **Game support**: keys can be clicked while a fullscreen game (e.g. Wine/Proton) has grabbed the mouse

### Changed
- **English US is now the default layout** (a layout you already picked is kept)
- Flat square keys with tight spacing; pressed keys turn navy
- White title bar with square corners
- Key press sends key-down on press and key-up on release
- Labels are sized from the actual key size

### Removed
- S/M/B size buttons (replaced by drag-to-resize)
- Monitor switch buttons (`<-` / `->`) and the gear button in the title bar

### Fixed
- DE layout: Y and Z were swapped
- `make install` failed with "missing separator"
- PKGBUILD did not install the UK/US layouts
- Crash on quit
- A click could linger as a key press when the cursor was not on a key

### Known limitations
- Some fullscreen games (especially native Wayland ones, or games that take exclusive control of the mouse) can cover the keyboard or stop clicks reaching it
- The DE layout has no side block, so it has no Options key; use the tray menu

## v1.2.0 (2026-01-27)

### Added
- **New dark design**: iOS-style buttons with 3D shadow effect and rounded corners
- **Opacity setting**: Adjustable transparency (50%-100%) via system tray menu
- **Window move indicator**: Icon between monitor switch buttons for better UX

### Changed
- Darker background color (#131315) for better contrast
- Improved button styling with bottom shadow for depth
- Adjusted default keyboard position (58px from bottom)
- Tray menu now in English

## v1.1.0 (2026-01-26)

### Added
- **Single instance enforcement**: The application now prevents multiple instances from running simultaneously. If you try to launch MaiN_Keyboard while it's already running, it will display a message and exit gracefully.

## v1.0.0 (2026-01-26)

### Initial Release
- On-screen keyboard for KDE Plasma / Wayland
- German QWERTZ layout with umlauts
- Scalable interface (S/M/B sizes)
- Monitor switching functionality
- System tray integration
- No focus stealing from text fields
- Settings persistence
