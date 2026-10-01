"""Embedded Matplotlib visualization for runway and crossing data."""

from __future__ import annotations

from matplotlib import colormaps
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Polygon
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QWidget

from simple_database_toolkit.services import (
    RunwayMapComparison,
    RunwayMapSnapshot,
)


class RunwayMapDialog(QDialog):
    def __init__(
        self,
        comparison: RunwayMapComparison,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle(f"Runway Map — {comparison.before.title}")
        self.resize(1120, 720)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        figure = Figure(layout="constrained")
        canvas = FigureCanvasQTAgg(figure)
        layout.addWidget(canvas)

        background = self.palette().window().color().name()
        foreground = self.palette().windowText().color().name()
        figure.set_facecolor(background)
        if comparison.after is None:
            axes = [figure.add_subplot(1, 1, 1)]
            snapshots = [(comparison.before, "Current state")]
        else:
            axes = [
                figure.add_subplot(1, 2, 1),
                figure.add_subplot(1, 2, 2),
            ]
            snapshots = [
                (comparison.before, "Before fix"),
                (comparison.after, "After fix"),
            ]
        figure.suptitle(
            comparison.before.title,
            color=foreground,
            fontsize=13,
            fontweight="bold",
        )
        for axis, (snapshot, title) in zip(axes, snapshots, strict=True):
            _draw_snapshot(
                axis,
                snapshot,
                title,
                background,
                foreground,
            )
        canvas.draw()


def _draw_snapshot(
    axis,
    snapshot: RunwayMapSnapshot,
    title: str,
    background: str,
    foreground: str,
) -> None:
    axis.set_facecolor(background)
    axis.set_title(title, color=foreground)
    axis.set_aspect("equal", adjustable="datalim")
    axis.grid(True, alpha=0.22)
    axis.set_xlabel("OffsetX", color=foreground)
    axis.set_ylabel("OffsetY", color=foreground)
    axis.tick_params(colors=foreground)
    for spine in axis.spines.values():
        spine.set_color(foreground)

    for runway in snapshot.polygons:
        axis.add_patch(
            Polygon(
                runway.vertices,
                closed=True,
                alpha=0.2,
                facecolor="#4f8dd6",
                edgecolor="#1b5aa5",
                linewidth=1.5,
            )
        )
        center_x = sum(point[0] for point in runway.vertices) / len(
            runway.vertices
        )
        center_y = sum(point[1] for point in runway.vertices) / len(
            runway.vertices
        )
        axis.text(
            center_x,
            center_y,
            f"Rwy {runway.runway_number}",
            color=foreground,
            ha="center",
            va="center",
            fontsize=8,
            fontweight="bold",
        )

    color_map = colormaps["tab20"]
    for index, path in enumerate(snapshot.paths):
        if not path.points:
            continue
        color = color_map(index % 20)
        xs = [point.x for point in path.points]
        ys = [point.y for point in path.points]
        axis.plot(xs, ys, "-", color=color, linewidth=0.9, alpha=0.7)
        axis.plot(xs, ys, ".", color=color, markersize=2.5)
        for point in path.points:
            if point.crossing_point == 1:
                marker, marker_color, edge = "o", "#58d66b", "#20752f"
            elif point.crossing_point == -1:
                marker, marker_color, edge = "s", "#ff595e", "#9d1c20"
            elif point.crossing_point not in (None, 0):
                marker, marker_color, edge = "D", "#ff9f1c", "#a95d00"
            else:
                continue
            axis.plot(
                point.x,
                point.y,
                marker=marker,
                color=marker_color,
                markeredgecolor=edge,
                markeredgewidth=1.5,
                markersize=8,
                zorder=7,
            )
            axis.annotate(
                f"{point.relative_index} ({point.crossing_point})",
                (point.x, point.y),
                color=foreground,
                fontsize=6,
                xytext=(5, 5),
                textcoords="offset points",
            )

    for x, y, _runway_number in snapshot.runway_points:
        axis.plot(x, y, "^", color="#1b5aa5", markersize=9, zorder=6)
    for x, y, _runway_number in snapshot.takeoff_points:
        axis.plot(x, y, "*", color="#9554c7", markersize=11, zorder=6)

    legend = axis.legend(
        handles=[
            Line2D(
                [0],
                [0],
                marker="^",
                color="none",
                markerfacecolor="#1b5aa5",
                label="Runway point",
            ),
            Line2D(
                [0],
                [0],
                marker="*",
                color="none",
                markerfacecolor="#9554c7",
                label="Takeoff point",
            ),
            Line2D(
                [0],
                [0],
                marker="o",
                color="none",
                markerfacecolor="#58d66b",
                label="CP=1 start",
            ),
            Line2D(
                [0],
                [0],
                marker="s",
                color="none",
                markerfacecolor="#ff595e",
                label="CP=-1 end",
            ),
            Polygon(
                [(0, 0)],
                facecolor="#4f8dd6",
                edgecolor="#1b5aa5",
                alpha=0.2,
                label="RunwayDim",
            ),
        ],
        loc="upper right",
        fontsize=7,
        framealpha=0.75,
    )
    legend.get_frame().set_facecolor(background)
    legend.get_frame().set_edgecolor(foreground)
    for text in legend.get_texts():
        text.set_color(foreground)
