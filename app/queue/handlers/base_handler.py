from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.queue.queue import AsyncQueue
    from app.im.application import Application
    from app.incident.incidents import Incidents


class BaseHandler(ABC):
    """
    Base class for all handlers

    :param queue: AsyncQueue instance
    :param application: Application instance
    :param incidents: Incidents instance
    """
    __slots__ = ['queue', 'app', 'incidents']

    def __init__(self, queue: 'AsyncQueue', application: 'Application', incidents: 'Incidents'):
        self.queue = queue
        self.app = application
        self.incidents = incidents

    @abstractmethod
    async def handle(self, *args, **kwargs):
        pass
