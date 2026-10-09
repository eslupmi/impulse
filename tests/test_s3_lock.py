"""Conditional S3 lease and real heartbeat-thread regressions."""
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import io
import json
import threading
from unittest.mock import ANY, AsyncMock, patch

import boto3
from botocore.exceptions import EndpointConnectionError
from botocore.response import StreamingBody
from botocore.stub import Stubber
import pytest

from app.config.environment import EnvironmentConfig
from app.s3_lock import S3Lock
from app.storage import S3Storage


BUCKET = 'state-bucket'
KEY = 'deployment/.lock.d/lease.json'
SERVER_NOW = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)


@pytest.fixture
def lease_lock(tmp_path):
    config = EnvironmentConfig(storage_backend='s3', s3_bucket=BUCKET,
                               s3_prefix='deployment', data_path=str(tmp_path))
    client = boto3.client('s3', region_name='us-east-1',
                          aws_access_key_id='test', aws_secret_access_key='test')
    with patch('app.storage.boto3.client', return_value=client):
        storage = S3Storage(config)
        assert storage.client is client
    lock = S3Lock(storage)
    with Stubber(client) as stubber:
        yield lock, stubber, client
        lock._lose()
        if lock._heartbeat_thread is not None:
            lock._heartbeat_thread.join(timeout=1)
            assert not lock._heartbeat_thread.is_alive()
        stubber.assert_no_pending_responses()


def add_missing(stubber):
    stubber.add_client_error('get_object', service_error_code='NoSuchKey', http_status_code=404,
                            expected_params={'Bucket': BUCKET, 'Key': KEY})


def add_lease(stubber, age=0, *, response_changes=None, body=None):
    payload = {'owner': 'other-owner', 'revision': 'other-revision', 'host': 'other-host', 'pid': '123'}
    content = json.dumps(payload).encode() if body is None else body
    stream = io.BytesIO(content)
    response = {'Body': StreamingBody(stream, len(content)), 'ETag': '"old"',
                'LastModified': SERVER_NOW - timedelta(seconds=age),
                'ResponseMetadata': {'HTTPStatusCode': 200,
                                     'HTTPHeaders': {'date': format_datetime(SERVER_NOW, usegmt=True)}}}
    if response_changes:
        for key, value in response_changes.items():
            if value is None:
                response.pop(key, None)
            else:
                response[key] = value
    stubber.add_response('get_object', response, {'Bucket': BUCKET, 'Key': KEY})
    return stream


def add_put(stubber, etag='"first"', **condition):
    stubber.add_response('put_object', {'ETag': etag},
                         {'Bucket': BUCKET, 'Key': KEY, 'Body': ANY, **condition})


@pytest.mark.asyncio
async def test_absent_lease_uses_conditional_create_and_release(lease_lock):
    lock, stubber, _ = lease_lock
    add_missing(stubber)
    add_put(stubber, IfNoneMatch='*')
    assert lock.acquire_lock()
    assert lock.check_owned()
    thread = lock._heartbeat_thread
    assert thread.is_alive() and thread.daemon
    assert lock.can_take_over_lock() is False
    stubber.add_response('delete_object', {}, {'Bucket': BUCKET, 'Key': KEY, 'IfMatch': '"first"'})
    await lock.release_lock()
    assert not lock.check_owned()
    assert not thread.is_alive()


@pytest.mark.parametrize('code,status', [('PreconditionFailed', 412), ('ConditionalRequestConflict', 409),
                                        ('AccessDenied', 403), ('InternalError', 500), ('NotImplemented', 501)])
def test_failed_conditional_create_never_claims_ownership(lease_lock, code, status):
    lock, stubber, _ = lease_lock
    add_missing(stubber)
    stubber.add_client_error('put_object', service_error_code=code, http_status_code=status,
                            expected_params={'Bucket': BUCKET, 'Key': KEY, 'Body': ANY, 'IfNoneMatch': '*'})
    assert not lock.acquire_lock()
    assert not lock.check_owned()
    assert lock._heartbeat_thread is None


