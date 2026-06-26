import re

from app.logging import logger


class Matcher:
    re_type = re.compile(r'(?P<label>\w+)\s?(?P<type>=|!=|=~|!~)\s?"(?P<expr>.+)"')

    def __init__(self, string):
        m = Matcher.re_type.match(string)
        if not m:
            raise ValueError(
                f'Invalid matcher "{string}": use label op "value" with op =, !=, =~, or !~'
            )
        self.type = m.group('type')
        self.label = m.group('label')
        self.expr = m.group('expr')
        if self.type in ['=~', '!~']:
            try:
                self.regex = re.compile(self.expr)
            except re.error as exc:
                raise ValueError(f'Invalid regex in matcher "{string}"') from exc

    def matches(self, alert_state):
        common_labels = alert_state.get('commonLabels')
        if common_labels is None:
            label_value = None
        else:
            label_value = common_labels.get(self.label)

        if self.type == '=':
            return label_value == self.expr
        elif self.type == '!=':
            return label_value != self.expr
        elif self.type == '=~':
            if label_value is None:
                return False
            return bool(self.regex.match(label_value))
        elif self.type == '!~':
            if label_value is None:
                return True
            return not bool(self.regex.match(label_value))
        else:
            logger.warning(f'Unknown matcher type \"{self.type}\" in matcher \"{self.label} {self.type} {self.expr}\"')
            return False
