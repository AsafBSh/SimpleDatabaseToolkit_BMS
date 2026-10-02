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
            list_tag = "ol" if heading == "Step by step" else "ul"
            list_items = "".join(
                f"<li>{_inline_markup(item)}</li>" for item in items
            )
            sections.append(
                f"<h2>{html.escape(heading)}</h2><{list_tag}>{list_items}</{list_tag}>"
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
            + "<h2>Before you save</h2>"
            + f"<p>{_inline_markup(self.safety_note)}</p>"
        )


def _inline_markup(text: str) -> str:
    escaped = html.escape(text)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)


TUTORIAL_TOPICS: tuple[TutorialTopic, ...] = (
    TutorialTopic(
        topic_id="getting-started", page_id="overview", category="Basics",
        title="Getting Started",
        summary="Start here if you are new to Falcon BMS database editing. Learn what the files contain and how to make your first change.",
        keywords=("beginner", "first steps", "glossary", "backup", "restore", "XML", "CSV", "JSON", "atomic"),
        sections=(
            ("The basic idea", (
                "A theater is a game region with its own database. This toolkit changes selected database files; it does not replace the BMS theater editor.",
                "An objective is a location in that database, such as an airbase. A feature is an object placed at that location, such as a hangar. A model describes the object's 3D shape and appearance.",
                "A Class Table is the theater's catalog of object types. Its CT numbers identify entries in that catalog. A CT number is not a model folder number; do not assume they are interchangeable.",
            )),
            ("Recognize the files", (
                "`ObjectiveRelatedData` holds objective folders. `OCD_01234` is an example: replace 01234 with your objective's actual number.",
                "`FED_01234.xml` lists the features placed at that objective. `PHD_01234.xml` and `PDX_01234.xml` describe airbase point records and their positions/connections.",
                "`Parent.dat` is a model's text description. `.bml` files contain model data. A texture is an image used on a model; a material describes a named surface used by the model.",
                "XML is text with named fields. CSV is a table saved as text, with comma-separated columns. JSON is text used for structured settings or lookup data. Keep the expected file format when preparing inputs.",
            )),
            ("Step by step", (
                "Start with a copy of one objective or model folder. Keep files belonging to the same objective together, and use the Class Table from that same theater.",
                "Choose the tool whose tutorial matches your goal. In single-objective mode, select the specific OCD folder; in batch mode, follow that tool's file selector description.",
                "Enable `Back up edited files` before a write. Open Overview's `BACKUP SETTINGS` to choose a backup folder outside the target folder. BML saves have their own backup choice.",
                "Use Scan, Check, Inspect, or Preview first when available. These actions read the selected files; they do not apply the proposed edits.",
                "Read the result, then use the tool's Execute, Fix, Apply, or Save action. Check the changed-file count and inspect the result in your usual BMS editing workflow before repeating on a whole theater.",
            )),
            ("Understand the output", (
                "Diagnostic output is the operation's message list. Info explains progress, warnings need review, and errors describe a problem. Read the message and its target file together.",
                "Session metrics are totals such as files checked, matches found, and files changed. Zero changes can mean the data already matched your request, or that nothing matched the selected inputs.",
                "`CLEAR OUTPUT` only clears messages. It does not undo edits. Cancel stops at a safe point; changes already completed in a batch may remain.",
            )),
            ("Restore a backup", (
                "Open the timestamped backup folder and read `RESTORE.txt`. It names the original destination. Copy the contents of `restore/` into that destination and allow matching files to be replaced.",
                "Copy the contents of restore, not the restore folder itself. Keep its subfolders intact. The backup's `manifest.json` records which originals were saved.",
                "An atomic write means the tool prepares a temporary file, then replaces the original when ready. A rollback restores coordinated files after a failed save. Neither replaces a backup for undoing a successful edit.",
            )),
        ),
        safety_note="You do not need to memorize field names. Each tool tutorial explains the terms and inputs it uses. Start small, read the messages, and keep a backup.",
    ),
    TutorialTopic(
        topic_id="replace-features", page_id="replace", category="Features",
        title="Replace Features",
        summary="Change which object type is used by matching features, such as replacing one hangar type with another.",
        keywords=("FED", "FeatureCtIdx", "single objective", "entire theater", "Class Table"),
        sections=(
            ("Files and terms", (
                "A feature is an object placed at an objective. Its `FeatureCtIdx` field is the feature's Class Table number: it tells BMS which object type to use.",
                "In single-objective mode, select an `OCD_XXXXX` folder containing the matching `FED_XXXXX.xml`. The Xs stand for the actual objective number.",
                "In entire-theater mode, select the theater's Class Table XML beside `ObjectiveRelatedData`. This lets the tool find that theater's objective files.",
            )),
            ("Step by step", (
                "Choose the target mode and select its required folder or file. Use one objective for your first test.",
                "Enter the feature number to remove and the replacement feature number. Identify the current number in the FED file and verify the replacement in that theater's Class Table; do not guess.",
                "Click `SCAN TARGET`. Review the matching entries and files before proceeding.",
                "Enable backups, then click `EXECUTE REPLACE`. Review the scope in the confirmation dialog and read the final messages.",
            )),
            ("Example", (
                "Suppose you have confirmed that CT 100 is the old object and CT 200 is the replacement. Enter 100 and 200. A matching `FeatureCtIdx` changes from 100 to 200. These numbers are examples, not recommended BMS object IDs.",
            )),
            ("Check the result", (
                "This operation changes the object-type number, not its saved position or heading. Check how the replacement looks: a different model may need separate alignment work.",
                "No matches means nothing was replaced. Missing or malformed files are reported; other objectives may still be processed, so inspect the full result before retrying.",
            )),
        ),
        safety_note="A theater-wide replacement affects every matching entry found in that theater. Scan first, verify both CT numbers, and keep the original files backed up.",
    ),
    TutorialTopic(
        topic_id="offset-fixer", page_id="offset", category="Features",
        title="Offset Fixer",
        summary="Move or turn matching placed objects, or change their stored height, heading, or Value field.",
        keywords=("OffsetX", "OffsetY", "OffsetZ", "Heading", "Value", "rotation", "delta", "absolute", "position", "move an object"),
        sections=(
            ("Files and terms", (
                "A FED file stores placed objects. `FeatureCtIdx` identifies the object type to target. `OffsetX` and `OffsetY` describe its position; `OffsetZ` is its vertical offset.",
                "Heading is an angle in degrees. A delta means an amount to add to the existing value; Set means replace the existing value with the number you enter.",
                "Select one OCD folder containing its FED XML, or select the matching theater Class Table XML for batch mode.",
            )),
            ("Step by step", (
                "Choose the scope and select the required target. Click `SCAN FEATURES` to list feature numbers found there.",
                "Select the feature type you want to change, or enter its known CT number. All matching instances in the selected scope are affected.",
                "Choose an operation below and enter the numbers it asks for. Enable backups before writing.",
                "Click `EXECUTE CHANGE`, review the confirmation, and inspect the messages and the resulting alignment.",
            )),
            ("Choose the right operation", (
                "`Fix XY offsets` adds an X/Y movement relative to the object's current heading. The tool turns your movement by that heading before adding it to the saved position.",
                "`Fix Rotation` adds an angle to the current heading. `Set Heading` replaces it. Results wrap around a full 360-degree turn.",
                "`Set Z` replaces the vertical offset. `Set Value` replaces the FED Value field; this is separate from position and rotation. Only use a value whose meaning you have confirmed for the feature.",
            )),
            ("Example and result", (
                "For an object facing 20 degrees, a rotation change of +3 gives 23 degrees. Set Heading to 3 gives 3 degrees instead. Choose Add or Set behavior deliberately.",
                "An unchanged Set value produces no write or backup. The scan only reads data; applying changes preserves unrelated XML text.",
                "For X/Y work, verify the axis directions and coordinate units in your Objective Editor before entering a movement. The illustration is an alignment example, not a universal movement recipe.",
            )),
        ),
        safety_note="Changing a shared feature number can move many objects. Start with one objective and a small change, then inspect the result before using batch mode.",
        image_name="tut_1.png",
        image_caption="A model-center alignment example: compare the placed object's center with the intended position, then confirm your editor's X/Y axes before moving it.",
    ),
    TutorialTopic(
        topic_id="runway-dimension-fixer", page_id="runway", category="Airbase",
        title="Runway Dimension Fixer",
        summary="Check an airbase's runway directions, runway areas, and taxi routes, then repair the supported problems.",
        keywords=("PHD", "PDX", "RunwayListType", "RunwayDimType", "CrossingPoint", "RootIdx", "map", "taxi path", "fix a runway"),
        sections=(
            ("Files and terms", (
                "Select one airbase's OCD folder, or the matching theater Class Table XML for batch mode. Keep the matching PHD and PDX XML files together.",
                "PHD holds point records and their associated data. PDX holds positions and connections. Together they describe runway and taxi-path information.",
                "A heading is a direction in degrees. RunwayList headings identify runway-end directions; RunwayDim describes the runway area and its assigned heading.",
                "A taxi path is a chain of connected points. A crossing marker tells the data where that path enters or leaves a runway area.",
            )),
            ("Step by step", (
                "Select one airbase and choose the checks you need. Start with `CHECK RUNWAYS`; this reports problems without changing the XML.",
                "Read each warning or error and its target. For a visual view, include Crossing functionality, run the check in single-airbase mode, then click `SHOW MAP`.",
                "For heading repairs, review the near-match cone, First/Second selection, and Force setting explained below. Enable backups.",
                "Click `FIX RUNWAYS` for supported repairs and review the changes. If you selected Paths checker, Fix is disabled: run that check separately and address its reports in your editing workflow.",
            )),
            ("What each check means", (
                "`RunwayList heading` checks whether the saved runway direction agrees with the direction calculated from its runway points.",
                "`RunwayDim assignment` checks which runway area contains each runway point. `RunwayDim heading` checks the heading stored for that area.",
                "`Crossing functionality` checks runway entry/exit markers against actual taxi-segment intersections. In the XML these markers use `CrossingPoint=1` and `CrossingPoint=-1`.",
                "`Paths checker` looks for broken or unsuitable point sequences and unexpected distances. It reports problems but does not repair paths.",
            )),
            ("Heading repairs: near match, priority, and Force", (
                "The near-match cone is a tolerance on either side of a valid heading, adjustable from 4 to 6 degrees; the default is plus or minus 5 degrees.",
                "Inside that tolerance, a small error snaps to the closest runway-end heading. A heading already matching either end is kept, even when the other end is selected as First or Second.",
                "Outside the tolerance, the selected First/Second heading is the fallback. These labels mean the order of available headings in the data, not a compass direction.",
                "Example: valid headings are 200 and 020. With First selected and Force off, 022 becomes 020; an existing 020 stays 020. This prevents an unnecessary reversal.",
                "`Force selected first/second heading` deliberately applies that selection, even if the current heading matches the opposite end. Leave it off for ordinary small corrections.",
            )),
            ("Read the map and path warnings", (
                "A check shows current runway areas, paths, and crossing markers. Supported fix results can show before/after views. Review the log as well as the picture.",
                "Distance guidance is in feet: Park to Taxi is at most 200; Taxi to Taxi/TakeRunway and TakeRunway to TakeRunway are at most 300; TakeRunway to Takeoff is at least 180.",
                "TakeRunway and Takeoff are path-point roles. Distances beyond twice a maximum or below half a minimum are reported as errors rather than warnings.",
                "Advanced XML labels: Type 1 PHD Data holds runway-list heading data; Type 2 and Type 1 PDX points provide its direction; Type 8 points describe runway bounds. RootIdx is a path connection index, not an angle.",
            )),
        ),
        safety_note="Check first and leave Force off unless a deliberate direction change is intended. PHD and PDX repairs are saved together per airbase; a failed coordinated save restores both originals.",
    ),
    TutorialTopic(
        topic_id="parking-fixer", page_id="parking", category="Airbase",
        title="Parking Fixer",
        summary="Move aircraft parking positions to nearby hangar centers after reviewing the proposed moves.",
        keywords=("parking", "hangar", "shelter", "Class Table", "CT", "FED", "PDX", "radius", "preview"),
        sections=(
            ("Files and terms", (
                "A parking point is a saved aircraft parking position in PDX XML. Hangar features are placed objects listed in FED XML.",
                "The matching Class Table tells the tool which features are hangars. This tool uses the hangar category numbered Type 45; a CT number selects a specific catalog entry.",
                "Select one OCD folder, or `ObjectiveRelatedData` for all-objective mode. Also select the Class Table XML belonging to that same theater.",
            )),
            ("Step by step", (
                "Select the target and matching Class Table. Set the search radius in feet: this is the maximum distance between a parking point and an eligible hangar center.",
                "Enter known hangar CT numbers separated by commas to restrict the search, or enter `0` to consider all Type-45 hangars.",
                "Click `PREVIEW MOVES`. Read the proposed old/new coordinates and any unchanged or unmatched points. Preview does not move anything.",
                "Enable backups, then click `APPLY PREVIEWED MOVES` if the suggestions are appropriate. Check the updated parking positions in your usual editor.",
            )),
            ("Example and result", (
                "With a 10 ft radius, a suitable hangar center 6 ft away may be selected; one 15 ft away is outside the search. The nearest eligible center in range is used.",
                "If no eligible hangar is in range, the parking point stays unchanged. Check the radius, Class Table, and selected hangar IDs rather than assuming the operation failed.",
                "Changing a path or option invalidates the preview. If the source files have changed since Preview, Apply refuses the old plan; preview again before saving.",
                "The saved change updates the parking point's X/Y position, not the hangar's position or the parking heading.",
            )),
        ),
        safety_note="Review every proposed move before applying. A larger radius can select a hangar you did not intend; start with one airbase and keep backups enabled.",
    ),
    TutorialTopic(
        topic_id="folder-creator", page_id="folder", category="Database",
        title="Folder Creator",
        summary="Create a numbered set of model folders, with optional starter Parent.dat files.",
        keywords=("folders", "range", "Parent.dat", "numbered", "model"),
        sections=(
            ("Files and terms", (
                "A model folder groups files for a model. Its folder number is part of your model organization; it is not automatically a feature's Class Table number.",
                "`Parent.dat` is the model's text description. The optional file created here is a starting template; it does not contain or generate a 3D model.",
                "Select the parent directory: this is the existing folder that will contain the new numbered folders.",
            )),
            ("Step by step", (
                "Choose a destination directory and enter the first and last folder numbers.",
                "Check the requested count. Both endpoints are included: 100 through 102 creates folders 100, 101, and 102.",
                "Enable `Create Parent.dat in every folder` if you need starter description files.",
                "Click `EXECUTE CREATE`, review the range in the confirmation, then read the created/skipped totals.",
            )),
            ("Check the result", (
                "The first number must be no larger than the last. Existing folders are skipped and their files are left unchanged.",
                "You still need to add the appropriate model files and complete each model's description through your normal development workflow.",
                "Cancellation is checked between creations. Read the final result to see which folders were completed.",
            )),
        ),
        safety_note="Choose the destination carefully and check your numbering plan. This tool adds folders; it does not overwrite existing folders or register new models in the theater database.",
    ),
    TutorialTopic(
        topic_id="reformat-parents", page_id="parents", category="Database",
        title="Reformat Parents",
        summary="Check model description files for missing or invalid entries, then tidy their layout or model filename references.",
        keywords=("Parent.dat", "Dimensions", "TextureSets", "Switches", "Dofs", "AddLOD", "BML", "LOD"),
        sections=(
            ("Files and terms", (
                "`Parent.dat` is a text description used alongside model files. It includes numbers and references that need to agree with the model's actual files.",
                "LOD means level of detail: a model version referenced for a viewing distance. An `AddLOD` entry pairs a model filename with its distance.",
                "`TextureSets` counts texture sets; `Switches` and `Dofs` are counts used for model controls and movement data. Reformatting does not create the controls or fix the model geometry.",
            )),
            ("Step by step", (
                "Choose `Single file` and select the exact Parent.dat, or choose `Folder tree` and select a root directory. Folder-tree mode searches that folder and all its subfolders.",
                "Click `CHECK FIELDS` to find missing or invalid entries. This only reads files.",
                "Click `CHECK BML FILES` to compare the listed model references with BML files present in each model folder. Resolve missing or unexpected files before bulk changes.",
                "If the field values and references are correct, enable backups and click `REFORMAT PARENTS` to write the standard field layout.",
                "Only enable the optional .lod-to-.bml filename conversion when your references should point to existing BML files. Renaming a reference does not convert a model file.",
            )),
            ("Example and validation details", (
                "A reference to `example.lod` can become `example.bml` when that option is enabled. The tool changes the name written in Parent.dat; it does not create example.bml.",
                "Dimensions must contain seven ordinary, finite numbers. TextureSets, Switches, and Dofs must be whole numbers at least zero; TextureSets can be greater than one.",
                "Each AddLOD needs a filename and a distance greater than zero. If a check reports an invalid value, correct it using the actual model data; formatting alone cannot determine the intended value.",
            )),
        ),
        safety_note="Run both checks before reformatting a folder tree. Keep backups and verify that referenced BML files actually exist.",
    ),
    TutorialTopic(
        topic_id="links-generator", page_id="links", category="Database",
        title="Links Generator",
        summary="Build connections between nearby objectives, or update connections after objectives are added or moved.",
        keywords=("CSV", "TE_New_NT", "LUT", "distance cost", "neighbors", "intersections", "generate", "update"),
        sections=(
            ("Files and terms", (
                "An objective is a database location. A link connects it to another objective. A neighbor is another objective close enough to consider for a link.",
                "Use an objective dataset CSV, a text table containing objective IDs, positions, and link data. The required headings are `Name`, `Type`, `Subtype`, `ID`, `X`, `Y`, `LCount`, and `Links`.",
                "LCount is the number of links in a row. Each link data group contains eight cost values and the destination objective ID. Keep the format from your supported export; an arbitrary spreadsheet of place names is not enough.",
                "Link costs are stored numbers associated with a connection. A LUT, or lookup table, groups distances and supplies eight cost values for each distance range. Its optional input file is JSON.",
            )),
            ("Step by step", (
                "Choose Generate to rebuild all links from one dataset, or Update to compare an older dataset with a newer one.",
                "Select the required CSV file(s). Keep the same objective IDs in old/new datasets when an objective is unchanged or moved.",
                "Set the neighbor radius in kilometers. The tool treats CSV X/Y distances as kilometers, so confirm your dataset uses the expected coordinate units.",
                "Choose whether links may cross existing segments. Leave the optional LUT blank to derive distance/cost rules from links already in the source data, or select a compatible LUT JSON.",
                "Select a separate output CSV path and run `GENERATE LINKS` or `UPDATE LINKS`. Review the messages and output before using it to replace your theater's data.",
            )),
            ("Example and result", (
                "If an objective moves but keeps its ID, Update can recalculate its affected connections and neighboring objectives while retaining unaffected links.",
                "A 20 km radius considers candidates up to 20 km away. Allowing segment crossings means drawn link segments may intersect; it does not create an intersection objective.",
                "If the source has no usable existing link-cost examples, provide a compatible LUT instead of expecting the tool to invent cost values.",
                "Review objectives with too few neighbors and malformed input reports. Generating a CSV does not automatically import it into BMS.",
            )),
        ),
        safety_note="Keep the input datasets unchanged and inspect the separate output. Use consistent IDs and coordinate units before replacing or importing theater data.",
    ),
    TutorialTopic(
        topic_id="bml-editor", page_id="bml", category="Models",
        title="BML Editor",
        summary="Change a model's texture selections or material names without changing its 3D shape.",
        keywords=("BMLv1", "BMLv2", "texture ID", "skinset", "materials.mtl", "Parent.dat", "LZMA", "compression"),
        sections=(
            ("Files and terms", (
                "BML is a model file format. Select a model folder containing its BML files and related description files, not the theater's whole Objects directory.",
                "A texture is an image used on a model. In BML v1, a texture ID is a number used to select a texture. A skinset is a complete group of texture selections for one appearance.",
                "In BML v2, the editor works with material names. A material is a named surface entry; `materials.mtl` is the related material-definition file.",
                "`Parent.dat` records model description data, including TextureSets. A LOD is another detail level of the same model; consistent detail levels need corresponding texture or material information.",
            )),
            ("Step by step", (
                "Select the model folder and click `INSPECT MODEL`. This reads the model version and data before enabling the appropriate editor.",
                "For v1, edit known texture IDs or use `ADD SKINSET` / `REMOVE` for complete texture sets. Click `SAVE V1 CHANGES` when ready.",
                "For v2, edit material names and click `SAVE V2 CHANGES`. Verify those names fit your material definitions.",
                "The save dialog asks whether to back up changed BML files and related files. Choose backups if you want to recover the previous appearance.",
                "Read the save result, then inspect the model in your normal viewing workflow. A successful file save does not prove the chosen texture or material looks correct.",
            )),
            ("Example, related files, and limits", (
                "For v1, replacing an existing texture ID with another verified ID changes that selection. It does not paint an image or add an individual texture slot.",
                "Changing the v1 skinset count updates Parent.dat's TextureSets when that related file is present. Renaming v2 materials also updates materials.mtl.",
                "Mixed BML versions or inconsistent detail-level data may make the folder unsuitable for editing. Read the inspection message instead of forcing a save.",
                "The editor does not change geometry, create BML models, or convert between v1 and v2. Saving recompresses the edited model data and checks that it can be read again; the compression format is LZMA.",
            )),
        ),
        safety_note="Use verified texture IDs and material names. A save can affect several BML detail levels and related files together; backups preserve all changed originals, and a failed coordinated save rolls them back.",
    ),
)

TUTORIAL_TOPICS = tuple(topic for topic in TUTORIAL_TOPICS if page_enabled(topic.page_id))
TOPICS_BY_ID = {topic.topic_id: topic for topic in TUTORIAL_TOPICS}
