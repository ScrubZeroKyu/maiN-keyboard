# Maintainer: MaiN
pkgname=main-keyboard-git
pkgver=1.0.0
pkgrel=2
pkgdesc="On-screen keyboard for KDE/Wayland that actually works"
arch=('any')
url="https://github.com/cachyOSMaiN/maiN-keyboard"
license=('MIT')
depends=('python' 'python-pyqt6' 'python-evdev')
optdepends=('python-gobject: follow text fields through accessibility' 'at-spi2-core: follow text fields through accessibility')
makedepends=('git')
provides=('main-keyboard')
conflicts=('main-keyboard')
install=main-keyboard.install
source=("git+$url.git")
sha256sums=('SKIP')

pkgver() {
    cd "$srcdir/maiN-keyboard"
    printf "r%s.%s" "$(git rev-list --count HEAD)" "$(git rev-parse --short HEAD)"
}

package() {
    cd "$srcdir/maiN-keyboard"

    # Install Python files
    install -Dm755 main.py "$pkgdir/usr/share/$pkgname/main.py"
    install -Dm644 keyboard.py "$pkgdir/usr/share/$pkgname/keyboard.py"
    install -Dm644 input_emitter.py "$pkgdir/usr/share/$pkgname/input_emitter.py"
    install -Dm644 suggestions.py "$pkgdir/usr/share/$pkgname/suggestions.py"
    install -Dm644 options.py "$pkgdir/usr/share/$pkgname/options.py"
    install -Dm644 focus_watch.py "$pkgdir/usr/share/$pkgname/focus_watch.py"
    install -Dm644 layouts/__init__.py "$pkgdir/usr/share/$pkgname/layouts/__init__.py"
    install -Dm644 layouts/de.py "$pkgdir/usr/share/$pkgname/layouts/de.py"
    install -Dm644 layouts/uk.py "$pkgdir/usr/share/$pkgname/layouts/uk.py"
    install -Dm644 layouts/us.py "$pkgdir/usr/share/$pkgname/layouts/us.py"
    install -Dm644 layouts/common.py "$pkgdir/usr/share/$pkgname/layouts/common.py"
    install -Dm644 words/en.txt "$pkgdir/usr/share/$pkgname/words/en.txt"
    install -Dm644 words/de.txt "$pkgdir/usr/share/$pkgname/words/de.txt"

    # Install launcher script
    install -Dm755 /dev/stdin "$pkgdir/usr/bin/main-keyboard" << EOF
#!/bin/bash
cd /usr/share/$pkgname && python3 main.py "\$@"
EOF

    # Install desktop entry
    install -Dm644 /dev/stdin "$pkgdir/usr/share/applications/$pkgname.desktop" << EOF
[Desktop Entry]
Name=MaiN_Keyboard
Comment=On-screen keyboard for KDE/Wayland
Exec=main-keyboard
Icon=input-keyboard
Terminal=false
Type=Application
Categories=Utility;Accessibility;
Keywords=keyboard;tastatur;onscreen;virtuell;osk;
EOF

    # Install udev rule for uinput access
    install -Dm644 /dev/stdin "$pkgdir/usr/lib/udev/rules.d/99-$pkgname.rules" << EOF
# Allow users in input group to access uinput
KERNEL=="uinput", GROUP="input", MODE="0660"
EOF
}
