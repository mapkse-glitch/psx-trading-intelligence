import pytest
from psx_app.database import postgres,turso
from psx_app.database.availability import safe_failure,DatabaseUnavailable


def test_pg_config_requires_uri_and_certificate(monkeypatch):
    monkeypatch.delenv('DATABASE_URL',raising=False)
    with pytest.raises(RuntimeError,match='DATABASE_URL'):postgres.settings()
    monkeypatch.setenv('DATABASE_URL','postgresql://owner:private-password@db.example.com:5432/defaultdb?sslmode=disable')
    monkeypatch.delenv('DATABASE_CA_CERT',raising=False)
    with pytest.raises(RuntimeError,match='DATABASE_CA_CERT'):postgres.settings()
    # The test bypass cannot disable TLS on a real remote host.
    monkeypatch.setenv('PSX_PG_LOOPBACK_TEST','1')
    with pytest.raises(RuntimeError,match='DATABASE_CA_CERT'):postgres.settings()
    monkeypatch.setenv('DATABASE_CA_CERT','-----BEGIN CERTIFICATE-----\\npublic-test-cert\\n-----END CERTIFICATE-----')
    cfg=postgres.settings()
    assert cfg['sslmode']=='verify-full' and '\\n' not in open(cfg['sslrootcert']).read()


def test_pg_serverless_default_never_falls_back(monkeypatch):
    monkeypatch.setenv('VERCEL','1');monkeypatch.delenv('PSX_DATABASE_BACKEND',raising=False)
    assert turso.backend_name()=='postgres'
    monkeypatch.setenv('PSX_DATABASE_BACKEND','sqlite')
    with pytest.raises(RuntimeError,match='fallback'):turso.enabled()


def test_sql_translation_preserves_parameters_and_literals():
    assert postgres._bind("SELECT '?' AS q, ? AS v, '25%' AS p")=="SELECT '?' AS q, %s AS v, '25%%' AS p"
    assert postgres.translate('INSERT OR IGNORE INTO t(a) VALUES (?)').endswith('ON CONFLICT DO NOTHING')
    sql=postgres.translate('INSERT OR REPLACE INTO company_reference(list_name,symbol,company,sector) VALUES (?,?,?,?)')
    assert 'ON CONFLICT (list_name,symbol) DO UPDATE' in sql
    assert 'company=excluded.company' in sql
    with pytest.raises(ValueError):postgres.translate('INSERT OR REPLACE INTO unreviewed(a) VALUES (?)')
    ddl=';'.join(postgres.schema_sql())
    assert 'AUTOINCREMENT' not in ddl and 'DOUBLE PRECISION' in ddl and 'volume BIGINT' in ddl


@pytest.mark.parametrize('message,code',[
    ('password authentication failed for user secret-user','AUTHENTICATION_REJECTED'),
    ('DATABASE_URL must be a valid PostgreSQL connection URI: private','SERVER_CONFIGURATION'),
    ('DATABASE_CA_CERT must contain complete PEM: private','SERVER_CONFIGURATION'),
    ('too many clients already','CONNECTION_CAPACITY'),
    ('no space left on device','STORAGE_CAPACITY')])
def test_pg_failure_codes_are_credential_safe(message,code,caplog):
    result=safe_failure(RuntimeError(message),'test')
    assert result.code==code
    assert 'private' not in str(result)+caplog.text and 'secret-user' not in str(result)+caplog.text


def test_unknown_write_outcome_is_never_retried():
    class Raw:
        calls=0
        def execute(self,*a):
            self.calls+=1
            if self.calls<=2:return None # BEGIN and advisory lock succeed
            raise RuntimeError('connection timed out; private-password')
    raw=Raw();c=postgres.Connection(raw)
    with pytest.raises(DatabaseUnavailable) as error:c.execute("INSERT INTO audit_events(event_type,created_at) VALUES (?,?)",('test','2025'))
    assert error.value.uncertain and raw.calls==3 and 'private-password' not in str(error.value)
