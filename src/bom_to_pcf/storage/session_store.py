"""Keeps state in the visitor's session, for the hosted app. Download and re-upload to continue."""

from collections.abc import MutableMapping

from bom_to_pcf.models import ProjectState
from bom_to_pcf.storage.base import StorageBackend

STATE_KEY = "saved_project_state"


class SessionStore(StorageBackend):
    def __init__(self, session: MutableMapping) -> None:
        self._session = session

    def load(self) -> ProjectState:
        saved = self._session.get(STATE_KEY)
        return ProjectState.model_validate_json(saved) if saved else ProjectState()

    def _write(self, state: ProjectState) -> None:
        self._session[STATE_KEY] = state.model_dump_json()
