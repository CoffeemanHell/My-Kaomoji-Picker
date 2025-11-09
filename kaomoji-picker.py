#!/usr/bin/env python3
import json
import logging
import subprocess
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from textwrap import dedent
from typing import TypeAlias, override

from PyQt6.QtCore import QEvent, QObject, QSettings, Qt, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QColor, QKeyEvent, QMouseEvent, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from config import Config
from i18n import init_i18n, t


@dataclass
class EmoticonCategory:
    name: str
    emoticons: list[str]


@dataclass
class DataGroup:
    name: str
    categories: list[EmoticonCategory]


class Constants(StrEnum):
    RECENTS_KEY = "__recents__"


# Type alias'lar okunabilirliği artırır
KaomojiData: TypeAlias = list[DataGroup]
RecentsDict: TypeAlias = dict[str, int]

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)
config = Config()
init_i18n(config.language)


def hex_color(qcolor: QColor | None) -> str:
    """QColor nesnesini hex renk koduna dönüştürür."""
    return qcolor.name() if qcolor else "#000000"


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
            config.category_bar_margin, 0, config.category_bar_margin, 0
        )
        self.layout.setSpacing(config.category_bar_spacing)
        self.setWidget(self.container)

        self._setup_styles()
        self.buttons: dict[str, QPushButton] = {}
        self.active_category: str | None = None

    def _setup_styles(self) -> None:
        palette = QApplication.instance().palette()
        bg = hex_color(palette.color(QPalette.ColorRole.Window))
        button_text = hex_color(palette.color(QPalette.ColorRole.ButtonText))
        hover_text = hex_color(palette.color(QPalette.ColorRole.HighlightedText))
        active_border = hex_color(palette.color(QPalette.ColorRole.Highlight))
        border_color = hex_color(palette.color(QPalette.ColorRole.Mid))

        self.setStyleSheet(
            dedent(f"""
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
            QPushButton:hover {{ color: {hover_text}; }}
            QPushButton[active="true"] {{
                color: {hover_text};
                border-bottom: 2px solid {active_border};
            }}
        """)
        )

    def update_categories(self, categories: list[str]) -> None:
        btn = QPushButton(t("recents"))
        btn.clicked.connect(lambda: self.set_active_category(Constants.RECENTS_KEY))
        self.layout.addWidget(btn)
        self.buttons[Constants.RECENTS_KEY] = btn

        for cat in categories:
            btn = QPushButton(t(f"cat_{cat}", cat))
            btn.clicked.connect(lambda _, c=cat: self.set_active_category(c))
            self.layout.addWidget(btn)
            self.buttons[cat] = btn

        if self.buttons:
            self.set_active_category(Constants.RECENTS_KEY)

    def set_active_category(self, category: str) -> None:
        if self.active_category and (btn := self.buttons.get(self.active_category)):
            btn.setProperty("active", False)
            btn.style().polish(btn)

        self.active_category = category
        if btn := self.buttons.get(category):
            btn.setProperty("active", True)
            btn.style().polish(btn)

        self.categoryClicked.emit(category)


