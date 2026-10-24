import threading
import pytest
from fastapi.testclient import TestClient
from psx_app.database import availability, turso


@pytest.mark.parametrize('text,code', [
    ('Hrana unauthorized JWT expired secret-token', 'AUTHENTICATION_REJECTED'),
    ('403 forbidden', 'PERMISSION_DENIED'),
    ('TLS certificate verify failed', 'TLS_CONNECTION_FAILED'),
    ('tcp connect error connection refused', 'NETWORK_CONNECTION_FAILED'),
    ('request timed out', 'CONNECTION_TIMEOUT'),
    ('429 too many requests', 'SERVICE_RATE_LIMITED'),
    ('Imported PSX schema is missing.', 'REQUIRED_SCHEMA_MISSING'),
    ('TURSO_AUTH_TOKEN is required', 'SERVER_CONFIGURATION'),
    ('unknown https://private-host.turso.io bearer secret-token', 'DRIVER_OPERATION_FAILED'),
])
def test_diagnostics_do_not_leak_driver_text(text,code,caplog):
    failure=availability.safe_failure(ValueError(text),'query',uncertain=True)
    assert failure.code==code
    assert failure.payload()['write_outcome_uncertain'] is True
    assert 'secret-token' not in str(failure)+caplog.text
    assert 'private-host' not in str(failure)+caplog.text
    assert 'check its saved status' in str(failure)


def test_first_query_failures_use_safe_code():
    class Raw:
        def execute(self,*args): raise ValueError('unauthorized bearer secret-token')
    with pytest.raises(availability.DatabaseUnavailable) as error:
        turso.Connection(Raw()).execute("SELECT name FROM sqlite_master WHERE type='table'")
    assert error.value.code=='AUTHENTICATION_REJECTED'
    assert not error.value.uncertain
    assert 'secret-token' not in str(error.value)


def test_failed_write_is_not_retried_or_reported_as_rollback():
    class Raw:
        calls=0
        def execute(self,*args):
            self.calls+=1
            raise ValueError('connection timed out')
    raw=Raw()
    with pytest.raises(availability.DatabaseUnavailable) as error:
        turso.Connection(raw).execute("INSERT INTO audit_events VALUES (?)",('sensitive',))
    assert error.value.uncertain and raw.calls==1


def test_cooldown_and_recovery(monkeypatch):
    now=[100.0]; gate=availability.Readiness(clock=lambda:now[0]); calls=[]
    monkeypatch.setattr(turso,'enabled',lambda:True)
    def unavailable(): calls.append(1);raise ValueError('401 unauthorized')
    monkeypatch.setattr(turso,'ensure_ready',unavailable)
    for _ in range(3):
        with pytest.raises(availability.DatabaseUnavailable):gate.check()
    assert len(calls)==1
    now[0]+=11
    monkeypatch.setattr(turso,'ensure_ready',lambda:calls.append(1))
    gate.check();assert gate.failure is None and len(calls)==2


def test_lifespan_and_static_survive_failed_first_remote_read(monkeypatch):
    from psx_app import main
    gate=availability.Readiness();calls=[];thread_names=[]
    monkeypatch.setattr(main,'readiness',gate)
    monkeypatch.setattr(turso,'enabled',lambda:True)
    def failed():
        calls.append(1);thread_names.append(threading.current_thread().name)
        raise ValueError('unauthorized https://private-host.turso.io secret-token')
    monkeypatch.setattr(turso,'ensure_ready',failed)
    monkeypatch.setattr(main,'init_db',lambda *a:pytest.fail('remote DB must not run in lifespan'))
    with TestClient(main.app) as client:
        assert calls==[]
        page=client.get('/');assert page.status_code==200 and '1.3.14' in page.text
        assert client.get('/static/app.js').status_code in (200,404) # actual asset path is root /app.js
        assert client.get('/app.js').status_code==200
        health=client.get('/api/health');assert health.status_code==503
        assert health.json()['code']=='AUTHENTICATION_REJECTED'
        assert health.json()['db_integrity']['ok'] is False
        for path in ('/api/v139/market/meta', '/api/data-dates', '/api/overview?brief=true', '/api/system/status'):
            assert client.get(path).status_code==503
        assert client.post('/api/settings',json={'updates':{}}).status_code==503
        assert len(calls)==1  # concurrent boot requests cannot hammer failed startup
        assert 'secret-token' not in health.text
        assert all('AnyIO worker thread' in n for n in thread_names)
        gate.retry_at=0;monkeypatch.setattr(turso,'ensure_ready',lambda:None)
        monkeypatch.setattr(main.BackupService,'run_integrity_check',lambda s:{'ok':True})
        recovered=client.get('/api/health');assert recovered.status_code==200
        assert recovered.json()['db_integrity']['ok'] is True


def test_bad_backend_configuration_does_not_kill_shell(monkeypatch):
    from psx_app import main
    monkeypatch.setenv('PSX_DATABASE_BACKEND','invalid-test-backend')
    monkeypatch.setattr(main,'readiness',availability.Readiness())
    with TestClient(main.app) as client:
        assert client.get('/').status_code==200
        r=client.get('/api/health');assert r.status_code==503
        assert r.json()['code']=='SERVER_CONFIGURATION'


@pytest.mark.parametrize('status,body,expected',[
    (401,{},'AUTHENTICATION_REJECTED'),
    (403,{},'PERMISSION_DENIED'),
    (503,{},'REMOTE_SERVICE_HTTP_ERROR'),
    (302,{},'REMOTE_SERVICE_HTTP_ERROR'),
    (200,{'results':[{'type':'error','error':{'message':'private'}}]},'REMOTE_QUERY_REJECTED'),
    (200,{'results':[{'type':'ok','response':{'type':'execute','result':{}}}]},'HTTPS_READ_OK_NATIVE_DRIVER_OR_SCHEMA_CHECK_FAILED'),
])
def test_https_diagnostic_only_sends_read_and_never_exposes_secrets(monkeypatch,status,body,expected):
    import httpx
    calls=[]
    monkeypatch.setattr(turso,'credentials',lambda:('libsql://example.turso.io','synthetic-private-token'))
    class Client:
        def __init__(self,**kwargs):assert kwargs['follow_redirects'] is False
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,url,**kwargs):
            calls.append((url,kwargs));return httpx.Response(status,json=body)
    monkeypatch.setattr(httpx,'Client',Client)
    result=availability.http_read_diagnostic()
    assert result['code']==expected
    assert calls[0][0]=='https://example.turso.io/v2/pipeline'
    assert calls[0][1]['json']['requests'][0]['stmt']['sql']=='SELECT 1'
    assert 'synthetic-private-token' not in str(result) and 'private' not in str(result)


def test_outage_after_ready_is_caught_before_freshness(monkeypatch):
    from psx_app import main
    monkeypatch.setattr(turso,'enabled',lambda:True)
    monkeypatch.setattr(turso,'ensure_ready',lambda:None)
    monkeypatch.setattr(main,'readiness',availability.Readiness())
    def unavailable(*args,**kwargs):
        raise availability.DatabaseUnavailable('NETWORK_CONNECTION_FAILED','query')
    monkeypatch.setattr(main,'check_cloud_freshness',unavailable)
    main._READ_FRESHNESS.clear()
    with TestClient(main.app) as client:
        r=client.get('/api/data-dates')
        assert r.status_code==503 and r.json()['code']=='NETWORK_CONNECTION_FAILED'