@pytest.mark.parametrize('age,expected', [(0, True), (18, True), (19, True), (20, False)])
def test_staleness_uses_server_timestamps_and_rounding_margin(lease_lock, age, expected):
    lock, stubber, _ = lease_lock
    stream = add_lease(stubber, age=age)
    with patch('app.s3_lock.time.time', return_value=-1e12):
        assert lock.is_locked() is expected
    assert stream.closed


def test_fresh_lease_is_not_overwritten(lease_lock):
    lock, stubber, _ = lease_lock
    add_lease(stubber, age=19)
    assert not lock.acquire_lock()


@pytest.mark.asyncio
async def test_stale_lease_takeover_compares_observed_etag(lease_lock):
    lock, stubber, _ = lease_lock
    add_lease(stubber, age=20)
    add_put(stubber, etag='"takeover"', IfMatch='"old"')
    assert lock.acquire_lock()
    stubber.add_response('delete_object', {}, {'Bucket': BUCKET, 'Key': KEY, 'IfMatch': '"takeover"'})
    await lock.release_lock()


@pytest.mark.parametrize('code,status', [('PreconditionFailed', 412), ('ConditionalRequestConflict', 409)])
def test_takeover_loses_to_concurrent_renewal(lease_lock, code, status):
    lock, stubber, _ = lease_lock
    add_lease(stubber, age=30)
    stubber.add_client_error('put_object', service_error_code=code, http_status_code=status,
                            expected_params={'Bucket': BUCKET, 'Key': KEY, 'Body': ANY, 'IfMatch': '"old"'})
    assert not lock.acquire_lock()
    assert not lock.check_owned()


@pytest.mark.parametrize('code,status', [('404', 404), ('NoSuchBucket', 404), ('AccessDenied', 403),
                                        ('InternalError', 500)])
def test_read_failures_are_not_absent_or_unlocked(lease_lock, code, status):
    lock, stubber, _ = lease_lock
    for _ in range(3):
        stubber.add_client_error('get_object', service_error_code=code, http_status_code=status)
    assert lock.is_locked()
    assert not lock.acquire_lock()
    assert lock.get_lock_info() == (None, None)


def test_missing_lease_and_remote_owner_info(lease_lock):
    lock, stubber, _ = lease_lock
    add_missing(stubber)
    assert not lock.is_locked()
    add_missing(stubber)
    assert lock.get_lock_info() == (None, None)
    add_lease(stubber)
    assert lock.get_lock_info() == ('other-host', '123')


@pytest.mark.parametrize('changes,body', [({}, b'invalid json'), ({}, b'{}'),
                                        ({'ETag': None}, None), ({'ETag': '*'}, None), ({'LastModified': None}, None),
                                        ({'ResponseMetadata': {'HTTPHeaders': {}}}, None),
                                        ({'ResponseMetadata': {'HTTPHeaders': {'date': 'bad-date'}}}, None),
                                        ({'LastModified': datetime(2026, 10, 8)}, None)])
def test_malformed_lease_fails_closed(lease_lock, changes, body):
    lock, stubber, _ = lease_lock
    streams = [add_lease(stubber, response_changes=changes, body=body) for _ in range(2)]
    assert lock.is_locked()
    assert not lock.acquire_lock()
    assert all(stream.closed for stream in streams)


def test_network_errors_fail_closed(lease_lock):
    lock, _, client = lease_lock
    with patch.object(client, 'get_object', side_effect=EndpointConnectionError(endpoint_url='https://s3.example')):
        assert lock.is_locked()
        assert not lock.acquire_lock()


@pytest.mark.asyncio
async def test_each_renewal_changes_revision_and_uses_latest_etag(lease_lock):
    lock, stubber, client = lease_lock
    add_missing(stubber)
    add_put(stubber, IfNoneMatch='*')
    add_put(stubber, etag='"renewed"', IfMatch='"first"')
    with patch.object(client, 'put_object', wraps=client.put_object) as writes:
        assert lock.acquire_lock()
        assert lock._renew()
    first, second = [json.loads(call.kwargs['Body']) for call in writes.call_args_list]
    assert first['owner'] == second['owner']
    assert first['revision'] != second['revision']
    stubber.add_response('delete_object', {}, {'Bucket': BUCKET, 'Key': KEY, 'IfMatch': '"renewed"'})
    await lock.release_lock()


