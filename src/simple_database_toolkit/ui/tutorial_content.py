"""Structured, searchable help content for migrated toolkit modules."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from simple_database_toolkit.build_profile import page_enabled


@dataclass(frozen=True, slots=True)
class TutorialTopic:
    topic_id: str
    page_id: str
    category: str
    title: str
    summary: str
    keywords: tuple[str, ...]
    sections: tuple[tuple[str, tuple[str, ...]], ...]
    safety_note: str
    image_name: str | None = None
    image_caption: str = ""

    @property
    def search_text(self) -> str:
        section_text = " ".join(
            f"{heading} {' '.join(items)}"
            for heading, items in self.sections
        )
        return " ".join(
            (
                self.title,
                self.category,
                self.summary,
                " ".join(self.keywords),
                section_text,
                self.safety_note,
                self.image_caption,
            )
        ).casefold()

    def to_html(self, image_source: str | None = None) -> str:
        sections = []
        for heading, items in self.sections:
            list_items = "".join(
                f"<li>{_inline_markup(item)}</li>" for item in items
            )
            sections.append(
                f"<h2>{html.escape(heading)}</h2><ul>{list_items}</ul>"
            )
        image_html = ""
        if image_source and self.image_name:
            image_html = (
                "<p><img src='"
                + html.escape(image_source, quote=True)
                + "' width='300'></p>"
                + (
                    "<p class='caption'>"
                    + html.escape(self.image_caption)
                    + "</p>"
                    if self.image_caption
                    else ""
                )
            )
        return (
            f"<p class='module'>{html.escape(self.category.upper())}</p>"
            f"<h1>{html.escape(self.title)}</h1>"
            f"<p class='summary'>{html.escape(self.summary)}</p>"
            + image_html
            + "".join(sections)
            + "<h2>Safety and behavior</h2>"
            + f"<p>{_inline_markup(self.safety_note)}</p>"
        )


def _inline_markup(text: str) -> str:
    escaped = html.escape(text)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)


TUTORIAL_TOPICS: tuple[TutorialTopic, ...] = (
    TutorialTopic(
        topic_id="replace-features",
        page_id="replace",
        category="Features",
        title="Replace Features",
        summary=(
            "Scan and replace FeatureCtIdx values in objective FED XML files."
        ),
        keywords=(
            "FED",
            "FeatureCtIdx",
            "single objective",
            "entire theater",
            "Class Table",
            "atomic",
        ),
        sections=(
            (
                "Workflow",
                (
                    "Choose `Single objective` and select the OCD_XXXXX "
                    "folder containing FED_XXXXX.xml, or choose `Entire "
                    "theater` and select the Class Table XML beside "
                    "ObjectiveRelatedData.",
                    "Enter the existing and replacement Class Table feature "
                    "numbers.",
                    "Run `SCAN TARGET` first to review matching files and "
                    "entries.",
                    "Run `EXECUTE REPLACE`, confirm the scope, and inspect "
                    "the diagnostic output and session metrics.",
                ),
            ),
            (
                "What changes",
                (
                    "Only matching `FeatureCtIdx` values in FED XML are "
                    "changed.",
                    "Missing, malformed, and non-matching files are reported "
                    "without stopping unrelated objectives.",
                    "Changed files are replaced atomically; originals remain "
                    "untouched if writing fails.",
                ),
            ),
        ),
        safety_note=(
            "Use feature numbers from the correct theater Class Table. Scan "
            "before applying a theater-wide replacement."
        ),
    ),
    TutorialTopic(
        topic_id="offset-fixer",
        page_id="offset",
        category="Features",
        title="Offset Fixer",
        summary=(
            "Apply targeted position, rotation, heading, or value changes to "
            "matching FED features."
        ),
        keywords=(
            "OffsetX",
            "OffsetY",
            "OffsetZ",
            "Heading",
            "Value",
            "rotation",
            "delta",
            "absolute",
        ),
        sections=(
            (
                "Workflow",
                (
                    "For a single objective, select the OCD_XXXXX folder "
                    "containing FED_XXXXX.xml. For an entire theater, select "
                    "the Class Table XML beside ObjectiveRelatedData.",
                    "Run `SCAN FEATURES` to populate the available feature "
                    "list, or enter a FeatureCtIdx directly.",
                    "Choose a transformation, enter its parameters, then run "
                    "`EXECUTE CHANGE` and confirm.",
                ),
            ),
            (
                "Transformations",
                (
                    "`Fix XY Offsets` adds local X/Y deltas rotated by the "
                    "feature's current heading.",
                    "`Set Z`, `Set Heading`, and `Set Value` replace the "
                    "stored value.",
                    "`Fix Rotation` adds a heading delta and normalizes the "
                    "result.",
                ),
            ),
        ),
        safety_note=(
            "The scan is read-only. Apply writes only matching FED entries "
            "and preserves unrelated XML text."
        ),
        image_name="tut_1.png",
        image_caption=(
            "Legacy model-center alignment example. Confirm the current "
            "Objective Editor coordinate convention before applying the "
            "illustrated X/Y deltas."
        ),
    ),
    TutorialTopic(
        topic_id="runway-dimension-fixer",
        page_id="runway",
        category="Airbase",
        title="Runway Dimension Fixer",
        summary=(
            "Validate and repair PHD/PDX headings, RunwayDim assignments, "
            "crossings, and path trees."
        ),
        keywords=(
            "PHD",
            "PDX",
            "RunwayListType",
            "RunwayDimType",
            "CrossingPoint",
            "RootIdx",
            "map",
            "taxi path",
        ),
        sections=(
            (
                "Checks",
                (
                    "Single mode takes one OCD_XXXXX folder. Entire-theater "
                    "mode takes the Class Table XML beside "
                    "ObjectiveRelatedData.",
                    "`RunwayList heading` compares PHD Type 1 Data with the "
                    "heading calculated from Type 2 and Type 1 PDX points.",
                    "`RunwayDim assignment` finds the Type 8 bounding box "
                    "containing each runway point.",
                    "`RunwayDim heading` preserves either valid Type 1 "
                    "heading. Within the adjustable 4–6° cone it snaps to "
                    "the closest runway end; outside the cone it uses the "
                    "selected first/second fallback. Force overrides a "
                    "valid opposite-end heading.",
                    "`Crossing functionality` validates CrossingPoint=1 and "
                    "CrossingPoint=-1 markers using taxi-segment intersections "
                    "with Type 8 polygons.",
                    "`Paths checker` validates convergence, point-type "
                    "transitions, and distances. It is strictly check-only "
                    "and disables Fix.",
                ),
            ),
            (
                "Path distance guidance",
                (
                    "Park → Taxi: at most 200 ft.",
                    "Taxi → Taxi/TakeRunway and TakeRunway → TakeRunway: at "
                    "most 300 ft.",
                    "TakeRunway → Takeoff: at least 180 ft.",
                    "A violation beyond twice a maximum, or below half a "
                    "minimum, is escalated from warning to error.",
                ),
            ),
            (
                "Map",
                (
                    "In single-objective mode, include the crossing check and "
                    "run Check or Fix to enable `SHOW MAP`.",
                    "Fix results display before/after views; checks display "
                    "the current runway polygons, paths, and crossing markers.",
                ),
            ),
        ),
        safety_note=(
            "PHD and PDX changes are committed as one transaction per "
            "airbase and rolled back together if either replacement fails. "
            "When enabled, the original files are backed up before repair."
        ),
    ),
    TutorialTopic(
        topic_id="parking-fixer",
        page_id="parking",
        category="Airbase",
        title="Parking Fixer",
        summary=(
            "Preview and relocate parking PDX points to nearby Type-45 "
            "hangar feature centers."
        ),
        keywords=(
            "parking",
            "hangar",
            "shelter",
            "Class Table",
            "CT",
            "FED",
            "PDX",
            "radius",
            "preview",
        ),
        sections=(
            (
                "Workflow",
                (
                    "Select one OCD objective folder or an "
                    "ObjectiveRelatedData folder for batch mode.",
                    "Select the matching Class Table XML, enter a search "
                    "radius, and enter hangar CT numbers separated by commas.",
                    "Use CT number `0` to consider all Type-45 hangars.",
                    "Run `PREVIEW MOVES` and inspect every proposed coordinate "
                    "change before `APPLY PREVIEWED MOVES` becomes available.",
                ),
            ),
            (
                "Selection logic",
                (
                    "Each parking point moves to the nearest eligible hangar "
                    "center inside the selected radius.",
                    "Points without an eligible hangar in range are unchanged.",
                    "Changing paths or parameters invalidates the preview and "
                    "requires a new one.",
                ),
            ),
        ),
        safety_note=(
            "Apply revalidates the preview against current files and changes "
            "only the selected PDX OffsetX/OffsetY values atomically."
        ),
    ),
    TutorialTopic(
        topic_id="folder-creator",
        page_id="folder",
        category="Database",
        title="Folder Creator",
        summary=(
            "Create an inclusive validated range of numbered model folders."
        ),
        keywords=(
            "folders",
            "range",
            "Parent.dat",
            "numbered",
            "model",
        ),
        sections=(
            (
                "Workflow",
                (
                    "Enter start and end numbers; the requested count is "
                    "shown before execution.",
                    "Select the parent directory and optionally enable "
                    "`Create Parent.dat in every folder`.",
                    "Run `EXECUTE CREATE`, confirm the inclusive range, and "
                    "review created and skipped counts.",
                ),
            ),
            (
                "Conflict handling",
                (
                    "The start must be less than or equal to the end and both "
                    "values must be in the supported range.",
                    "Existing folders are never overwritten.",
                    "Cancellation is checked between folder creations.",
                ),
            ),
        ),
        safety_note=(
            "Folder creation is additive. Existing directories and files are "
            "left unchanged."
        ),
    ),
    TutorialTopic(
        topic_id="reformat-parents",
        page_id="parents",
        category="Database",
        title="Reformat Parents",
        summary=(
            "Validate, normalize, and cross-check Parent.dat model metadata."
        ),
        keywords=(
            "Parent.dat",
            "Dimensions",
            "TextureSets",
            "Switches",
            "Dofs",
            "AddLOD",
            "BML",
            "LOD",
        ),
        sections=(
            (
                "Actions",
                (
                    "`Single file` takes one exact Parent.dat file. `Folder "
                    "tree` takes a root folder and recursively searches the "
                    "selected folder and every subfolder for Parent.dat.",
                    "`CHECK FIELDS` validates required values and AddLOD "
                    "records without writing.",
                    "`CHECK BML FILES` compares AddLOD references with BML "
                    "files present in each model folder.",
                    "`REFORMAT PARENTS` writes the normalized field layout; "
                    "the optional checkbox converts AddLOD names from .lod "
                    "to .bml.",
                ),
            ),
            (
                "Validation rules",
                (
                    "Dimensions requires seven finite numeric values.",
                    "TextureSets, Switches, and Dofs accept non-negative "
                    "integers. TextureSets may be greater than one.",
                    "AddLOD requires a model filename and positive distance.",
                ),
            ),
        ),
        safety_note=(
            "Single-file and recursive folder-tree modes use atomic writes. "
            "Run both checks before a bulk reformat."
        ),
    ),
    TutorialTopic(
        topic_id="links-generator",
        page_id="links",
        category="Database",
        title="Links Generator",
        summary=(
            "Rebuild all objective links or recalculate links affected by "
            "new and moved objectives."
        ),
        keywords=(
            "CSV",
            "TE_New_NT",
            "LUT",
            "distance cost",
            "neighbors",
            "intersections",
            "generate",
            "update",
        ),
        sections=(
            (
                "Modes",
                (
                    "`Generate — rebuild all links` reads one dataset CSV and "
                    "writes a new complete output CSV.",
                    "`Update — recalculate changed objectives` compares old "
                    "and new datasets, preserving unaffected links.",
                ),
            ),
            (
                "Options",
                (
                    "Radius limits the neighbor search in kilometers.",
                    "When `Allow links to cross existing segments` is off, "
                    "new links avoid segment intersections.",
                    "An optional LUT JSON maps distance bins to eight link "
                    "costs. Without it, a LUT is derived from source links.",
                    "The output path is always separate and is replaced "
                    "atomically only after successful generation.",
                ),
            ),
        ),
        safety_note=(
            "Review diagnostics for malformed rows and objectives with too "
            "few neighbors before replacing theater data with the output."
        ),
    ),
    TutorialTopic(
        topic_id="bml-editor",
        page_id="bml",
        category="Models",
        title="BML Editor",
        summary=(
            "Inspect and safely edit BML v1 texture skinsets or BML v2 "
            "material names across a model folder."
        ),
        keywords=(
            "BMLv1",
            "BMLv2",
            "texture ID",
            "skinset",
            "materials.mtl",
            "Parent.dat",
            "LZMA",
            "compression",
        ),
        sections=(
            (
                "Workflow",
                (
                    "Select a model folder and run `INSPECT MODEL` before any "
                    "editor controls are enabled.",
                    "For BML v1, edit texture IDs or add/remove complete "
                    "skinsets, then run `SAVE V1 CHANGES`.",
                    "For BML v2, rename materials and run "
                    "`SAVE V2 CHANGES`.",
                    "Each save asks whether to back up the changed BML "
                    "files and sidecars before committing them.",
                    "Review model diagnostics for mixed versions, inconsistent "
                    "LOD data, or non-editable folders.",
                ),
            ),
            (
                "Side files and limits",
                (
                    "V1 skinset changes update Parent.dat TextureSets.",
                    "V2 material renames update materials.mtl.",
                    "The editor does not modify geometry, create BML files, "
                    "add individual texture slots, or convert model versions.",
                ),
            ),
        ),
        safety_note=(
            "Every edited BML is recompressed and verified before a "
            "transactional multi-file commit. Commit failures trigger "
            "rollback of BML and side files."
        ),
    ),
)


TUTORIAL_TOPICS = tuple(topic for topic in TUTORIAL_TOPICS if page_enabled(topic.page_id))
TOPICS_BY_ID = {topic.topic_id: topic for topic in TUTORIAL_TOPICS}
