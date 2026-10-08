"""Shared S3 lease using conditional object writes and deletes."""
import asyncio
from datetime import datetime
from email.utils import parsedate_to_datetime
import json
import os
import socket
import threading
import time
from uuid import uuid4

from botocore.exceptions import BotoCoreError, ClientError  # type: ignore[import-untyped]

from app.logging import logger
from app.storage import S3Storage


class S3Lock:
    HEARTBEAT_SEC = 6
    STALE_SEC = 18

    def __init__(self, storage: S3Storage):
        self._storage = storage
        self._key = '/'.join(filter(None, (storage.prefix, '.lock.d/lease.json')))
        self._hostname = socket.gethostname()
        self._pid = str(os.getpid())
        self._owner: str | None = None
        self._etag: str | None = None
        self._deadline = 0.0
        self._active = False
        self._mutex = threading.Lock()
        self._stop = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None

    def _read_lease(self):
        try:
            response = self._storage.client.get_object(Bucket=self._storage.bucket, Key=self._key)
        except ClientError as error:
            if error.response['Error']['Code'] == 'NoSuchKey':
                return None
            raise
        body = response['Body']
        try:
            lease = json.loads(body.read())
        finally:
            body.close()
        if not isinstance(lease, dict) or any(not isinstance(lease.get(name), str) or not lease[name]
                                               for name in ('owner', 'revision', 'host', 'pid')):
            raise ValueError('Malformed S3 lease')
        etag = response['ETag']
        modified = response['LastModified']
        headers = response['ResponseMetadata']['HTTPHeaders']
        server_now = parsedate_to_datetime(headers.get('date') or headers.get('Date'))
        if not isinstance(etag, str) or not etag or etag.strip() == '*' or not isinstance(modified, datetime):
            raise ValueError('Missing S3 lease metadata')
        if modified.utcoffset() is None or server_now.utcoffset() is None:
            raise ValueError('S3 lease timestamps must include time zones')
        return lease, etag, (server_now - modified).total_seconds()

    def _put_lease(self, **condition):
        lease = {'owner': self._owner, 'revision': uuid4().hex,
                 'host': self._hostname, 'pid': self._pid}
        response = self._storage.client.put_object(
            Bucket=self._storage.bucket, Key=self._key,
            Body=json.dumps(lease, separators=(',', ':')).encode('utf-8'), **condition)
        etag = response.get('ETag')
        if not isinstance(etag, str) or not etag or etag.strip() == '*':
            raise ValueError('S3 conditional lease write returned no usable ETag')
        return etag

    def _lose(self):
        self._active = False
        self._stop.set()

    def check_owned(self) -> bool:
        """Local, nonblocking deadline check; an expired lease cannot resume work."""
        if self._active:
            if time.monotonic() < self._deadline and not self._stop.is_set():
                return True
            self._lose()
        return False

    def acquire_lock(self) -> bool:
        with self._mutex:
            if self.check_owned():
                return True
            if self._heartbeat_thread is not None and self._heartbeat_thread.is_alive():
                return False
            try:
                current = self._read_lease()
                if current is not None and current[2] <= self.STALE_SEC + 1:
                    return False
                condition = {'IfNoneMatch': '*'} if current is None else {'IfMatch': current[1]}
                self._owner = uuid4().hex
                started = time.monotonic()
                self._etag = self._put_lease(**condition)
                self._deadline = started + self.STALE_SEC
                if time.monotonic() >= self._deadline:
                    self._lose()
                    return False
                self._stop = threading.Event()
                self._active = True
                self._heartbeat_thread = threading.Thread(
                    target=self._heartbeat, args=(self._stop,), name='impulse-s3-lease', daemon=True)
                self._heartbeat_thread.start()
                logger.debug('S3 lease acquired')
                return True
            except (BotoCoreError, ClientError, OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
                self._lose()
                logger.warning(f'S3 lease acquisition failed: {error}')
                return False

    def _renew(self) -> bool:
        with self._mutex:
            if not self.check_owned():
                return False
            previous_deadline = self._deadline
            started = time.monotonic()
            if started >= previous_deadline:
                self._lose()
                return False
            try:
                self._etag = self._put_lease(IfMatch=self._etag)
                if not self._active or self._stop.is_set() or time.monotonic() >= previous_deadline:
                    self._lose()
                    return False
                self._deadline = started + self.STALE_SEC
                return True
            except (BotoCoreError, ClientError, OSError, ValueError, TypeError, KeyError) as error:
                self._lose()
                logger.warning(f'S3 lease renewal failed: {error}')
                return False

    def _heartbeat(self, stop):
        while not stop.wait(self.HEARTBEAT_SEC):
            if not self._renew():
                break

    def is_locked(self) -> bool:
        try:
            current = self._read_lease()
            # HTTP Date and LastModified round to seconds; wait one extra second before takeover.
            return current is not None and current[2] <= self.STALE_SEC + 1
        except (BotoCoreError, ClientError, OSError, ValueError, TypeError, KeyError) as error:
            logger.warning(f'S3 lease read failed: {error}')
            return True

    def can_take_over_lock(self) -> bool:
        return False

    def get_lock_info(self) -> tuple[str | None, str | None]:
        try:
            current = self._read_lease()
            if current is not None:
                return current[0]['host'], current[0]['pid']
        except (BotoCoreError, ClientError, OSError, ValueError, TypeError, KeyError):
            pass
        return None, None

    def _release(self, owner, thread):
        with self._mutex:
            if self._owner != owner or self._active:
                return
        if thread is not None and thread.ident is not None:
            thread.join()
        with self._mutex:
            if self._owner != owner or self._active:
                return
            etag, self._etag = self._etag, None
            self._heartbeat_thread = None
            if etag is None:
                return
            try:
                self._storage.client.delete_object(Bucket=self._storage.bucket, Key=self._key, IfMatch=etag)
                logger.debug('S3 lease released')
            except (BotoCoreError, ClientError, OSError, ValueError, TypeError) as error:
                logger.warning(f'S3 lease release failed: {error}')

    async def release_lock(self):
        owner, thread = self._owner, self._heartbeat_thread
        self._lose()
        await asyncio.to_thread(self._release, owner, thread)

    async def wait_for_unlock(self):
        while await asyncio.to_thread(self.is_locked):
            await asyncio.sleep(1)
