from typing import Union

from app.im.chain.chain import Chain
from app.im.chain.schedule_chain import ScheduleChain
from app.im.chain.google_calendar_chain import GoogleCalendarChain
from app.logging import logger


class ChainFactory:
    @staticmethod
    def _create_chain(name: str, config: Union[dict, list]):
        """
        Create and return a Chain or ScheduleChain instance based on the configuration.
        """
        if 'type' in config and config.get('type') == 'schedule':
            chain = GoogleCalendarChain(name, config) if config.get('provider') == 'google' else ScheduleChain(
                name=name,
                timezone=config.get('timezone', ScheduleChain.DEFAULT_TIMEZONE),
                schedule=config.get('schedule', []),
            )
            # Start the sync task if it's a Google Calendar chain
            if isinstance(chain, GoogleCalendarChain):
                chain.start_sync()
            return chain
        else:
            return Chain(name, config)

    @classmethod
    def generate(cls, chains_dict):
        logger.info('Creating chains')
        chains = {
            name: cls._create_chain(name, config)
            for name, config in chains_dict.items()
        }
        return chains