@pytest.mark.parametrize('code,status', [('PreconditionFailed', 412), ('ConditionalRequestConflict', 409),
                                        ('AccessDenied', 403), ('InternalError', 500)])
def test_renewal_failure_irreversibly_loses_ownership(lease_lock, code, status):
    lock, stubber, _ = lease_lock
    add_missing(stubber)
    add_put(stubber, IfNoneMatch='*')
    assert lock.acquire_lock()
    stubber.add_client_error('put_object', service_error_code=code, http_status_code=status,
                            expected_params={'Bucket': BUCKET, 'Key': KEY, 'Body': ANY, 'IfMatch': '"first"'})
    assert not lock._renew()
    assert not lock.check_owned()
    assert not lock._renew()


def test_expired_local_deadline_cannot_renew_or_resume(lease_lock):
    lock, _, _ = lease_lock
    lock._active = True
    lock._deadline = 100
    with patch('app.s3_lock.time.monotonic', return_value=100):
        assert not lock.check_owned()
        assert not lock._renew()
    with patch('app.s3_lock.time.monotonic', return_value=90):
        assert not lock.check_owned()


@pytest.mark.asyncio
async def test_late_renewal_response_does_not_extend_expired_ownership(lease_lock):
    lock, stubber, client = lease_lock
    clock = [100.0]
    add_missing(stubber)
    add_put(stubber, IfNoneMatch='*')
    add_put(stubber, etag='"late"', IfMatch='"first"')
    with patch('app.s3_lock.time.monotonic', side_effect=lambda: clock[0]):
        assert lock.acquire_lock()
        clock[0] = 106
        actual_put = client.put_object

        def late_put(**kwargs):
            response = actual_put(**kwargs)
            clock[0] = 119
            return response

        with patch.object(client, 'put_object', side_effect=late_put):
            assert not lock._renew()
        assert not lock.check_owned()
        clock[0] = 110
        assert not lock.check_owned()
    stubber.add_response('delete_object', {}, {'Bucket': BUCKET, 'Key': KEY, 'IfMatch': '"late"'})
    await lock.release_lock()


@pytest.mark.asyncio
async def test_late_acquisition_response_never_starts_heartbeat(lease_lock):
    lock, stubber, client = lease_lock
    clock = [100.0]
    add_missing(stubber)
    add_put(stubber, IfNoneMatch='*')
    actual_put = client.put_object

    def late_put(**kwargs):
        response = actual_put(**kwargs)
        clock[0] = 119
        return response

    with patch('app.s3_lock.time.monotonic', side_effect=lambda: clock[0]), \
            patch.object(client, 'put_object', side_effect=late_put):
        assert not lock.acquire_lock()
        assert not lock.check_owned()
        assert lock._heartbeat_thread is None
    stubber.add_response('delete_object', {}, {'Bucket': BUCKET, 'Key': KEY, 'IfMatch': '"first"'})
    await lock.release_lock()


@pytest.mark.asyncio
@pytest.mark.parametrize('code,status', [('PreconditionFailed', 412), ('ConditionalRequestConflict', 409),
                                        ('NoSuchKey', 404), ('NotImplemented', 501)])
async def test_release_never_deletes_a_successor_or_falls_back(lease_lock, code, status):
    lock, stubber, _ = lease_lock
    add_missing(stubber)
    add_put(stubber, IfNoneMatch='*')
    assert lock.acquire_lock()
    stubber.add_client_error('delete_object', service_error_code=code, http_status_code=status,
                            expected_params={'Bucket': BUCKET, 'Key': KEY, 'IfMatch': '"first"'})
    await lock.release_lock()
    assert not lock.check_owned()
    assert lock._etag is None


