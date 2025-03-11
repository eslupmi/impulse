from app.queue.handlers.alert_handler import AlertHandler
from app.queue.handlers.status_update_handler import StatusUpdateHandler
from app.queue.handlers.step_handler import StepHandler
from app.queue.handlers.update_handler import UpdateHandler


class QueueManager:
    """
    QueueManager class is responsible for handling the queue items.
    """
    __slots__ = ['queue', 'update_handler', 'step_handler', 'status_update_handler', 'alert_handler']

    def __init__(self, queue, application, incidents, webhooks, route_):
        """
        Initialize QueueManager object.

        :param queue: Queue object.
        :param application: Application object.
        :param incidents: Incidents object.
        :param webhooks: Webhooks object.
        :param route_: Route object
        """
        self.queue = queue
        self.update_handler = UpdateHandler(self.queue, application, incidents)
        self.step_handler = StepHandler(self.queue, application, incidents, webhooks)
        self.status_update_handler = StatusUpdateHandler(self.queue, application, incidents)
        self.alert_handler = AlertHandler(self.queue, application, incidents, route_)

    def handle_check_update(self, identifier: str):
        """
        Handle check update.
        :param identifier: String identifier.
        """
        self.update_handler.handle(identifier)

    def handle_step(self, uuid_: str, identifier: str):
        """
        Handle step.

        :param uuid_: String uuid.
        :param identifier: String identifier.
        """
        self.step_handler.handle(uuid_, identifier)

    def handle_status_update(self, uuid_: str):
        """
        Handle status update.
        :param uuid_: String uuid.
        """
        self.status_update_handler.handle(uuid_)

    def handle_alert(self, alert_state: dict):
        """
        Handle alert.
        :param alert_state: Dictionary alert_state.
        """
        self.alert_handler.handle(alert_state)

    def queue_handle(self):
        """
        Handle queue.
        The method handles the queue items. Calls the appropriate handler based on the type of the item.
        """
        if not self.queue.items:
            return

        type_, uuid_, identifier, data = self.queue.handle()
        if type_ is None:
            return

        if type_ == 'update_status':
            self.handle_status_update(uuid_)
        elif type_ == 'chain_step':
            self.handle_step(uuid_, identifier)
        elif type_ == 'check_update' and self.status_update_handler.app.type != 'telegram':
            self.handle_check_update(identifier)
        elif type_ == 'alert':
            self.handle_alert(data)
