"""Technical Console pages."""

from simple_database_toolkit.build_profile import BML_EDITOR_ENABLED

if BML_EDITOR_ENABLED:
    from .bml_page import BmlPage
else:
    BmlPage = None
from .dashboard_page import DashboardPage
from .folder_page import FolderCreatorPage
from .links_page import LinksPage
from .offset_page import OffsetPage
from .parking_page import ParkingPage
from .parents_page import ParentsPage
from .placeholder_page import PlaceholderPage
from .replace_page import ReplacePage
from .runway_page import RunwayPage
from .tutorial_page import TutorialPage

__all__ = [
    "BmlPage",
    "DashboardPage",
    "FolderCreatorPage",
    "LinksPage",
    "OffsetPage",
    "ParkingPage",
    "ParentsPage",
    "PlaceholderPage",
    "ReplacePage",
    "RunwayPage",
    "TutorialPage",
]