@pytest.mark.asyncio
async def test_heartbeat_renews_while_event_loop_is_blocked(lease_lock):
    lock, stubber, client = lease_lock
    lock.HEARTBEAT_SEC = 0.01
    add_missing(stubber)
    writes = []
    renewed = threading.Event()

    def write(**kwargs):
        writes.append(kwargs)
        if len(writes) > 1:
            renewed.set()
        return {'ETag': f'"etag-{len(writes)}"'}

    with patch.object(client, 'put_object', side_effect=write):
        assert lock.acquire_lock()
        thread = lock._heartbeat_thread
        # Deliberately block this async function: heartbeat must run on its own thread.
        assert renewed.wait(timeout=1)
        assert lock.check_owned()
        stubber.add_response('delete_object', {}, {'Bucket': BUCKET, 'Key': KEY, 'IfMatch': ANY})
        await lock.release_lock()
    assert not thread.is_alive()
    assert writes[0]['IfNoneMatch'] == '*'
    assert writes[1]['IfMatch'] == '"etag-1"'
    revisions = [json.loads(write['Body'])['revision'] for write in writes]
    assert len(revisions) == len(set(revisions))


@pytest.mark.asyncio
async def test_wait_for_unlock_observes_release(lease_lock):
    lock, stubber, _ = lease_lock
    add_lease(stubber)
    add_missing(stubber)
    with patch('app.s3_lock.asyncio.sleep', new_callable=AsyncMock) as sleep:
        await lock.wait_for_unlock()
        sleep.assert_awaited_once_with(1)



def test_deadline_check_does_not_wait_for_inflight_renewal(lease_lock):
    lock, _, client = lease_lock
    clock = [100.0]
    started, complete = threading.Event(), threading.Event()
    lock._owner, lock._etag = 'owner', '"old"'
    lock._active, lock._deadline = True, 110
    result = []

    def delayed_put(**kwargs):
        assert kwargs['IfMatch'] == '"old"'
        started.set()
        assert complete.wait(timeout=1)
        return {'ETag': '"late"'}

    with patch('app.s3_lock.time.monotonic', side_effect=lambda: clock[0]), \
            patch.object(client, 'put_object', side_effect=delayed_put):
        thread = threading.Thread(target=lambda: result.append(lock._renew()))
        thread.start()
        try:
            assert started.wait(timeout=1)
            clock[0] = 111
            assert not lock.check_owned()
            assert not complete.is_set()
        finally:
            complete.set()
            thread.join(timeout=1)
        assert not thread.is_alive()
    assert result == [False]
    assert not lock.check_owned()


def test_scheduled_renewal_cannot_start_after_old_deadline(lease_lock):
    lock, _, _ = lease_lock
    lock._active, lock._deadline = True, 110
    with patch('app.s3_lock.time.monotonic', side_effect=[109, 111]):
        assert not lock._renew()
    assert not lock.check_owned()


@pytest.mark.asyncio
async def test_thread_start_failure_releases_only_its_conditional_lease(lease_lock):
    lock, stubber, _ = lease_lock
    add_missing(stubber)
    add_put(stubber, IfNoneMatch='*')
    with patch('app.s3_lock.threading.Thread.start', side_effect=RuntimeError('thread unavailable')):
        assert not lock.acquire_lock()
    assert not lock.check_owned()
    stubber.add_response('delete_object', {}, {'Bucket': BUCKET, 'Key': KEY, 'IfMatch': '"first"'})
    await lock.release_lock()


@pytest.mark.parametrize('etag', [None, '*'])
def test_conditional_write_without_usable_etag_never_claims_ownership(lease_lock, etag):
    lock, stubber, _ = lease_lock
    add_missing(stubber)
    stubber.add_response('put_object', {} if etag is None else {'ETag': etag},
                         {'Bucket': BUCKET, 'Key': KEY, 'Body': ANY, 'IfNoneMatch': '*'})
    assert not lock.acquire_lock()
    assert not lock.check_owned()
