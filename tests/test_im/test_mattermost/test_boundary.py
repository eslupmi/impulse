"""Mattermost import boundary and resource checks."""

import ast
import os
import subprocess
import sys
from importlib.util import resolve_name
from pathlib import Path

import pytest

from app.im.providers.mattermost import TEMPLATE_NAMES, MattermostProvider
from tests.test_im.test_provider_seam import config_for


def test_missing_token_names_the_variable_without_its_value():
    with pytest.raises(ValueError, match='MATTERMOST_ACCESS_TOKEN') as error:
        MattermostProvider(config_for('mattermost'), {'MATTERMOST_ACCESS_TOKEN': ''})
    assert 'test-token' not in str(error.value)


def test_resources_load_outside_the_checkout(tmp_path):
    root = Path(__file__).resolve().parents[3]
    script = """
import sys
class NoPrivateCore:
    def find_spec(self, fullname, *args):
        if fullname.startswith(('app.config','app.incident','app.queue','app.logging','app.time', 'app.ui', 'app.http_client', 'app.im.application', 'app.im.users')):
            raise AssertionError(fullname)
sys.meta_path.insert(0, NoPrivateCore())
from app.im.providers.mattermost import MattermostProvider, TEMPLATE_NAMES
from app.im.providers.mattermost.authentication import MattermostAuthentication
from app.im.providers.none import NoneProvider
for name in TEMPLATE_NAMES:
    assert MattermostProvider.template_source(name).strip()
assert NoneProvider.descriptor.provider_id == 'none'
"""
    result = subprocess.run(
        [sys.executable, '-c', script], cwd=tmp_path,
        env={**os.environ, 'PYTHONPATH': str(root) + os.pathsep + os.environ.get('PYTHONPATH', '')},
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


def test_mattermost_import_boundary_and_core_selection():
    import app.im.providers.mattermost as mattermost

    root = Path(mattermost.__file__).parent
    for path in root.rglob('*.py'):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node, ast.ImportFrom):
                modules = [
                    resolve_name('.' * node.level + (node.module or ''), 'app.im.providers.mattermost')
                    if node.level else node.module or ''
                ]
            elif isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            else:
                modules = []
            for module in modules:
                assert not module.startswith('app.') or module == 'app.im.plugin_api' or module.startswith('app.im.providers.mattermost'), (path, module)
    for path in root.parents[2].rglob('*.py'):
        if 'providers' in path.parts or path.name == 'registry.py':
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or '').startswith('app.im.providers.mattermost'), path
            if isinstance(node, ast.Compare):
                assert not any(
                    (isinstance(item, ast.Constant) and item.value == 'mattermost')
                    or (isinstance(item, ast.Attribute) and item.attr == 'MATTERMOST')
                    for item in ast.walk(node)
                ), path
    assert 'body' in TEMPLATE_NAMES and len(TEMPLATE_NAMES) == 13
