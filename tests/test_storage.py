"""Storage contract tests use the SDK's Stubber, without an S3 service."""
import io
from unittest.mock import ANY, Mock, patch

import boto3
from botocore.exceptions import EndpointConnectionError
from botocore.response import StreamingBody
from botocore.stub import Stubber
from pydantic import ValidationError
import pytest

from app.config.environment import EnvironmentConfig
from app.storage import FileStorage, S3Storage, get_storage


@pytest.fixture
def s3_storage(tmp_path):
    config = EnvironmentConfig(storage_backend='s3', s3_bucket='state-bucket',
                               s3_prefix='deployment/', data_path=str(tmp_path))
    client = boto3.client('s3', region_name='us-east-1',
                          aws_access_key_id='test', aws_secret_access_key='test')
    with patch('app.storage.boto3.client', return_value=client):
        storage = S3Storage(config)
        assert storage.client is client
    with Stubber(client) as stubber:
        yield storage, stubber, tmp_path
        stubber.assert_no_pending_responses()


def test_filesystem_delegates_and_round_trips(tmp_path):
    storage = FileStorage()
    directory = tmp_path / 'nested'
    storage.makedirs(directory)
    source = directory / 'one.txt'
    with storage.open(source, 'w', encoding='utf-8') as handle:
        handle.write('hello')
    assert storage.exists(source)
    assert storage.listdir(directory) == ['one.txt']
    assert list(storage.walk(directory)) == [(str(directory), [], ['one.txt'])]
    target = directory / 'two.txt'
    storage.rename(source, target)
    with storage.open(target) as handle:
        assert handle.read() == 'hello'
    storage.remove(target)
    assert not storage.exists(target)
    with patch('builtins.open') as opened, patch('os.makedirs') as makedirs:
        storage.open('file', 'r')
        storage.makedirs('directory')
        opened.assert_called_once_with('file', 'r', encoding=None)
        makedirs.assert_called_once_with('directory', exist_ok=False)


def test_s3_rejects_mutations_after_ownership_loss(s3_storage):
    storage, _, root = s3_storage
    storage.check_owned = lambda: False
    with pytest.raises(OSError, match='lease is not owned'):
        with storage.open(root / 'incident.yml', 'w') as handle:
            handle.write('state')
    with pytest.raises(OSError, match='lease is not owned'):
        storage.remove(root / 'incident.yml')
    with pytest.raises(OSError, match='lease is not owned'):
        storage.rename(root / 'old.yml', root / 'new.yml')


def test_storage_configuration(monkeypatch):
    for name in ['STORAGE_BACKEND', 'S3_BUCKET', 'S3_PREFIX', 'S3_ENDPOINT_URL']:
        monkeypatch.delenv(name, raising=False)
    config = EnvironmentConfig()
    assert config.storage_backend == 'filesystem'
    assert config.s3_bucket is None
    assert config.s3_prefix == ''
    assert config.s3_endpoint_url is None
    assert isinstance(get_storage(config), FileStorage)
    monkeypatch.setenv('STORAGE_BACKEND', 's3')
    with pytest.raises(ValidationError, match='S3_BUCKET is required'):
        EnvironmentConfig()
    monkeypatch.setenv('S3_BUCKET', ' state-bucket ')
    monkeypatch.setenv('S3_PREFIX', 'instance')
    monkeypatch.setenv('S3_ENDPOINT_URL', 'https://storage.example.com')
    config = EnvironmentConfig()
    assert config.s3_bucket == 'state-bucket'
    assert config.s3_prefix == 'instance'
    assert config.s3_endpoint_url == 'https://storage.example.com'
    monkeypatch.setenv('STORAGE_BACKEND', 'unknown')
    with pytest.raises(ValidationError):
        EnvironmentConfig()
    with pytest.raises(ValidationError, match='S3_BUCKET is required'):
        EnvironmentConfig(storage_backend='s3', s3_bucket='  ')


