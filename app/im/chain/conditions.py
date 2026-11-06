"""Shared chain callers use the selected edition's small condition policy."""
from importlib import import_module

from pydantic import BaseModel

from app.edition import EDITION

_policy = import_module(f'{EDITION}.app.im.chain.conditions')
validate_step = _policy.validate_step
matches_step = _policy.matches_step


def validate_steps(steps):
    for step in steps or []:
        validate_step(step)


def validate_chains(chains):
    for config in chains.values():
        if isinstance(config, list):
            validate_steps(config)
            continue
        if isinstance(config, BaseModel):
            config = config.model_dump(by_alias=True)
        if not isinstance(config, dict):
            continue
        if config.get('type') == 'schedule':
            for entry in config.get('schedule') or []:
                validate_steps(entry.get('steps'))
        elif config.get('type') == 'cloud':
            validate_steps(config.get('default_steps'))
