"""Searchable local documentation for every toolkit module."""

from __future__ import annotations

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import (
    QKeySequence,
    QShortcut,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from simple_database_toolkit.ui.components import PageHeader
from simple_database_toolkit.ui.branding import find_media_asset
from simple_database_toolkit.ui.tutorial_content import (
    TOPICS_BY_ID,
    TUTORIAL_TOPICS,
    TutorialTopic,
)


class TutorialPage(QWidget):
    navigate_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        self._filtered_topics: tuple[TutorialTopic, ...] = TUTORIAL_TOPICS

        self._build_ui()
        self._connect_signals()
        self._filter_topics("")

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        layout.addWidget(
            PageHeader(
                "HELP / TUTORIAL",
                "Tutorial",
                "New here? Start with Getting Started, then choose a tool "
                "for explained terms, examples, and step-by-step instructions.",
            )
        )

        search_panel = QFrame()
        search_panel.setObjectName("Panel")
        search_layout = QVBoxLayout(search_panel)
        search_layout.setContentsMargins(15, 13, 15, 15)
        search_layout.setSpacing(7)
        search_title = QLabel("SEARCH LOCAL DOCUMENTATION")
        search_title.setObjectName("PanelTitle")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            "Search: move an object, fix a runway, backup, texture…"
        )
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setAccessibleName("Search tutorial documentation")
        self.search_status = QLabel(
            "Start with Getting Started, or search for what you want to do."
        )
        self.search_status.setObjectName("MutedText")
        search_layout.addWidget(search_title)
        search_layout.addWidget(self.search_edit)
        search_layout.addWidget(self.search_status)
        layout.addWidget(search_panel)

        content_row = QHBoxLayout()
        content_row.setSpacing(10)

        topic_panel = QFrame()
        topic_panel.setObjectName("Panel")
        topic_panel.setFixedWidth(220)
        topic_layout = QVBoxLayout(topic_panel)
        topic_layout.setContentsMargins(10, 9, 10, 10)
        topic_layout.setSpacing(7)
        topic_title = QLabel("TOPICS")
        topic_title.setObjectName("PanelTitle")
        self.topic_list = QListWidget()
        self.topic_list.setObjectName("TutorialTopics")
        self.topic_list.setUniformItemSizes(True)
        self.topic_list.setAccessibleName("Tutorial topics")
        topic_layout.addWidget(topic_title)
        topic_layout.addWidget(self.topic_list, 1)

        document_panel = QFrame()
        document_panel.setObjectName("Panel")
        document_layout = QVBoxLayout(document_panel)
        document_layout.setContentsMargins(10, 9, 10, 10)
        document_layout.setSpacing(7)
        document_header = QHBoxLayout()
        document_title = QLabel("DOCUMENT")
        document_title.setObjectName("PanelTitle")
        self.open_tool_button = QPushButton("OPEN TOOL")
        self.open_tool_button.setProperty("primary", True)
        document_header.addWidget(document_title)
        document_header.addStretch(1)
        document_header.addWidget(self.open_tool_button)
        self.document_browser = QTextBrowser()
        self.document_browser.setObjectName("TutorialDocument")
        self.document_browser.setOpenExternalLinks(False)
        self.document_browser.setMinimumHeight(410)
        self.document_browser.document().setDefaultStyleSheet(
            """
            h1 { font-size: 22px; font-weight: 700; margin: 4px 0 8px 0; }
            h2 { font-size: 16px; font-weight: 700; margin: 15px 0 4px 0; }
            p { margin: 5px 0; line-height: 1.35; }
            p.module { font-family: Consolas; font-size: 11px;
                       letter-spacing: 1px; margin-bottom: 2px; }
            p.summary { font-size: 14px; margin-bottom: 11px; }
            p.caption { font-size: 11px; font-style: italic;
                        margin: 2px 0 12px 0; }
            li { margin-bottom: 6px; }
            code { font-family: Consolas; font-weight: 600; }
            """
        )
        document_layout.addLayout(document_header)
        document_layout.addWidget(self.document_browser, 1)

        content_row.addWidget(topic_panel)
        content_row.addWidget(document_panel, 1)
        layout.addLayout(content_row, 1)

        shortcut_note = QLabel(
            "Ctrl+F focuses tutorial search • Ctrl+K opens command search • "
            "F1 opens Help from anywhere"
        )
        shortcut_note.setObjectName("MutedText")
        shortcut_note.setWordWrap(True)
        layout.addWidget(shortcut_note)

        self.search_shortcut = QShortcut(
            QKeySequence.StandardKey.Find,
            self,
        )
        self.search_shortcut.setContext(
            Qt.ShortcutContext.WidgetWithChildrenShortcut
        )

    def _connect_signals(self) -> None:
        self.search_edit.textChanged.connect(self._filter_topics)
        self.topic_list.currentItemChanged.connect(
            self._on_topic_changed
        )
        self.open_tool_button.clicked.connect(self._open_current_tool)
        self.search_shortcut.activated.connect(self.focus_search)

    def focus_search(self) -> None:
        self.search_edit.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.search_edit.selectAll()

    def select_topic(self, topic_id: str) -> bool:
        for index in range(self.topic_list.count()):
            item = self.topic_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == topic_id:
                self.topic_list.setCurrentItem(item)
                return True
        return False

    def _filter_topics(self, query: str) -> None:
        normalized = " ".join(query.casefold().split())
        current_id = self._current_topic_id()
        self._filtered_topics = tuple(
            topic
            for topic in TUTORIAL_TOPICS
            if not normalized or normalized in topic.search_text
        )
        self.topic_list.blockSignals(True)
        self.topic_list.clear()
        for topic in self._filtered_topics:
            item = QListWidgetItem(
                f"{topic.category.upper()}\n{topic.title}"
            )
            item.setData(Qt.ItemDataRole.UserRole, topic.topic_id)
            item.setToolTip(topic.summary)
            self.topic_list.addItem(item)
        self.topic_list.blockSignals(False)

        match_count = len(self._filtered_topics)
        self.search_status.setText(
            f"{match_count} topic{'s' if match_count != 1 else ''} matched"
            + (f' “{query.strip()}”' if query.strip() else "")
        )
        if match_count == 0:
            self.open_tool_button.setEnabled(False)
            self.document_browser.setHtml(
                "<h1>No matching tutorial</h1>"
                "<p>Try a short phrase such as parking, heading, backup, "
                "or texture. Getting Started explains the common file names.</p>"
            )
            return

        target_row = 0
        if current_id is not None:
            for index, topic in enumerate(self._filtered_topics):
                if topic.topic_id == current_id:
                    target_row = index
                    break
        self.topic_list.setCurrentRow(target_row)
        self._render_topic(self._filtered_topics[target_row], query)

    def _on_topic_changed(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if current is None:
            return
        topic = TOPICS_BY_ID.get(
            str(current.data(Qt.ItemDataRole.UserRole))
        )
        if topic is not None:
            self._render_topic(topic, self.search_edit.text())

    def _render_topic(self, topic: TutorialTopic, query: str) -> None:
        image_source = None
        if topic.image_name:
            image_path = find_media_asset(topic.image_name)
            if image_path is not None:
                image_source = QUrl.fromLocalFile(
                    str(image_path)
                ).toString()
        self.document_browser.setHtml(topic.to_html(image_source))
        self.document_browser.moveCursor(QTextCursor.MoveOperation.Start)
        self.open_tool_button.setEnabled(True)
        self.open_tool_button.setText(
            "OPEN OVERVIEW" if topic.page_id == "overview"
            else f"OPEN {topic.title.upper()}"
        )
        self._highlight_query(query)

    def _highlight_query(self, query: str) -> None:
        query = query.strip()
        if not query:
            self.document_browser.setExtraSelections([])
            return
        selections: list[QTextEdit.ExtraSelection] = []
        cursor = QTextCursor(self.document_browser.document())
        highlight = self.palette().highlight().color()
        highlight.setAlpha(115)
        text_format = QTextCharFormat()
        text_format.setBackground(highlight)
        text_format.setForeground(self.palette().text().color())
        while True:
            cursor = self.document_browser.document().find(query, cursor)
            if cursor.isNull():
                break
            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            selection.format = text_format
            selections.append(selection)
        self.document_browser.setExtraSelections(selections)

    def _current_topic_id(self) -> str | None:
        item = self.topic_list.currentItem()
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return str(value) if value else None

    def _open_current_tool(self) -> None:
        topic_id = self._current_topic_id()
        if topic_id is None:
            return
        topic = TOPICS_BY_ID.get(topic_id)
        if topic is not None:
            self.navigate_requested.emit(topic.page_id)
