"""Telegram import boundary and packaged resource checks."""
import subprocess
import sys

def test_resources_and_openid_import_outside_checkout(tmp_path):
    script = """
import sys
class NoCore:
    def find_spec(self, fullname, *args):
        if fullname == 'app' or fullname.startswith('app.'):
            raise AssertionError(fullname)
sys.meta_path.insert(0, NoCore())
from impulse_telegram import TelegramProvider, TEMPLATE_NAMES
from impulse_telegram.authentication import TelegramAuthentication
for name in TEMPLATE_NAMES:
    assert TelegramProvider.template_source(name).strip()
assert TelegramAuthentication.name == 'telegram'
"""
    result = subprocess.run(
        [sys.executable, '-I', '-c', script], cwd=tmp_path,
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
