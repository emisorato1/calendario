"""Agente de sincronización con Google Calendar."""

from agents.calendar_sync.auth import get_credentials
from agents.calendar_sync.client import CalendarClient
from agents.calendar_sync.colors import get_color_emoji, get_color_id
from agents.calendar_sync.conflict_checker import check_conflicts, suggest_alternatives
from agents.calendar_sync.event_builder import build_event, build_patch
from agents.calendar_sync.formatter import (
    format_event_list_item,
    format_event_summary,
    format_events_list,
)

__all__ = [
    "CalendarClient",
    "build_event",
    "build_patch",
    "check_conflicts",
    "format_event_list_item",
    "format_event_summary",
    "format_events_list",
    "get_color_emoji",
    "get_color_id",
    "get_credentials",
    "suggest_alternatives",
]
