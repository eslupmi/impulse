from html.parser import HTMLParser

import yaml


class NoAliasDumper(yaml.Dumper):
    """
    A Dumper that does not use aliases. This is useful when you want to dump
    a data structure to a YAML file, and you don't want to use aliases to
    represent duplicate data.
    """

    def ignore_aliases(self, data):
        return True


class HTMLTextExtractor(HTMLParser):
    """HTML parser to extract plain text from HTML content."""

    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.in_br = False

    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'br':
            self.text_parts.append('\n')
        elif tag.lower() in ['p', 'div']:
            if self.text_parts and not self.text_parts[-1].endswith('\n'):
                self.text_parts.append('\n')

    def handle_endtag(self, tag):
        if tag.lower() in ['p', 'div']:
            if self.text_parts and not self.text_parts[-1].endswith('\n'):
                self.text_parts.append('\n')

    def handle_data(self, data):
        self.text_parts.append(data)

    def get_text(self):
        return ''.join(self.text_parts)
