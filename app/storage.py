"""Filesystem and S3 persistence for application state under DATA_PATH."""
import builtins
from collections.abc import Callable
from contextlib import contextmanager
import io
import os
from pathlib import Path

import boto3  # type: ignore[import-untyped]
from botocore.config import Config  # type: ignore[import-untyped]
from botocore.exceptions import BotoCoreError, ClientError  # type: ignore[import-untyped]

from app.config.environment import EnvironmentConfig, get_environment_config


class FileStorage:
    """Persist application state using standard filesystem operations."""

    def open(self, path, mode='r', encoding=None):
        return builtins.open(path, mode, encoding=encoding)

    def exists(self, path):
        return os.path.exists(path)

    def makedirs(self, path, exist_ok=False):
        return os.makedirs(path, exist_ok=exist_ok)

    def listdir(self, path):
        return os.listdir(path)

    def walk(self, path):
        return os.walk(path)

    def remove(self, path):
        return os.remove(path)

    def rename(self, old_path, new_path):
        return os.rename(old_path, new_path)


class S3Storage:
    """Store whole state files in S3; directories are virtual object prefixes."""

    def __init__(self, config: EnvironmentConfig):
        self.root = os.path.abspath(config.data_path)
        self.bucket = config.s3_bucket
        self.prefix = config.s3_prefix.strip('/')
        self.endpoint_url = config.s3_endpoint_url
        self._client = None
        self.check_owned: Callable[[], bool] | None = None

    @property
    def client(self):
        if self._client is None:
            try:
                self._client = boto3.client(
                    's3', endpoint_url=self.endpoint_url,
                    config=Config(connect_timeout=5, read_timeout=5,
                                  retries={'mode': 'standard', 'total_max_attempts': 3}))
            except BotoCoreError as error:
                raise OSError(str(error)) from error
        return self._client

    def _key(self, path):
        path = os.fsdecode(path)
        absolute = os.path.abspath(path)
        if '..' in Path(path).parts or os.path.commonpath([self.root, absolute]) != self.root:
            raise ValueError('Storage paths must stay within DATA_PATH')
        relative = os.path.relpath(absolute, self.root)
        if relative == '.':
            return self.prefix
        return '/'.join(filter(None, (self.prefix, relative.replace(os.sep, '/'))))

    def _file_key(self, path):
        key = self._key(path)
        if key == self.prefix:
            raise IsADirectoryError(os.fspath(path))
        return key

    def _call(self, operation, **kwargs):
        if operation in {'put_object', 'copy_object', 'delete_object'} and self.check_owned is not None:
            if not self.check_owned():
                raise OSError('Storage lease is not owned by this instance')
        try:
            return getattr(self.client, operation)(Bucket=self.bucket, **kwargs)
        except ClientError as error:
            if error.response['Error']['Code'] == 'NoSuchKey':
                raise FileNotFoundError(str(error)) from error
            raise OSError(str(error)) from error
        except BotoCoreError as error:
            raise OSError(str(error)) from error

    @contextmanager
    def open(self, path, mode='r', encoding=None):
        """Read or replace a file; upload only after the writer exits successfully."""
        if mode not in {'r', 'rt', 'rb', 'w', 'wt', 'wb'}:
            raise ValueError('S3 storage supports only read and write modes')
        binary = 'b' in mode
        if binary and encoding is not None:
            raise ValueError('Binary mode does not take an encoding')
        key = self._file_key(path)
        content = b''
        if mode.startswith('r'):
            body = self._call('get_object', Key=key)['Body']
            try:
                content = body.read()
            except BotoCoreError as error:
                raise OSError(str(error)) from error
            finally:
                body.close()
        buffer = io.BytesIO(content) if binary else io.StringIO(content.decode(encoding or 'utf-8'), newline=None)
        with buffer:
            yield buffer
            if mode.startswith('w'):
                content = buffer.getvalue()
                if not binary:
                    content = content.encode(encoding or 'utf-8')
                self._call('put_object', Key=key, Body=content)

    def exists(self, path):
        key = self._key(path)
        if key != self.prefix:
            contents = self._call('list_objects_v2', Prefix=key, MaxKeys=1).get('Contents', [])
            if not contents:
                return False
            if any(item['Key'] == key or item['Key'].startswith(key + '/') for item in contents):
                return True
            # A sibling (e.g. name-old) can sort before name/; check that directory separately.
        prefix = key + '/' if key else ''
        return bool(self._call('list_objects_v2', Prefix=prefix, MaxKeys=1).get('Contents'))

    def makedirs(self, path, exist_ok=False):
        self._key(path)

    def _pages(self, path, delimiter=None):
        key = self._key(path)
        prefix = key + '/' if key else ''
        parameters = {'Bucket': self.bucket, 'Prefix': prefix}
        if delimiter is not None:
            parameters['Delimiter'] = delimiter
        try:
            for page in self.client.get_paginator('list_objects_v2').paginate(**parameters):
                yield prefix, page
        except (BotoCoreError, ClientError) as error:
            raise OSError(str(error)) from error

    @staticmethod
    def _relative(key, prefix):
        if not key.startswith(prefix):
            return None
        relative = key[len(prefix):].rstrip('/')
        if not relative or any(part in {'', '.', '..'} for part in relative.split('/')):
            return None
        return relative

    def listdir(self, path):
        names = set()
        for prefix, page in self._pages(path, delimiter='/'):
            entries = [entry['Key'] for entry in page.get('Contents', [])]
            entries.extend(entry['Prefix'] for entry in page.get('CommonPrefixes', []))
            for key in entries:
                relative = self._relative(key, prefix)
                if relative:
                    names.add(relative.split('/')[0])
        return sorted(names)

    def walk(self, path):
        tree = {}
        for prefix, page in self._pages(path):
            for entry in page.get('Contents', []):
                key = entry['Key']
                relative = self._relative(key, prefix)
                if relative is None:
                    continue
                parts = relative.split('/')
                directories = parts if key.endswith('/') else parts[:-1]
                tree.setdefault('', (set(), set()))
                for index, name in enumerate(directories):
                    parent = '/'.join(parts[:index])
                    directory = '/'.join(parts[:index + 1])
                    tree[parent][0].add(name)
                    tree.setdefault(directory, (set(), set()))
                if not key.endswith('/'):
                    tree['/'.join(parts[:-1])][1].add(parts[-1])
        for directory, (dirs, files) in sorted(tree.items()):
            root = os.path.join(os.fspath(path), *directory.split('/')) if directory else os.fspath(path)
            yield root, sorted(dirs), sorted(files)

    def remove(self, path):
        self._call('delete_object', Key=self._file_key(path))

    def rename(self, old_path, new_path):
        old_key, new_key = self._file_key(old_path), self._file_key(new_path)
        if old_key == new_key:
            return
        self._call('copy_object', Key=new_key, CopySource={'Bucket': self.bucket, 'Key': old_key})
        self._call('delete_object', Key=old_key)


_s3_config = None
_s3_storage = None


def get_storage(env_config=None) -> FileStorage | S3Storage:
    """Reuse the S3 client for the current environment configuration instance."""
    config = env_config if env_config is not None else get_environment_config()
    if getattr(config, 'storage_backend', 'filesystem') != 's3':
        return FileStorage()
    global _s3_config, _s3_storage
    if _s3_config is not config or _s3_storage is None:
        storage = S3Storage(config)
        _s3_config, _s3_storage = config, storage
    return _s3_storage