def test_storage_selection_caches_by_config_and_uses_default_credentials():
    first = EnvironmentConfig(storage_backend='s3', s3_bucket='state-bucket',
                              s3_endpoint_url='https://s3.example.com')
    second = EnvironmentConfig(storage_backend='s3', s3_bucket='other-bucket')
    with patch('app.storage.boto3.client') as create:
        storage = get_storage(first)
        assert storage is get_storage(first)
        create.assert_not_called()
        assert storage.client is storage.client
        create.assert_called_once_with('s3', endpoint_url='https://s3.example.com', config=ANY)
        sdk_config = create.call_args.kwargs['config']
        assert sdk_config.connect_timeout == 5
        assert sdk_config.read_timeout == 5
        assert sdk_config.retries == {'mode': 'standard', 'total_max_attempts': 3}
        other = get_storage(second)
        assert other.bucket == 'other-bucket'
        assert create.call_count == 1
        other.client
        assert create.call_count == 2
    assert isinstance(get_storage(Mock()), FileStorage)
    with patch('app.storage.get_environment_config', return_value=EnvironmentConfig()):
        assert isinstance(get_storage(), FileStorage)


@pytest.mark.parametrize('mode,content', [('w', 'данные'), ('wb', b'\x00\xff'), ('wt', '')])
def test_s3_writes_entire_object_on_success(s3_storage, mode, content):
    storage, stubber, root = s3_storage
    expected = content.encode('utf-8') if isinstance(content, str) else content
    stubber.add_response('put_object', {}, {'Bucket': 'state-bucket',
                         'Key': 'deployment/users/test', 'Body': expected})
    with storage.open(root / 'users' / 'test', mode) as handle:
        handle.write(content)
    assert handle.closed


def test_s3_does_not_publish_failed_serialization(s3_storage):
    storage, _, root = s3_storage
    with pytest.raises(ValueError, match='serialization failed'):
        with storage.open(root / 'test', 'w') as handle:
            handle.write('partial')
            raise ValueError('serialization failed')
    assert handle.closed


@pytest.mark.parametrize('mode,content,expected', [('r', 'данные'.encode(), 'данные'),
                                                 ('rb', b'\x00\xff', b'\x00\xff'),
                                                 ('rt', b'', '')])
def test_s3_reads_and_closes_body(s3_storage, mode, content, expected):
    storage, stubber, root = s3_storage
    stream = io.BytesIO(content)
    body = StreamingBody(stream, len(content))
    stubber.add_response('get_object', {'Body': body}, {'Bucket': 'state-bucket',
                         'Key': 'deployment/incidents/test'})
    with storage.open(root / 'incidents' / 'test', mode) as handle:
        assert handle.read() == expected
        assert stream.closed
    assert handle.closed


@pytest.mark.parametrize('mode', ['a', 'r+', 'w+', 'x', 'invalid'])
def test_s3_rejects_unsupported_modes(s3_storage, mode):
    storage, _, root = s3_storage
    with pytest.raises(ValueError, match='read and write modes'):
        with storage.open(root / 'test', mode):
            pass


def test_s3_rejects_binary_encoding_and_paths_outside_namespace(s3_storage):
    storage, _, root = s3_storage
    with pytest.raises(ValueError, match='encoding'):
        with storage.open(root / 'test', 'rb', encoding='utf-8'):
            pass
    for path in [root.parent / 'outside', root / '..' / root.name / 'test']:
        with pytest.raises(ValueError, match='DATA_PATH'):
            storage.exists(path)
        with pytest.raises(ValueError, match='DATA_PATH'):
            storage.makedirs(path)
    with pytest.raises(IsADirectoryError):
        with storage.open(root, 'w'):
            pass
    storage.makedirs(root / 'incidents', exist_ok=True)


@pytest.mark.parametrize('code,exception', [('NoSuchKey', FileNotFoundError),
                                          ('NoSuchBucket', OSError),
                                          ('AccessDenied', OSError)])
def test_s3_read_error_types(s3_storage, code, exception):
    storage, stubber, root = s3_storage
    stubber.add_client_error('get_object', service_error_code=code, http_status_code=404)
    with pytest.raises(exception) as caught:
        with storage.open(root / 'test'):
            pass
    if code != 'NoSuchKey':
        assert not isinstance(caught.value, FileNotFoundError)
    assert caught.value.__cause__ is not None


