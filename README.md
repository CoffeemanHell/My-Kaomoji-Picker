# ╰( ͡° ͜ʖ ͡° )つ──☆*:・ﾟ My Kaomoji Picker
<img width="477" height="448" alt="resim" src="https://github.com/user-attachments/assets/cffb862b-d69e-4be0-818a-fb6eb1d491f6" />

### System
- **Python 3.14+**

### Dependencies
- `PyQt6` - GUI framework
- `wl-clipboard` - Wayland clipboard utilities (provides `wl-copy`)
- `libnotify` - Desktop notifications (provides `notify-send`)

## (ﾉ･ｪ･)ﾉ Installation

### 1. Install System Dependencies

**Fedora:**
```bash
sudo dnf install python3-pyqt6 wl-clipboard libnotify
```

### 2. Clone/Copy the Project

The project structure should be:
```
~/kaomoji-picker/
├── locales/
│   ├── en.json
│   └── tr.json
├── config.py
├── i18n.py
├── kaomoji-picker.py
└── kaomojis.json
```

### Running the Application

```bash
python ~/kaomoji-picker/kaomoji-picker.py
```

### Creating a Keyboard Shortcut

**KDE Plasma (System Settings → Shortcuts → Custom Shortcuts):**
- Action: Command/URL
- Command: `python3 ~/kaomoji-picker/kaomoji-picker.py`
- Trigger: `Meta+K` (or your preference)

## ( . .)φ Contributing

Feel free to:
- Add more kaomojis to `kaomojis.json`
- Fork and customize for your needs

## ( . .)φ License & Attribution

### Kaomoji Data

The kaomoji data in `kaomojis.json` is sourced from:
- **Project**: [KaomojiList](https://github.com/Aptivi-Analytics/KaomojiList)
- **License**: GNU Free Documentation License v1.3

Permission is granted to copy, distribute and/or modify this document under the terms of the GNU Free Documentation License, Version 1.3 or any later version published by the Free Software Foundation; with no Invariant Sections, no Front-Cover Texts, and no Back-Cover Texts. A copy of the license is included in the file LICENSE-GFDL.

---

**Enjoy expressing yourself with kaomojis!** ヽ(•‿•)ノ
