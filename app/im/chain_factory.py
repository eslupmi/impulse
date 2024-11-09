import logging
from typing import Union

from app.im.chain import Chain
from app.im.schedule_chain import ScheduleChain

logger = logging.getLogger(__name__)


class ChainFactory:
    @staticmethod
    def _create_chain(name: str, config: Union[dict, list]):
        """
        Create and return a Chain or ScheduleChain instance based on the configuration.
        """
        if 'type' in config and config.get('type') == 'schedule':
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
