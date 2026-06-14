"""Data models for Alangrapher."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Subject:
    id: Optional[int] = None
    name: str = ""
    color: str = "#5E6AD2"
    archived: int = 0
    sort_order: int = 0
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color,
            "archived": self.archived,
            "sort_order": self.sort_order,
            "created_at": self.created_at,
        }


@dataclass
class Record:
    id: Optional[int] = None
    subject_id: Optional[int] = None
    description: str = ""
    start_time: str = ""
    end_time: Optional[str] = None
    duration_s: int = 0
    slot_index: int = 0
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "subject_id": self.subject_id,
            "description": self.description,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_s": self.duration_s,
            "slot_index": self.slot_index,
            "created_at": self.created_at,
        }


@dataclass
class Todo:
    id: Optional[int] = None
    subject_id: Optional[int] = None
    description: str = ""
    est_minutes: int = 0
    status: str = "pending"
    sort_order: int = 0
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "subject_id": self.subject_id,
            "description": self.description,
            "est_minutes": self.est_minutes,
            "status": self.status,
            "sort_order": self.sort_order,
            "created_at": self.created_at,
        }


@dataclass
class SlotState:
    slot_index: int = 0
    status: str = "idle"  # idle | running | paused
    subject_id: Optional[int] = None
    description: str = ""
    elapsed_s: int = 0
    started_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "slot_index": self.slot_index,
            "status": self.status,
            "subject_id": self.subject_id,
            "description": self.description,
            "elapsed_s": self.elapsed_s,
            "started_at": self.started_at,
        }