def test_s3_empty_listing_and_directory_existence(s3_storage):
    storage, stubber, root = s3_storage
    stubber.add_response('list_objects_v2', {}, {'Bucket': 'state-bucket',
                         'Prefix': 'deployment/', 'Delimiter': '/'})
    assert storage.listdir(root) == []
    stubber.add_response('list_objects_v2', {}, {'Bucket': 'state-bucket', 'Prefix': 'deployment/'})
    assert list(storage.walk(root)) == []
    stubber.add_response('list_objects_v2', {}, {'Bucket': 'state-bucket',
                         'Prefix': 'deployment/', 'MaxKeys': 1})
    assert not storage.exists(root)
    stubber.add_response('list_objects_v2', {'Contents': [{'Key': 'deployment/incidents/one'}]},
                         {'Bucket': 'state-bucket', 'Prefix': 'deployment/incidents', 'MaxKeys': 1})
    assert storage.exists(root / 'incidents')
    stubber.add_response('list_objects_v2', {}, {'Bucket': 'state-bucket',
                         'Prefix': 'deployment/missing', 'MaxKeys': 1})
    assert not storage.exists(root / 'missing')
    stubber.add_response('list_objects_v2', {'Contents': [{'Key': 'deployment/file'}]},
                         {'Bucket': 'state-bucket', 'Prefix': 'deployment/file', 'MaxKeys': 1})
    assert storage.exists(root / 'file')


def test_s3_exists_propagates_auth_bucket_and_network_errors(s3_storage):
    storage, stubber, root = s3_storage
    stubber.add_client_error('list_objects_v2', service_error_code='AccessDenied', http_status_code=403,
                            expected_params={'Bucket': 'state-bucket', 'Prefix': 'deployment/test', 'MaxKeys': 1})
    with pytest.raises(OSError):
        storage.exists(root / 'test')
    stubber.add_client_error('list_objects_v2', service_error_code='NoSuchBucket', http_status_code=404)
    with pytest.raises(OSError):
        storage.exists(root / 'test')
    with patch.object(storage.client, 'list_objects_v2', side_effect=EndpointConnectionError(endpoint_url='https://s3.example')):
        with pytest.raises(OSError) as caught:
            storage.exists(root / 'test')
        assert isinstance(caught.value.__cause__, EndpointConnectionError)


def test_s3_listing_paginates_and_keeps_prefix_boundary(s3_storage):
    storage, stubber, root = s3_storage
    params = {'Bucket': 'state-bucket', 'Prefix': 'deployment/incidents/', 'Delimiter': '/'}
    stubber.add_response('list_objects_v2', {'Contents': [{'Key': 'deployment/incidents/one'}],
                         'CommonPrefixes': [{'Prefix': 'deployment/incidents/archive/'}],
                         'IsTruncated': True, 'NextContinuationToken': 'next'}, params)
    stubber.add_response('list_objects_v2', {'Contents': [{'Key': 'deployment/incidents/two'},
                         {'Key': 'deployment/incidents-extra/private'}, {'Key': 'deployment/incidents/../private'}]},
                         {**params, 'ContinuationToken': 'next'})
    assert storage.listdir(root / 'incidents') == ['archive', 'one', 'two']
    params.pop('Delimiter')
    stubber.add_response('list_objects_v2', {'Contents': [{'Key': 'deployment/incidents/one'},
                         {'Key': 'deployment/incidents/archive/old'}],
                         'IsTruncated': True, 'NextContinuationToken': 'next'}, params)
    stubber.add_response('list_objects_v2', {'Contents': [{'Key': 'deployment/incidents/two'},
                         {'Key': 'deployment/incidents/archive/empty/'}, {'Key': 'deployment/incidents-extra/private'}]},
                         {**params, 'ContinuationToken': 'next'})
    assert list(storage.walk(root / 'incidents')) == [
        (str(root / 'incidents'), ['archive'], ['one', 'two']),
        (str(root / 'incidents' / 'archive'), ['empty'], ['old']),
        (str(root / 'incidents' / 'archive' / 'empty'), [], [])]


def test_s3_listing_errors_are_not_empty_results(s3_storage):
    storage, stubber, root = s3_storage
    stubber.add_client_error('list_objects_v2', service_error_code='AccessDenied', http_status_code=403)
    with pytest.raises(OSError):
        storage.listdir(root)
    stubber.add_client_error('list_objects_v2', service_error_code='NoSuchBucket', http_status_code=404)
    with pytest.raises(OSError):
        list(storage.walk(root))


