from dataclasses import dataclass, field
from abc import ABC, abstractmethod


@dataclass
class Song:
    name: str
    artist: str
    album: str = ""
    duration: int = 0
    platform_id: str = ""


class BaseParser(ABC):
    @staticmethod
    @abstractmethod
    def can_parse(url: str) -> bool:
        ...

    @staticmethod
    @abstractmethod
    async def parse(url: str) -> list[Song]:
        ...
