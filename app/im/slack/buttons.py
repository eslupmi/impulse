from app.config.config import get_config
from app.config.environment import get_environment_config
from app.im.slack.config import buttons
from app.time import format_freeze_expiration


def chain_attrs(chain_enabled, status):
    if chain_enabled:
        chain_text = buttons['chain']['takeit']['text']
        chain_style = buttons['chain']['takeit']['style']
    else:
        if status != 'resolved':
            chain_text = buttons['chain']['assigned']['text']
            chain_style = buttons['chain']['assigned']['style']
        else:
            chain_text = buttons['chain']['release']['text']
            chain_style = buttons['chain']['release']['style']
    return chain_text, chain_style
