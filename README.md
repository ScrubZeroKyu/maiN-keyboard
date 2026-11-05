# MaiN_Keyboard

An on-screen keyboard for KDE Plasma / Wayland that actually works.

## Why MaiN_Keyboard?

Many on-screen keyboards have issues under Wayland:
- Focus gets stolen from text fields
- Keystrokes don't arrive
- Complicated configuration required

**MaiN_Keyboard solves these problems** through:
- XWayland mode with special window flags
- Kernel-level keyboard input via uinput
- No focus stealing - text fields stay active

## Features

- **Works under Wayland** - Uses uinput for reliable keyboard input
- **No focus stealing** - Text fields remain active while typing
- **Dark design** - Modern iOS-style buttons with 3D shadow effect
- **Adjustable opacity** - Set transparency (50%-100%) via tray menu
- **Multiple layouts** - German (DE), English UK, English US
- **Word suggestions** - Tap a suggestion to finish the word. After a space it guesses the next word from the words you usually type together. Words you use often come first; tap **+ word** to add a new one (English list of 20,000 words, small German list)
- **Key repeat** - Hold a key to repeat it, using KDE's repeat settings
- **Knows when you move to another text field** - Suggestions start fresh after a click or touch outside the keyboard. Apps that support accessibility (GTK, Qt/KDE, Firefox) also report the text before the cursor, so suggestions stay right after clicking around, and password fields are never learned from (needs `python-gobject` and `at-spi2-core`)
- **Options** - ⚙ button in the title bar (or tray menu): layout, opacity, number of suggestions, next-word guessing, remove added words, block words you never want suggested
- **Resizable** - Drag the white-outlined edge or a corner to resize (down to half the default size)
- **Monitor switching** - Move active window between monitors
- **System Tray** - Minimizes to taskbar
- **Saves settings** - Remembers size, layout, and opacity
- **Movable** - Window can be freely positioned

## Screenshot

![MaiN_Keyboard](https://i.ibb.co/RTxm3ypq/Bildschirmfoto-20260127-034035.png)

## Installation

### Arch Linux / CachyOS / Manjaro (AUR)

```bash
paru -S main-keyboard-git   # CachyOS
yay -S main-keyboard-git    # Arch/Manjaro
```

> [!IMPORTANT]
> After installation, add your user to the `input` group and then log out and back in:
> ```bash
> sudo usermod -aG input $USER
> ```

### Manual Installation

**Install dependencies:**
```bash
sudo pacman -S python-pyqt6 python-evdev
```

**Clone repository:**
```bash
git clone https://github.com/cachyOSMaiN/maiN-keyboard.git
cd main-keyboard
```

**Install:**
```bash
sudo make install
```

**Or run directly:**
```bash
python3 main.py
```

### uinput Permission

MaiN_Keyboard requires access to `/dev/uinput`. If needed:

```bash
# Set permission once
sudo setfacl -m u:$USER:rw /dev/uinput

# Or permanently via udev rule
echo 'KERNEL=="uinput", MODE="0666"' | sudo tee /etc/udev/rules.d/99-uinput.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

## Usage

| Action | Description |
|--------|-------------|
| **Drag title bar** | Move window |
| **DE / UK / US** | Switch keyboard layout |
| **Drag window edge or corner** | Resize keyboard |
| **<- / ->** | Move active window to other monitor |
| **✕** | Minimize to system tray |
| **Tray icon left-click** | Show/hide keyboard |
| **Tray icon right-click** | Menu with layout selection |

## Technical Details

- **GUI:** PyQt6
- **Input:** python-evdev (uinput)
- **Display:** XWayland (for focus handling)
- **Config:** `~/.config/osk/settings.json`

## License

MIT License

## Credits

The English word list (`words/en.txt`) comes from [FrequencyWords](https://github.com/hermitdave/FrequencyWords) by Hermit Dave (OpenSubtitles 2018), licensed [CC-BY-SA-4.0](https://creativecommons.org/licenses/by-sa/4.0/). Regenerate it with `python3 tools/build_wordlists.py`.

## Author

MaiN

---

**Keywords:** on-screen keyboard Linux, virtual keyboard KDE Plasma, Wayland on-screen keyboard, OSK Wayland, touchscreen keyboard Linux, software keyboard KDE, on-screen keyboard Python, uinput keyboard Linux, XWayland keyboard, on-screen keyboard Arch Linux, on-screen keyboard CachyOS, on-screen keyboard Manjaro, virtual keyboard Wayland focus, accessibility keyboard KDE
