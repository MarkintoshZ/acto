from abc import ABC, abstractmethod

from acto.common import OracleResult
from acto.snapshot import Snapshot


class Checker(ABC):

    @property
    @abstractmethod
    def name(self):
        raise NotImplementedError

    def __init__(self, **kwargs):
        pass

    @abstractmethod
    def check(self, generation: int, snapshot: Snapshot, prev_snapshot: Snapshot) -> OracleResult:
        raise NotImplementedError()
