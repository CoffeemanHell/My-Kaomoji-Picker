from dataclasses import dataclass


@dataclass
class Config:
    # Language
    # Available: "en" (English), "tr" (Turkish)
    # To add a new language, create a new JSON file in locales/ directory
    # Example: locales/de.json for German
    language: str = "en"

    # Recents
    max_recents: int = 15

    # Window dimensions
    min_width: int = 250
    min_height: int = 300
    default_width: int = 300
    default_height: int = 380

    # Category bar
    category_bar_height: int = 60
    category_bar_margin: int = 5
    category_bar_spacing: int = 8

    # Layout settings
    layout_margin: int = 8
    layout_spacing: int = 6
    content_spacing: int = 6
    list_item_spacing: int = 3

    # Border and styling
    border_radius: int = 10
    border_width: int = 2
    item_border_radius: int = 4
    item_padding: int = 6
    button_padding_h: int = 12
    button_padding_v: int = 6

    # Resize settings
    resize_edge_threshold: int = 10

    # Behavior settings
    auto_close_on_copy: bool = True
    show_notifications: bool = True
    close_on_focus_loss: bool = True

    # Timeouts
    clipboard_timeout: float = 1.0
    notification_timeout: float = 1.0

    # System commands
    clipboard_command: str = "wl-copy"
    notification_command: str = "notify-send"