def test_s3_write_remove_and_rename_failures_preserve_cause(s3_storage):
    storage, stubber, root = s3_storage
    stubber.add_client_error('put_object', service_error_code='AccessDenied', http_status_code=403)
    with pytest.raises(OSError) as caught:
        with storage.open(root / 'new', 'w') as handle:
            handle.write('state')
    assert handle.closed
    assert caught.value.__cause__ is not None
    copy_params = {'Bucket': 'state-bucket', 'Key': 'deployment/new',
                   'CopySource': {'Bucket': 'state-bucket', 'Key': 'deployment/old'}}
    stubber.add_client_error('copy_object', service_error_code='AccessDenied', http_status_code=403,
                            expected_params=copy_params)
    with pytest.raises(OSError):
        storage.rename(root / 'old', root / 'new')
    stubber.add_response('copy_object', {}, copy_params)
    stubber.add_client_error('delete_object', service_error_code='AccessDenied', http_status_code=403,
                            expected_params={'Bucket': 'state-bucket', 'Key': 'deployment/old'})
    with pytest.raises(OSError):
        storage.rename(root / 'old', root / 'new')
    storage.rename(root / 'same', root / 'same')
    stubber.add_response('delete_object', {}, {'Bucket': 'state-bucket', 'Key': 'deployment/remove'})
    storage.remove(root / 'remove')


def test_s3_relative_data_path_and_empty_prefix(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = EnvironmentConfig(storage_backend='s3', s3_bucket='state-bucket', data_path='./state')
    client = boto3.client('s3', region_name='us-east-1',
                          aws_access_key_id='test', aws_secret_access_key='test')
    with patch('app.storage.boto3.client', return_value=client), Stubber(client) as stubber:
        storage = S3Storage(config)
        stubber.add_response('put_object', {}, {'Bucket': 'state-bucket', 'Key': 'users/one', 'Body': b'data'})
        with storage.open('state/users/one', 'wb') as handle:
            handle.write(b'data')
        stubber.add_response('list_objects_v2', {}, {'Bucket': 'state-bucket', 'Prefix': '', 'Delimiter': '/'})
        assert storage.listdir('./state') == []
        stubber.add_response('list_objects_v2', {}, {'Bucket': 'state-bucket', 'Prefix': '', 'MaxKeys': 1})
        assert not storage.exists('./state')
        stubber.assert_no_pending_responses()


def test_s3_incomplete_reads_close_body_and_report_error(s3_storage):
    storage, stubber, root = s3_storage
    stream = io.BytesIO(b'short')
    stubber.add_response('get_object', {'Body': StreamingBody(stream, 10)},
                         {'Bucket': 'state-bucket', 'Key': 'deployment/test'})
    with pytest.raises(OSError) as caught:
        with storage.open(root / 'test'):
            pass
    assert caught.value.__cause__ is not None
    assert stream.closed


@pytest.mark.parametrize('contents,expected', [([], False),
                                              ([{'Key': 'deployment/test'}], True),
                                              ([{'Key': 'deployment/test/file'}], True)])
def test_s3_exists_uses_scoped_listing(s3_storage, contents, expected):
    storage, stubber, root = s3_storage
    stubber.add_response('list_objects_v2', {'Contents': contents},
                         {'Bucket': 'state-bucket', 'Prefix': 'deployment/test', 'MaxKeys': 1})
    assert storage.exists(root / 'test') is expected


@pytest.mark.parametrize('directory_contents,expected', [([], False),
                                                        ([{'Key': 'deployment/test/file'}], True)])
def test_s3_exists_keeps_sibling_prefixes_separate(s3_storage, directory_contents, expected):
    storage, stubber, root = s3_storage
    stubber.add_response('list_objects_v2', {'Contents': [{'Key': 'deployment/test-other'}]},
                         {'Bucket': 'state-bucket', 'Prefix': 'deployment/test', 'MaxKeys': 1})
    stubber.add_response('list_objects_v2', {'Contents': directory_contents},
                         {'Bucket': 'state-bucket', 'Prefix': 'deployment/test/', 'MaxKeys': 1})
    assert storage.exists(root / 'test') is expected
