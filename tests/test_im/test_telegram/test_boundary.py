"""Telegram import boundary and packaged resource checks."""
import ast
import os
import subprocess
import sys
from importlib.util import resolve_name
from pathlib import Path

from app.im.providers.telegram import TEMPLATE_NAMES


def test_resources_and_openid_import_outside_checkout(tmp_path):
    root = Path(__file__).resolve().parents[3]
    script = """
import sys
class NoPrivateCore:
    def find_spec(self, fullname, *args):
        if fullname.startswith(('app.config', 'app.incident', 'app.queue', 'app.logging', 'app.time', 'app.ui', 'app.http_client', 'app.im.application', 'app.im.users')):
            raise AssertionError(fullname)
sys.meta_path.insert(0, NoPrivateCore())
from app.im.providers.telegram import TelegramProvider, TEMPLATE_NAMES
from app.im.providers.telegram.authentication import TelegramAuthentication
for name in TEMPLATE_NAMES:
    assert TelegramProvider.template_source(name).strip()
assert TelegramAuthentication.name == 'telegram'
"""
    result = subprocess.run(
        [sys.executable, '-c', script], cwd=tmp_path,
        env={**os.environ, 'PYTHONPATH': str(root) + os.pathsep + os.environ.get('PYTHONPATH', '')},
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


def test_telegram_import_boundary_and_core_selection():
    import app.im.providers.telegram as telegram

    root = Path(telegram.__file__).parent
    for path in root.rglob('*.py'):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node, ast.ImportFrom):
                modules = [resolve_name('.' * node.level + (node.module or ''),
                                        'app.im.providers.telegram') if node.level else node.module or '']
            elif isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            else:
                modules = []
            for module in modules:
                assert not module.startswith('app.') or module == 'app.im.plugin_api' or module.startswith('app.im.providers.telegram'), (path, module)
    for path in root.parents[2].rglob('*.py'):
        if 'providers' in path.parts or path.name == 'registry.py':
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or '').startswith('app.im.providers.telegram'), path
            if isinstance(node, ast.Compare):
                assert not any(
                    (isinstance(item, ast.Constant) and item.value == 'telegram')
                    or (isinstance(item, ast.Attribute) and item.attr == 'TELEGRAM')
                    for item in ast.walk(node)
                ), path
    assert len(TEMPLATE_NAMES) == 13
