"""Mattermost import boundary and resource checks."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.im.providers.mattermost import MattermostProvider
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
