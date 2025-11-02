#!/usr/bin/env python3
import sys
import subprocess
import logging
from pathlib import Path
from typing import override

from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QFrame,
    QListWidget,
    QListWidgetItem,
    QHBoxLayout,
    QScrollArea,
    QPushButton,
)
from PyQt6.QtCore import Qt, QSettings, pyqtSignal, QObject, QEvent
from PyQt6.QtGui import QPalette, QColor, QCloseEvent, QKeyEvent, QMouseEvent

from config import Config
from i18n import init_i18n, t

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)
config = Config()
init_i18n(config.language)

RECENTS_KEY = "__recents__"


def hex_color(qcolor: QColor | None) -> str:
    if qcolor is None:
        return "#000000"
    return qcolor.name()


class CategoryBar(QScrollArea):
    categoryClicked = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFixedHeight(config.category_bar_height)

        self.container = QWidget()
        self.layout: QHBoxLayout = QHBoxLayout(self.container)
        self.layout.setContentsMargins(
            config.category_bar_margin,
            config.category_bar_margin,
            config.category_bar_margin,
            config.category_bar_margin,
        )
        self.layout.setSpacing(config.category_bar_spacing)
        self.setWidget(self.container)

        app = QApplication.instance()
        palette = app.palette() if app else QPalette()

        bg = hex_color(palette.color(QPalette.ColorRole.Window))
        button_text = hex_color(palette.color(QPalette.ColorRole.ButtonText))
        hover_text = hex_color(palette.color(QPalette.ColorRole.HighlightedText))
        active_border = hex_color(palette.color(QPalette.ColorRole.Highlight))
        border_color = hex_color(palette.color(QPalette.ColorRole.Mid))

        style = f"""
            QScrollArea {{
                background-color: {bg};
                border: none;
                border-bottom: 1px solid {border_color};
            }}
            QPushButton {{
                background-color: transparent;
                color: {button_text};
                border: none;
                padding: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                color: {hover_text};
            }}
            QPushButton[active="true"] {{
                color: {hover_text};
                border-bottom: 2px solid {active_border};
            }}
        """
        self.setStyleSheet(style)

        self.buttons: dict[str, QPushButton] = {}
        self.active_category: str | None = None

    def update_categories(self, categories: list[str]) -> None:
        btn = QPushButton(t("recents"))
        btn.clicked.connect(lambda: self.set_active_category(RECENTS_KEY))
        self.layout.addWidget(btn)
        self.buttons[RECENTS_KEY] = btn

        for cat in categories:
            btn = QPushButton(t(f"cat_{cat}", cat))
            btn.clicked.connect(lambda _, c=cat: self.set_active_category(c))
            self.layout.addWidget(btn)
            self.buttons[cat] = btn

        self.set_active_category(RECENTS_KEY)

    def set_active_category(self, category: str) -> None:
        if self.active_category in self.buttons:
            self.buttons[self.active_category].setProperty("active", False)
            style = self.buttons[self.active_category].style()
            if style:
                style.polish(self.buttons[self.active_category])

        self.active_category = category
        if category in self.buttons:
            self.buttons[category].setProperty("active", True)
            style = self.buttons[category].style()
            if style:
                style.polish(self.buttons[category])

        self.categoryClicked.emit(category)


