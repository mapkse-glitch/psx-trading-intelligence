import json,hashlib
from fastapi import APIRouter,File,UploadFile,HTTPException,Query
from pydantic import BaseModel,Field
from psx_app.config import DB_PATH
from psx_app.database.schema import get_connection
from psx_app.services.market_explorer import MarketExplorer
from psx_app.services.sector_reference import SectorReference
from psx_app.services.forecast_ledger import ForecastLedger,execution_contract
from psx_app.services.technical_service import TechnicalService

router=APIRouter(prefix='/api/v139')
class ReferenceCommit(BaseModel): token:str=Field(min_length=64,max_length=64)
class ForecastRequest(BaseModel): symbol:str=Field(min_length=1,max_length=24)

@router.get('/market/meta')
def metadata():return MarketExplorer(DB_PATH).metadata()
@router.get('/market/volume')
def volume(date:str|None=None,n:int=Query(10,ge=1,le=10)):return MarketExplorer(DB_PATH).volume(date,n)
@router.get('/market/symbol/{symbol}')
def symbol(symbol:str,n:int=Query(50,ge=1,le=6000),end:str|None=None):return MarketExplorer(DB_PATH).symbol(symbol,n,end)
@router.get('/contract/{symbol}')
def contract(symbol:str):
    r=TechnicalService(DB_PATH).get_ticker_analysis(symbol,tail_bars=120)
    if not r.get('latest'):raise HTTPException(404,'No price data for selected symbol.')
    return {'contract':execution_contract(r['latest']),'latest':r['latest'],'series':r['series']}
@router.post('/reference/preview')
async def preview(file:UploadFile=File(...)):
    try:return SectorReference(DB_PATH).preview(await file.read(2_000_001))
    except Exception as e:raise HTTPException(400,str(e) if isinstance(e,ValueError) else 'Workbook could not be read; use a valid XLSX reference workbook.')
@router.post('/reference/commit')
def commit(req:ReferenceCommit):
    try:
        res=SectorReference(DB_PATH).commit(req.token)
        from psx_app.main import invalidate_api_cache
        invalidate_api_cache();return res
    except ValueError as e:raise HTTPException(400,str(e))
@router.post('/forecasts/record')
def record(req:ForecastRequest):
    try:return ForecastLedger(DB_PATH).record(req.symbol)
    except ValueError as e:raise HTTPException(400,str(e))
@router.post('/forecasts/evaluate')
def evaluate():return ForecastLedger(DB_PATH).reconcile()
@router.get('/forecasts')
def forecasts():return ForecastLedger(DB_PATH).list()
@router.get('/learning/{symbol}')
def learning(symbol:str):
    with get_connection(DB_PATH) as c:
        row=c.execute('SELECT result_json FROM learning_runs WHERE symbol=? ORDER BY created_at DESC LIMIT 1',(symbol.upper(),)).fetchone()
        current=[dict(r) for r in c.execute('SELECT trade_date,close,volume FROM equity_ohlcv WHERE symbol=? ORDER BY trade_date',(symbol.upper(),))] if row else []
    result=json.loads(row[0]) if row else {'status':'NOT_TRAINED','note':'Run python -m tools.refresh_learning outside the web request, or the optional GitHub Actions research workflow.'}
    from psx_app.services.learning_research import VERSION
    result['stale']=bool(row and result.get('run_id')!=hashlib.sha256((VERSION+json.dumps(current,sort_keys=True)).encode()).hexdigest())
    return result

@router.get('/coverage')
def coverage(search: str = Query('', max_length=150)):
    from psx_app.services.data_coverage import DataCoverage
    return DataCoverage(DB_PATH).report(search)
