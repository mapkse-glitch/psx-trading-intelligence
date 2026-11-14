"""Alphabetical directory from the imported company list and cash history."""
import re
from psx_app.database.schema import get_connection
from psx_app.services.market_analytics1335 import refs


def company_records(db_path, letter='A', sort='company', direction='asc', page=1, limit=50):
    if not re.fullmatch(r'[A-Z]',letter or ''): raise ValueError('Choose a letter A–Z')
    columns={'symbol':'symbol','company':'company','first':'first_date','last':'last_date'}
    if sort not in columns or direction not in ('asc','desc') or page<1 or limit<1 or limit>100: raise ValueError('Invalid table settings')
    with get_connection(db_path) as c:
        source=refs(c)
        if not source:return {'source':None,'rows':[],'total':0,'page':1,'pages':1}
        where='list_name=? AND UPPER(TRIM(company)) LIKE ?'
        args=(source,letter+'%')
        total=c.execute('SELECT COUNT(*) FROM company_reference WHERE '+where,args).fetchone()[0]
        pages=max(1,(total+limit-1)//limit);page=min(page,pages)
        sql='''SELECT symbol,company,
          (SELECT MIN(e.trade_date) FROM equity_ohlcv e WHERE e.symbol=cr.symbol) AS first_date,
          (SELECT MAX(e.trade_date) FROM equity_ohlcv e WHERE e.symbol=cr.symbol) AS last_date
          FROM company_reference cr WHERE '''+where+' ORDER BY '+columns[sort]+' '+direction.upper()+', symbol ASC LIMIT ? OFFSET ?'
        rows=[dict(row) for row in c.execute(sql,(*args,limit,(page-1)*limit))]
    return {'source':source,'rows':rows,'total':total,'page':page,'pages':pages}
