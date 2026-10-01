"""Migration placeholder used for tools not yet ported."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from simple_database_toolkit.ui.components import PageHeader


class PlaceholderPage(QWidget):
    def __init__(
        self,
        module_code: str,
        title: str,
        description: str,
        migration_phase: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        layout.addWidget(PageHeader(module_code, title, description))

        panel = QFrame()
        panel.setObjectName("Panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 14, 16, 16)
        panel_layout.setSpacing(7)

        heading = QLabel("MIGRATION STATUS")
        heading.setObjectName("PanelTitle")

        status = QLabel(f"Scheduled for {migration_phase}.")
        detail = QLabel(
            "The legacy implementation remains available in StructureAdjuster.py "
            "until this service and page pass equivalence tests."
        )
        detail.setObjectName("MutedText")
        detail.setWordWrap(True)

        panel_layout.addWidget(heading)
        panel_layout.addWidget(status)
        panel_layout.addWidget(detail)
        panel_layout.addStretch(1)

        layout.addWidget(panel, 1)
