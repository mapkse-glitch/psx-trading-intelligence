from datetime import datetime
from io import BytesIO
import openpyxl
import pytest
from psx_app.parsers.detector import detect_file_type
from psx_app.parsers.ohlcv_parser import parse_ohlcv_file
from psx_app.database.schema import init_db,get_connection
from psx_app.services.import_orchestrator import ImportOrchestrator

HEADER=['DATE','SYMBOL','VOLUME','PR-CLOSE','HIGH','LOW','OPEN','CLOSE','AVG','1st initial']
def workbook(year,symbol='ATRL',price=101,header=None):
    w=openpyxl.Workbook();w.active.title=str(year);w.active.append(header or HEADER)
    w.active.append([datetime(year,1,4),symbol,100,100,102,99,100,price,100.5,'A'])
    b=BytesIO();w.save(b);return b.getvalue()

@pytest.mark.parametrize('year',[2016,2022,2026,2030])
def test_raw_price_schema_not_limited_to_2026(tmp_path,year):
    p=tmp_path/f'{year}.xlsx';p.write_bytes(workbook(year));assert detect_file_type(p)['file_type']=='OHLCV_CASH'


def test_unrelated_2026_named_workbook_is_not_a_price_file(tmp_path):
    p=tmp_path/'2026.xlsx';p.write_bytes(workbook(2026,header=['Name','Amount']))
    assert detect_file_type(p)['file_type']=='CUSTOM_XLSX'


def test_historical_futures_by_contract_not_filename(tmp_path):
    p=tmp_path/'history.xlsx';p.write_bytes(workbook(2019,'OGDC-SEPB'));assert detect_file_type(p)['file_type']=='OHLCV_FUTURES'


def test_historical_numeric_ticker_and_exact_date_preserved(tmp_path):
    p=tmp_path/'2022.xlsx';p.write_bytes(workbook(2022,786));record=parse_ohlcv_file(p)['records'][0]
    assert record['symbol']=='786';assert record['trade_date']=='2022-01-04';assert record['close']==101


def test_history_additive_and_repeat_upload_idempotent(tmp_path):
    db=tmp_path/'database/app.db';db.parent.mkdir();init_db(db);o=ImportOrchestrator(db,tmp_path)
    current=[('2026.xlsx',workbook(2026))];o.commit_staged_batch(o.stage_uploaded_files(current)['batch_uuid'])
    files=[(f'{y}.xlsx',workbook(y)) for y in [2016,2022]]
    stage=o.stage_uploaded_files(files);assert stage['new_records']==2;assert stage['rows_accepted']==2
    assert all(f['file_type']=='OHLCV_CASH' for f in stage['files'])
    o.commit_staged_batch(stage['batch_uuid']);repeat=o.stage_uploaded_files(files);assert repeat['new_records']==0;assert repeat['duplicates_ignored']==2
    o.commit_staged_batch(repeat['batch_uuid'])
    with get_connection(db) as c:
        assert c.execute('SELECT COUNT(*) FROM equity_ohlcv').fetchone()[0]==3
        assert c.execute('SELECT MAX(trade_date) FROM equity_ohlcv').fetchone()[0]=='2026-01-04'


def test_zero_accepted_rows_cannot_be_marked_committed(tmp_path):
    db=tmp_path/'database/app.db';db.parent.mkdir();init_db(db);o=ImportOrchestrator(db,tmp_path)
    stage=o.stage_uploaded_files([('notes.xlsx',workbook(2022,header=['Name','Amount']))]);assert stage['rows_accepted']==0
    with pytest.raises(ValueError,match='No importable rows'):o.commit_staged_batch(stage['batch_uuid'])
