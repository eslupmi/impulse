buttons = {
    # styles: default, danger, primary
    'chain': {
        'takeit': {
            'text': 'Take It',
            'style': 'primary'
        },
        'assigned': {
            'text': 'Take It',
            'style': 'default'
        },
        'release': {
            'text': 'Release',
            'style': 'primary'
        }
    },
    'freeze': {
        'inactive': {
            'text': 'Freeze',
            'style': 'default'
        },
        'inhibited': {
            'text': 'Inhibited',
            'style': 'default'
        },
        'options': [
            {'text': 'Tomorrow', 'value': 'tomorrow'},
            {'text': 'Next Monday', 'value': 'next_monday'},
            {'text': 'In Month', 'value': 'month'},
            {'text': 'In 6 months', 'value': '6months'}
        ]
    },
    'task': {
        'create': {
            'text': ':pushpin:',
            'style': 'default'
        }
    }
}




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
