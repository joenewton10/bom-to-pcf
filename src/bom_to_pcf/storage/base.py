"""The storage interface, the export format and the choice of backend."""

import json
from abc import ABC, abstractmethod

from pydantic import ValidationError

from bom_to_pcf.models import ProjectState

EXPORT_FORMAT = "bom-to-pcf-state"
EXPORT_VERSION = 1
SQLITE = "sqlite"
SESSION = "session"
STORAGE_VARIABLE = "BOM_TO_PCF_STORAGE"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]"}


class HistoryConflictError(ValueError):
    """Saving would remove or change history that is already stored."""


class StorageBackend(ABC):
    """Where a user's work is kept. History already stored can only ever be added to."""

    @abstractmethod
    def load(self) -> ProjectState:
        """Return the saved state, or an empty one."""

    @abstractmethod
    def _write(self, state: ProjectState) -> None:
        """Store the state."""

    def save(self, state: ProjectState) -> None:
        """Save the state, refusing anything that would rewrite history."""
        stored = self.load()
        for name in ("audit", "versions", "rejections", "review_log"):
            old, new = getattr(stored, name), getattr(state, name)
            if new[: len(old)] != old:
                raise HistoryConflictError(
                    f"this would change the saved {name.replace('_', ' ')}, which is never "
                    "overwritten"
                )
        self._write(state)


def export_state(state: ProjectState) -> bytes:
    """Everything needed to carry on in a later session, as one JSON file."""
    return json.dumps(
        {
            "format": EXPORT_FORMAT,
            "version": EXPORT_VERSION,
            "state": state.model_dump(mode="json"),
        },
        indent=2,
        ensure_ascii=False,
    ).encode("utf-8")


def import_state(raw: bytes) -> ProjectState:
    """Read an export. Raises ValueError with a plain-English reason if it cannot be used."""
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise ValueError("this is not a saved progress file") from error
    if not isinstance(payload, dict) or payload.get("format") != EXPORT_FORMAT:
        raise ValueError("this is not a saved progress file")
    if payload.get("version") != EXPORT_VERSION:
        raise ValueError(
            f"this file uses format version {payload.get('version')}, which is unknown"
        )
    try:
        state = ProjectState.model_validate(payload["state"])
    except (KeyError, ValidationError) as error:
        raise ValueError("this saved progress file is damaged") from error
    known = {version.version_id for version in state.versions}
    if not set(state.active.values()) <= known:
        raise ValueError("this saved progress file is damaged: a version in use is missing")
    return state


def choose_backend(override: str | None, host: str | None) -> str:
    """Pick the backend. On a shared hosted app each visitor's data stays in their own session."""
    if override:
        if override not in (SQLITE, SESSION):
            raise ValueError(f"unknown storage backend '{override}'")
        return override
    hostname = (host or "").rsplit(":", 1)[0] if not (host or "").startswith("[") else "[::1]"
    return SQLITE if hostname in LOCAL_HOSTS else SESSION