class KaomojiPicker(QWidget):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("KaomojiPicker", "AppSettings")
        self.json_file = Path(__file__).parent / "kaomojis.json"

        self._cached_data: list[dict] | None = None

        self.categories = self._load_category_names()

        self.recents_dict: dict[str, int] = self.settings.value(
            "recent_kaomojis_dict", {}, type=dict
        )
        if not isinstance(self.recents_dict, dict):
            self.recents_dict = {}

        old_recents = self.settings.value("recent_kaomojis", None, type=list)
        if old_recents:
            for kaomoji in old_recents:
                if kaomoji not in self.recents_dict:
                    self.recents_dict[kaomoji] = 1
            self.settings.remove("recent_kaomojis")
            self.settings.setValue("recent_kaomojis_dict", self.recents_dict)

        self.current_category: str | None = None

        self.resizing = False
        self.resize_edge: Qt.CursorShape | None = None
        self.start_pos = None
        self.start_geo = None

        self.init_ui()
        self.restore_pos()

    def _load_all_data(self) -> list[dict[str, object]]:
        if self._cached_data is not None:
            return self._cached_data if self._cached_data is not None else []

        if not self.json_file.exists():
            self._create_default()
            return []

        try:
            import json

            with open(self.json_file, "r", encoding="utf-8") as f:
                self._cached_data = json.load(f)
            return self._cached_data if self._cached_data is not None else []
        except Exception as e:
            logger.error(f"JSON yüklenemedi: {e}")
            return []

    def _load_category_names(self) -> list[str]:
        data = self._load_all_data()
        if not data:
            return []

        cats = []
        for group in data:
            for cat in group.get("categories", []):
                name = cat.get("name")
                if name and name not in ["Positive", "Negative"]:
                    cats.append(name)
        return cats

    def _load_category_data(self, category_name: str) -> list[str]:
        data = self._load_all_data()

        for group in data:
            for cat in group.get("categories", []):
                if cat.get("name") == category_name:
                    return cat.get("emoticons", [])

        return []

    def init_ui(self) -> None:
        self.setWindowTitle(t("window_title"))
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        app = QApplication.instance()
        palette = app.palette() if app else QPalette()

        window_bg = hex_color(palette.color(QPalette.ColorRole.Window))
        frame_border = hex_color(palette.color(QPalette.ColorRole.Mid))
        list_bg = hex_color(palette.color(QPalette.ColorRole.Base))
        item_bg = hex_color(palette.color(QPalette.ColorRole.Button))
        item_text = hex_color(palette.color(QPalette.ColorRole.ButtonText))
        item_hover_text = hex_color(palette.color(QPalette.ColorRole.HighlightedText))
        highlight = hex_color(palette.color(QPalette.ColorRole.Highlight))
        text_color = hex_color(palette.color(QPalette.ColorRole.Text))

        container = QFrame(self)
        container_style = (
            f"QFrame {{ background-color: {window_bg}; "
            f"border-radius: {config.border_radius}px; "
            f"border: {config.border_width}px solid {frame_border}; }}"
        )
        container.setStyleSheet(container_style)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(
            config.layout_margin,
            config.layout_margin,
            config.layout_margin,
            config.layout_margin,
        )
        layout.setSpacing(config.layout_spacing)

        self.category_bar = CategoryBar()
        self.category_bar.categoryClicked.connect(self.on_category_click)
        layout.addWidget(self.category_bar)

        content_layout = QVBoxLayout()
        content_layout.setSpacing(config.content_spacing)

        self.list_widget = QListWidget()
        self.list_widget.setFlow(QListWidget.Flow.LeftToRight)
        self.list_widget.setWrapping(True)
        self.list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list_widget.setSpacing(config.list_item_spacing)
        self.list_widget.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.list_widget.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)

        list_style = f"""
            QListWidget {{
                background-color: transparent;
                border: none;
                color: {text_color};
            }}
            QListWidget::item {{
                background-color: {item_bg};
                color: {item_text};
                border: 1px solid {frame_border};
                border-radius: {config.item_border_radius}px;
                padding: {config.item_padding}px;
                margin: 2px;
            }}
            QListWidget::item:hover {{
                background-color: {list_bg};
                color: {item_hover_text};
            }}
        """
        self.list_widget.setStyleSheet(list_style)
        self.list_widget.itemClicked.connect(self.on_item_click)
        content_layout.addWidget(self.list_widget)

        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.addStretch()

        self.clear_btn = QPushButton("(っ'-')╮=͟͟͞͞□")
        self.clear_btn.setToolTip(t("clear_recents_tooltip"))

        clear_btn_style = f"""
            QPushButton {{
                background-color: {item_bg};
                color: {item_text};
                border: 1px solid {frame_border};
                border-radius: {config.item_border_radius}px;
                padding: {config.button_padding_v}px {config.button_padding_h}px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {highlight};
                color: {item_hover_text};
            }}
            QPushButton:pressed {{
                background-color: {frame_border};
            }}
        """
        self.clear_btn.setStyleSheet(clear_btn_style)
        self.clear_btn.clicked.connect(self.clear_recents)
        self.clear_btn.hide()
        button_layout.addWidget(self.clear_btn)

        content_layout.addWidget(button_container)
        layout.addLayout(content_layout)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(container)

        self.category_bar.update_categories(self.categories)
        self.setMinimumSize(config.min_width, config.min_height)
        self.resize(config.default_width, config.default_height)
        self.installEventFilter(self)

    def on_category_click(self, category: str) -> None:
        self.current_category = category
        self.list_widget.clear()

        if category == RECENTS_KEY:
            sorted_items = sorted(
                self.recents_dict.items(), key=lambda x: x[1], reverse=True
            )
            sorted_items = sorted_items[: config.max_recents]

            for kaomoji, count in sorted_items:
                display_text = f"{count}x  {kaomoji}"
                item = QListWidgetItem(display_text)
                item.setData(Qt.ItemDataRole.UserRole, kaomoji)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.list_widget.addItem(item)

            self.clear_btn.setVisible(len(sorted_items) > 0)
        else:
            items = self._load_category_data(category)
            for item_text in items:
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, item_text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.list_widget.addItem(item)

            self.clear_btn.hide()

    def on_item_click(self, item: QListWidgetItem) -> None:
        kaomoji = item.data(Qt.ItemDataRole.UserRole)
        self.copy_kaomoji(kaomoji)

    def copy_kaomoji(self, kaomoji: str) -> None:
        copied = False

        try:
            process = subprocess.Popen(
                [config.clipboard_command],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            process.stdin.write(kaomoji.encode())
            process.stdin.close()
            copied = True
            logger.debug(f"{config.clipboard_command} kullanıldı (daemon mode)")
        except (OSError, FileNotFoundError) as e:
            logger.warning(f"{config.clipboard_command} başarısız: {e}")

        if not copied:
            try:
                clipboard = QApplication.clipboard()
                if clipboard:
                    clipboard.setText(kaomoji)
                    copied = True
                    logger.debug("PyQt6 clipboard kullanıldı")
            except Exception as e:
                logger.error(f"PyQt6 clipboard başarısız: {e}")

        if not copied:
            logger.error(
                "Kaomoji panoya kopyalanamadı - hem wl-copy hem PyQt6 başarısız"
            )
            return

        if config.show_notifications:
            try:
                subprocess.run(
                    [config.notification_command, t("notification_title"), kaomoji],
                    check=False,
                    timeout=config.notification_timeout,
                    capture_output=True,
                )
            except Exception as e:
                logger.debug(f"Bildirim gönderilemedi: {e}")

        self.recents_dict[kaomoji] = self.recents_dict.get(kaomoji, 0) + 1

        if len(self.recents_dict) > config.max_recents:
            sorted_items = sorted(self.recents_dict.items(), key=lambda x: x[1])
            items_to_remove = sorted_items[
                : len(self.recents_dict) - config.max_recents
            ]
            for k, _ in items_to_remove:
                del self.recents_dict[k]

        self.settings.setValue("recent_kaomojis_dict", self.recents_dict)

        if config.auto_close_on_copy:
            QApplication.quit()

    def clear_recents(self) -> None:
        self.recents_dict.clear()
        self.settings.setValue("recent_kaomojis_dict", self.recents_dict)
        self.list_widget.clear()
        self.clear_btn.hide()

    @override
    def closeEvent(self, event: QCloseEvent) -> None:
        self.save_pos()
        event.accept()

    @override
    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.save_pos()
            QApplication.quit()
        elif (
            event.key() == Qt.Key.Key_Tab
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            if not self.categories:
                return

            try:
                current_index = self.categories.index(self.current_category)
            except (ValueError, AttributeError):
                current_index = 0

            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                next_index = (current_index - 1) % len(self.categories)
            else:
                next_index = (current_index + 1) % len(self.categories)

            new_category = self.categories[next_index]
            self.category_bar.set_active_category(new_category)
            self.on_category_click(new_category)

    @override
    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if (
            config.close_on_focus_loss
            and event.type() == event.Type.WindowDeactivate
            and not self.resizing
        ):
            self.save_pos()
            QApplication.quit()
        return super().eventFilter(obj, event)

    def save_pos(self) -> None:
        self.settings.setValue("pos", self.pos())
        self.settings.setValue("size", self.size())

    def restore_pos(self) -> None:
        if self.settings.contains("pos"):
            self.move(self.settings.value("pos"))
        if self.settings.contains("size"):
            self.resize(self.settings.value("size"))

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            edge = self.get_resize_edge(event.pos())
            if edge:
                self.resizing = True
                self.resize_edge = edge
                self.start_pos = event.globalPosition().toPoint()
                self.start_geo = self.geometry()

    @override
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.resizing and self.start_pos is not None and self.start_geo:
            delta = event.globalPosition().toPoint() - self.start_pos
            g = self.start_geo

            new_width = max(self.minimumWidth(), g.width() + delta.x())
            new_height = max(self.minimumHeight(), g.height() + delta.y())

            self.setGeometry(g.x(), g.y(), new_width, new_height)
        else:
            cursor = self.get_resize_edge(event.pos())
            self.setCursor(cursor if cursor else Qt.CursorShape.ArrowCursor)

    @override
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.resizing:
            self.resizing = False
            self.resize_edge = None
            self.save_pos()

    def get_resize_edge(self, pos) -> Qt.CursorShape | None:
        threshold = config.resize_edge_threshold
        rect = self.rect()
        left = pos.x() < threshold
        right = pos.x() > rect.width() - threshold
        top = pos.y() < threshold
        bottom = pos.y() > rect.height() - threshold

        if (top and left) or (bottom and right):
            return Qt.CursorShape.SizeFDiagCursor
        if (top and right) or (bottom and left):
            return Qt.CursorShape.SizeBDiagCursor
        if top or bottom:
            return Qt.CursorShape.SizeVerCursor
        if left or right:
            return Qt.CursorShape.SizeHorCursor
        return None

    def _create_default(self) -> None:
        import json

        default = [
            {
                "name": "Positive",
                "categories": [
                    {"name": "Joy", "emoticons": ["(* ^ ω ^)", "(´ ∀ `)", "٩(◕‿◕。)۶"]},
                    {"name": "Love", "emoticons": ["(ﾉ´ з `)ノ", "(♡μ_μ)"]},
                ],
            },
            {
                "name": "Negative",
                "categories": [{"name": "Anger", "emoticons": ["(#°Д°)", "(;¬_¬)"]}],
            },
        ]
        try:
            with open(self.json_file, "w", encoding="utf-8") as f:
                json.dump(default, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Varsayılan JSON oluşturulamadı: {e}")


def main() -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    picker = KaomojiPicker()
    picker.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
