import re
from typing import ClassVar

VERSION_RE = re.compile(r'^v(\d+)\.(\d+)\.(\d+)$')


class SchemaMigrator:
    """Shared upgrade and downgrade chain for versioned on-disk files."""

    MIGRATION_CHAIN: ClassVar[dict[str, str]] = {}
    REVERSE_MIGRATION_CHAIN: ClassVar[dict[str, str]] = {}
    DOWNGRADE_FLOOR: ClassVar[str] = 'v0.0.0'

    def __init__(self) -> None:
        self._migration_methods: dict = {}
        self._filename_migration_methods: dict = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.REVERSE_MIGRATION_CHAIN = {dst: src for src, dst in cls.MIGRATION_CHAIN.items()}

    @classmethod
    def actual_version(cls) -> str:
        raise NotImplementedError

    def _migrate_data(self, data: dict, from_version: str, to_version: str) -> dict:
        if not self.MIGRATION_CHAIN:
            data['version'] = to_version
            return data

        migration_path = self._get_migration_path(from_version, to_version)
        current_data = data.copy()
        for i in range(len(migration_path) - 1):
            current_data = self._apply_single_migration(
                current_data, migration_path[i], migration_path[i + 1]
            )
        return current_data

    def _get_migration_path(self, from_version: str, to_version: str) -> list[str]:
        if from_version == to_version:
            return [from_version]

        forward = self._walk_chain(from_version, to_version, self.MIGRATION_CHAIN)
        if forward is not None:
            return forward

        reverse = self._walk_chain(from_version, to_version, self.REVERSE_MIGRATION_CHAIN)
        if reverse is not None:
            return reverse

        raise ValueError(f'No migration path from {from_version} to {to_version}')

    @staticmethod
    def _walk_chain(from_version: str, to_version: str, chain: dict[str, str]) -> list[str] | None:
        path = [from_version]
        current = from_version
        while current != to_version:
            next_version = chain.get(current)
            if next_version is None:
                return None
            path.append(next_version)
            current = next_version
        return path

    def _apply_single_migration(self, data: dict, from_version: str, to_version: str) -> dict:
        method_key = f"{from_version}_to_{to_version}"
        migrated_data = self._migration_methods[method_key](data)
        migrated_data['version'] = to_version
        return migrated_data

    def _apply_filename_migrations(self, file_path: str, data: dict, from_version: str, to_version: str) -> str:
        if not self.MIGRATION_CHAIN:
            return file_path

        migration_path = self._get_migration_path(from_version, to_version)
        current_path = file_path
        for i in range(len(migration_path) - 1):
            method_key = f"{migration_path[i]}_to_{migration_path[i + 1]}"
            filename_method = self._filename_migration_methods.get(method_key)
            if filename_method:
                current_path = filename_method(current_path, data)
        return current_path

    @classmethod
    def schema_versions(cls) -> set[str]:
        return set(cls.MIGRATION_CHAIN.keys()) | set(cls.MIGRATION_CHAIN.values())

    @classmethod
    def resolve_downgrade_target(cls, version_arg: str | None) -> str:
        if version_arg is None or version_arg == '':
            actual = cls.actual_version()
            previous = cls.REVERSE_MIGRATION_CHAIN.get(actual)
            if previous is None:
                raise ValueError(f'No previous schema version to downgrade from {actual}')
            target = previous
        else:
            target = cls._map_release_to_schema(version_arg)

        if not cls._version_at_or_above_floor(target):
            raise ValueError(
                f'Downgrade target {target} is below supported floor {cls.DOWNGRADE_FLOOR}'
            )
        return target

    @classmethod
    def _map_release_to_schema(cls, version: str) -> str:
        schemas = cls.schema_versions()
        if version in schemas:
            return version

        match = VERSION_RE.match(version)
        if not match:
            raise ValueError(f'Unknown version: {version}')

        major, minor, _ = match.groups()
        prefix = f'v{major}.{minor}.'
        candidates = sorted(
            v for v in schemas
            if v.startswith(prefix) and VERSION_RE.match(v)
        )
        if not candidates:
            raise ValueError(f'No schema version for release {version}')
        return candidates[0]

    @classmethod
    def _version_at_or_above_floor(cls, version: str) -> bool:
        match = VERSION_RE.match(version)
        floor = VERSION_RE.match(cls.DOWNGRADE_FLOOR)
        if not match or not floor:
            return False
        return tuple(int(x) for x in match.groups()) >= tuple(int(x) for x in floor.groups())

    @classmethod
    def _version_newer_than(cls, current: str, target: str) -> bool:
        if current == target:
            return False
        return cls._walk_chain(current, target, cls.REVERSE_MIGRATION_CHAIN) is not None