class KaomojiPicker(QWidget):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("KaomojiPicker", "AppSettings")
        self.json_file = Path(__file__).parent / "kaomojis.json"
        self._data: KaomojiData = self._load_all_data()
        self.categories: list[str] = self._get_category_names()
        self.recents_dict: RecentsDict = self._load_recents()
        self.current_category: str | None = None
        self.resizing = False
        self.start_pos = None
        self.start_geo = None
        self.init_ui()
        self.restore_pos()

    def _load_all_data(self) -> KaomojiData:
        if not self.json_file.exists():
            self._create_default()
        try:
            with self.json_file.open("r", encoding="utf-8") as f:
                raw_data = json.load(f)
            return [
                DataGroup(
                    name=g["name"],
                    categories=[EmoticonCategory(**c) for c in g["categories"]],
                )
                for g in raw_data
            ]
        except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error(f"Could not load or parse JSON file: {e}")
            return []

    def _load_recents(self) -> RecentsDict:
        recents = self.settings.value("recents", {}, dict)
        if not isinstance(recents, dict):
            recents = {}
        if old := self.settings.value("recent_kaomojis", None, list):
            for k in old:
                recents.setdefault(k, 1)
            self.settings.remove("recent_kaomojis")
            self.settings.setValue("recents", recents)
        return recents

    def _get_category_names(self) -> list[str]:
        return [
            c.name
            for g in self._data
            for c in g.categories
            if c.name not in ["Positive", "Negative"]
        ]

    def _load_category_data(self, category_name: str) -> list[str]:
        for group in self._data:
            for cat in group.categories:
                if cat.name == category_name:
                    return cat.emoticons
        return []

    def init_ui(self) -> None:
        self.setWindowTitle(t("window_title"))
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        palette = QApplication.instance().palette()
        window_bg = hex_color(palette.color(QPalette.ColorRole.Window))
        frame_border = hex_color(palette.color(QPalette.ColorRole.Mid))
        container = QFrame(self)
        container.setStyleSheet(
            dedent(f"""
            QFrame {{
                background-color: {window_bg};
                border-radius: {config.border_radius}px;
                border: {config.border_width}px solid {frame_border};
            }}
        """)
        )
        layout = QVBoxLayout(container)
        layout.setContentsMargins(
            config.layout_margin,
            config.layout_margin,
            config.layout_margin,
            config.layout_margin,
        )
        self.category_bar = CategoryBar()
        self.category_bar.categoryClicked.connect(self.on_category_click)
        self.list_widget = self._create_list_widget(palette)
        self.clear_btn = self._create_clear_button(palette)
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.addStretch()
        button_layout.addWidget(self.clear_btn)
        content_layout = QVBoxLayout()
        content_layout.addWidget(self.list_widget)
        content_layout.addWidget(button_container)
        layout.addWidget(self.category_bar)
        layout.addLayout(content_layout)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(container)
        self.category_bar.update_categories(self.categories)
        self.setMinimumSize(config.min_width, config.min_height)
        self.resize(config.default_width, config.default_height)
        self.installEventFilter(self)

    def _create_list_widget(self, p: QPalette) -> QListWidget:
        widget = QListWidget()
        widget.setFlow(QListWidget.Flow.LeftToRight)
        widget.setWrapping(True)
        widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        widget.setSpacing(config.list_item_spacing)
        widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        widget.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        widget.setStyleSheet(
            dedent(f"""
            QListWidget {{ background-color: transparent; border: none; }}
            QListWidget::item {{
                background-color: {hex_color(p.color(QPalette.ColorRole.Button))};
                color: {hex_color(p.color(QPalette.ColorRole.ButtonText))};
                border: 1px solid {hex_color(p.color(QPalette.ColorRole.Mid))};
                border-radius: {config.item_border_radius}px; padding: {config.item_padding}px; margin: 2px;
            }}
            QListWidget::item:hover {{
                background-color: {hex_color(p.color(QPalette.ColorRole.Base))};
                color: {hex_color(p.color(QPalette.ColorRole.HighlightedText))};
            }}
        """)
        )
        widget.itemClicked.connect(self.on_item_click)
        return widget

    def _create_clear_button(self, p: QPalette) -> QPushButton:
        btn = QPushButton("(っ'-')╮=͟͟͞͞□")
        btn.setToolTip(t("clear_recents_tooltip"))
        btn.setStyleSheet(
            dedent(f"""
            QPushButton {{
                background-color: {hex_color(p.color(QPalette.ColorRole.Button))};
                color: {hex_color(p.color(QPalette.ColorRole.ButtonText))};
                border: 1px solid {hex_color(p.color(QPalette.ColorRole.Mid))};
                border-radius: {config.item_border_radius}px;
                padding: {config.button_padding_v}px {config.button_padding_h}px; font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {hex_color(p.color(QPalette.ColorRole.Highlight))};
                color: {hex_color(p.color(QPalette.ColorRole.HighlightedText))};
            }}
        """)
        )
        btn.clicked.connect(self.clear_recents)
        btn.hide()
        return btn

    def on_category_click(self, category: str) -> None:
        self.current_category = category
        self.list_widget.clear()
        match category:
            case Constants.RECENTS_KEY:
                sorted_items = sorted(
                    self.recents_dict.items(), key=lambda x: x[1], reverse=True
                )[: config.max_recents]
                for kaomoji, count in sorted_items:
                    self._add_list_item(f"{count}x  {kaomoji}", kaomoji)
                self.clear_btn.setVisible(bool(sorted_items))
            case _:
                for item_text in self._load_category_data(category):
                    self._add_list_item(item_text, item_text)
                self.clear_btn.hide()

    def _add_list_item(self, display: str, data: str) -> None:
        item = QListWidgetItem(display)
        item.setData(Qt.ItemDataRole.UserRole, data)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.list_widget.addItem(item)

    def on_item_click(self, item: QListWidgetItem) -> None:
        if kaomoji := item.data(Qt.ItemDataRole.UserRole):
            self.copy_kaomoji(kaomoji)

    def copy_kaomoji(self, kaomoji: str) -> None:
        if not self._try_system_clipboard(kaomoji):
            try:
                QApplication.clipboard().setText(kaomoji)
            except Exception as e:
                logger.error(f"Qt clipboard also failed: {e}")
                return
        self._show_notification(kaomoji)
        self._update_recents(kaomoji)
        if config.auto_close_on_copy:
            QApplication.quit()

    def _try_system_clipboard(self, text: str) -> bool:
        try:
            subprocess.run(
                [config.clipboard_command],
                input=text,
                text=True,
                check=True,
                timeout=config.clipboard_timeout,
            )
            return True
        except (
            OSError,
            FileNotFoundError,
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
        ) as e:
            logger.warning(f"{config.clipboard_command} failed: {e}")
            return False

    def _show_notification(self, kaomoji: str) -> None:
        if config.show_notifications:
            try:
                subprocess.run(
                    [config.notification_command, t("notification_title"), kaomoji],
                    check=False,
                    timeout=config.notification_timeout,
                )
            except (OSError, FileNotFoundError, subprocess.TimeoutExpired) as e:
                logger.debug(f"Could not send notification: {e}")

    def _update_recents(self, kaomoji: str) -> None:
        self.recents_dict[kaomoji] = self.recents_dict.get(kaomoji, 0) + 1
        self.settings.setValue("recents", self.recents_dict)

    def clear_recents(self) -> None:
        self.recents_dict.clear()
        self.settings.setValue("recents", self.recents_dict)
        self.list_widget.clear()
        self.clear_btn.hide()

    @override
    def closeEvent(self, event: QCloseEvent) -> None:
        self.save_pos()
        event.accept()

    @override
    def keyPressEvent(self, event: QKeyEvent) -> None:
        match (event.key(), event.modifiers()):
            case (Qt.Key.Key_Escape, _):
                self.close()
            case ((Qt.Key.Key_Q | Qt.Key.Key_W), m) if (
                m & Qt.KeyboardModifier.ControlModifier
            ):
                self.close()
            case (Qt.Key.Key_Tab, m) if m & Qt.KeyboardModifier.ControlModifier:
                self._handle_tab_navigation(
                    reverse=bool(m & Qt.KeyboardModifier.ShiftModifier)
                )

    def _handle_tab_navigation(self, reverse: bool = False) -> None:
        if not self.categories:
            return
        try:
            current_index = self.categories.index(self.current_category)
        except (ValueError, AttributeError):
            current_index = -1
        next_index = (current_index + (-1 if reverse else 1)) % len(self.categories)
        new_category = self.categories[next_index]
        self.category_bar.set_active_category(new_category)

    @override
    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if (
            config.close_on_focus_loss
            and event.type() == QEvent.Type.WindowDeactivate
            and not self.resizing
        ):
            self.close()
        return super().eventFilter(obj, event)

    def save_pos(self) -> None:
        self.settings.setValue("pos", self.pos())
        self.settings.setValue("size", self.size())

    def restore_pos(self) -> None:
        if pos := self.settings.value("pos"):
            self.move(pos)
        if size := self.settings.value("size"):
            self.resize(size)

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if edge := self.get_resize_edge(event.pos()):
                self.resizing = True
                self.start_pos = event.globalPosition().toPoint()
                self.start_geo = self.geometry()

    @override
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.resizing and self.start_pos and self.start_geo:
            delta = event.globalPosition().toPoint() - self.start_pos
            g = self.start_geo
            self.setGeometry(
                g.x(),
                g.y(),
                max(self.minimumWidth(), g.width() + delta.x()),
                max(self.minimumHeight(), g.height() + delta.y()),
            )
        else:
            self.setCursor(
                self.get_resize_edge(event.pos()) or Qt.CursorShape.ArrowCursor
            )

    @override
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.resizing:
            self.resizing = False
            self.save_pos()

    def get_resize_edge(self, pos) -> Qt.CursorShape | None:
        threshold, rect = config.resize_edge_threshold, self.rect()
        left, right, top, bottom = (
            pos.x() < threshold,
            pos.x() > rect.width() - threshold,
            pos.y() < threshold,
            pos.y() > rect.height() - threshold,
        )
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
        default_data = [
            {
                "name": "Positive",
                "categories": [
                    {"name": "Joy", "emoticons": ["(* ^ ω ^)"]},
                    {"name": "Love", "emoticons": ["(ﾉ´ з `)ノ"]},
                ],
            },
            {
                "name": "Negative",
                "categories": [{"name": "Anger", "emoticons": ["(#°Д°)"]}],
            },
        ]
        try:
            with self.json_file.open("w", encoding="utf-8") as f:
                json.dump(default_data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.error(f"Could not create default JSON file: {e}")


def main() -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    picker = KaomojiPicker()
    picker.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
