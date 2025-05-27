from typing import Union

from app.im.chain.chain import Chain
from app.im.chain.schedule_chain import ScheduleChain
from app.im.chain.google_calendar_chain import GoogleCalendarChain
from app.logging import logger


class ChainFactory:
    @staticmethod
    def _create_chain(name: str, config: Union[dict, list]):
        """
        Create and return a Chain, ScheduleChain or GoogleCalendarChain instance 
        based on the configuration.
        """
        if 'type' in config
            if config.get('type') == 'cloud' and config.get('provider') == 'google':
                chain = GoogleCalendarChain(name, config)
                if isinstance(chain, GoogleCalendarChain):
                    chain.start_sync()
                return chain
            elif config.get('type') == 'schedule':
                return ScheduleChain(
                    name=name,
                    timezone=config.get('timezone', ScheduleChain.DEFAULT_TIMEZONE),
                    schedule=config.get('schedule', []),
                )
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
