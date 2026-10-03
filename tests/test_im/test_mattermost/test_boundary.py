"""Mattermost import boundary and resource checks."""

import subprocess
import sys

import pytest

from impulse_mattermost import MattermostProvider
from tests.test_im.test_provider_seam import config_for


def test_missing_token_names_the_variable_without_its_value():
    with pytest.raises(ValueError, match='MATTERMOST_ACCESS_TOKEN') as error:
        MattermostProvider(config_for('mattermost'), {'MATTERMOST_ACCESS_TOKEN': ''})
    assert 'test-token' not in str(error.value)


def test_resources_load_outside_the_checkout(tmp_path):
    script = """
import sys
class NoCore:
    def find_spec(self, fullname, *args):
        if fullname == 'app' or fullname.startswith('app.'):
            raise AssertionError(fullname)
sys.meta_path.insert(0, NoCore())
from impulse_mattermost import MattermostProvider, TEMPLATE_NAMES
from impulse_mattermost.authentication import MattermostAuthentication
for name in TEMPLATE_NAMES:
    assert MattermostProvider.template_source(name).strip()
"""
    result = subprocess.run(
        [sys.executable, '-I', '-c', script], cwd=tmp_path,
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
