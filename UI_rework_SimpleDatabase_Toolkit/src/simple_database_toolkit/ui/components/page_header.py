"""Consistent page title and module identifier."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class PageHeader(QFrame):
    def __init__(
        self,
        module_code: str,
        title: str,
        description: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(3)

        code_label = QLabel(module_code.upper())
        code_label.setObjectName("ModuleCode")

        title_label = QLabel(title)
        title_label.setObjectName("PageTitle")

        description_label = QLabel(description)
        description_label.setObjectName("PageDescription")
        description_label.setWordWrap(True)

        layout.addWidget(code_label)
        layout.addWidget(title_label)
        layout.addWidget(description_label)
