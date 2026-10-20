from unittest.mock import Mock

import pytest

from app.config.config import UnifiedConfig
from app.migrator import MaintenanceMigrator


def test_incident_and_maintenance_keep_independent_schema_versions():
    assert UnifiedConfig(Mock()).INCIDENT_ACTUAL_VERSION == 'v3.7.0'
    assert MaintenanceMigrator.ACTUAL_VERSION == 'v3.8.0'


@pytest.mark.parametrize(
    'version_arg, expected',
    [
        (None, 'v3.7.0'),
        ('', 'v3.7.0'),
        ('v3.7.0', 'v3.7.0'),
        ('v3.7.3', 'v3.7.0'),
        ('v3.8.0', 'v3.8.0'),
        ('v3.8.3', 'v3.8.0'),
    ],
)
def test_maintenance_downgrade_target(version_arg, expected):
    assert MaintenanceMigrator.resolve_downgrade_target(version_arg) == expected


@pytest.mark.parametrize(
    'version_arg, message',
    [
        ('v3.6.0', 'No schema version for release'),
        ('v4.0.0', 'No schema version for release'),
        ('v03.7.0', 'No schema version for release'),
        ('not-a-version', 'Unknown version'),
    ],
)
def test_maintenance_rejects_unsupported_downgrade_targets(version_arg, message):
    with pytest.raises(ValueError, match=message):
        MaintenanceMigrator.resolve_downgrade_target(version_arg)
