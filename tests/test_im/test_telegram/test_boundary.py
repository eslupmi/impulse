"""Telegram import boundary and packaged resource checks."""
import os
import subprocess
import sys
from pathlib import Path

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
