"""The interface every calculation backend implements."""

from abc import ABC, abstractmethod

from bom_to_pcf.models import EmissionFactor, LciLine, ResultLine


class Engine(ABC):
    """Turns inventory lines into impacts. Everything else about a result is shared."""

    name: str

    @abstractmethod
    def impacts(self, lines: list[LciLine], factors: dict[str, EmissionFactor]) -> list[ResultLine]:
        """Return each line with its impact, or None if its factor has no value yet."""
