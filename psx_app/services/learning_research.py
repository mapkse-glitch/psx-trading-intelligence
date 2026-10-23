"""Versioned, chronological logistic baseline. Research only; never auto-promoted."""
import json,math,hashlib
from datetime import datetime,timezone
from psx_app.database.schema import get_connection

VERSION='chronological-logit-1'
def sigmoid(z):return 1/(1+math.exp(-max(-30,min(30,z))))

def research_model(rows):
    samples=[]
    closes=[r['close'] for r in rows]
    for i in range(20,len(rows)-1):
        cl=closes[max(0,i-20):i+1]
        if not all(v and v>0 for v in cl[-21:]) or not rows[i+1]['close'] or rows[i+1]['close']<=0:continue
        x=[1.,cl[-1]/cl[-2]-1,cl[-1]/cl[-6]-1,cl[-1]/(sum(cl[-20:])/20)-1,math.log1p(max(0,rows[i].get('volume') or 0))/20]
        samples.append((x,int(rows[i+1]['close']>cl[-1]),rows[i]['trade_date'],rows[i+1]['trade_date']))
    if len(samples)<300:return {'status':'INSUFFICIENT_DATA','samples':len(samples),'required':300,'version':VERSION}
    if any(r.get('close') is None or r['close']<=0 for r in rows[-21:]):
        return {'status':'INVALID_LATEST_DATA','version':VERSION,'note':'Latest feature window has non-positive or missing close; no research output created.'}
    a=int(len(samples)*.6);b=int(len(samples)*.8)
    train=samples[:a];val=samples[a+1:b];test=samples[b+1:]
    means=[sum(s[0][j] for s in train)/len(train) for j in range(5)]
    scales=[max(1e-6,(sum((s[0][j]-means[j])**2 for s in train)/len(train))**.5) for j in range(5)];means[0]=0;scales[0]=1
    def norm(x):return [(x[j]-means[j])/scales[j] for j in range(5)]
    def fit(l2):
        weights=[0.]*5
        for epoch in range(120):
            grad=[0.]*5
            for x,y,_,_ in train:
                z=norm(x);error=sigmoid(sum(w*v for w,v in zip(weights,z)))-y
                for j in range(5):grad[j]+=error*z[j]
            for j in range(5):weights[j]-=.08*(grad[j]/len(train)+(l2*weights[j] if j else 0))
        return weights
    def metrics(data,w):
        probs=[sigmoid(sum(a*b for a,b in zip(w,norm(s[0])))) for s in data]
        return {'n':len(data),'accuracy':sum((p>=.5)==s[1] for p,s in zip(probs,data))/len(data),'brier':sum((p-s[1])**2 for p,s in zip(probs,data))/len(data)}
    options=[(fit(v),v) for v in (.001,.01,.1)]
    w,l2=min(options,key=lambda pair:metrics(val,pair[0])['brier'])
    test_metrics=metrics(test,w);p0=sum(s[1] for s in train)/len(train)
    baseline={'accuracy':sum((p0>=.5)==s[1] for s in test)/len(test),'brier':sum((p0-s[1])**2 for s in test)/len(test)}
    cl=[r['close'] for r in rows]
    x=[1.,cl[-1]/cl[-2]-1,cl[-1]/cl[-6]-1,cl[-1]/(sum(cl[-20:])/20)-1,math.log1p(max(0,rows[-1].get('volume') or 0))/20]
    estimate=sigmoid(sum(a*b for a,b in zip(w,norm(x))))
    return {'status':'RESEARCH_ONLY','version':VERSION,'samples':len(samples),'training_end':train[-1][3],'validation_end':val[-1][3],'test_start':test[0][2],'test_end':test[-1][3],'test':test_metrics,'baseline':baseline,'beats_baseline_brier':test_metrics['brier']<baseline['brier'],'raw_model_output':estimate,'weights':w,'means':means,'scales':scales,'selected_l2':l2,'note':'Uncalibrated research output, not a validated win probability or production trading signal. 60/20/20 chronological split, one-sample boundary purge; training-only scaling, validation-selected regularization, untouched final test. Single holdout, not full walk-forward. No automatic rule replacement; corporate actions and survivorship unverified.'}


def train_symbol(symbol,db_path=None):
    symbol=symbol.upper()
    with get_connection(db_path) as c:
        rows=[dict(r) for r in c.execute('SELECT trade_date,close,volume FROM equity_ohlcv WHERE symbol=? ORDER BY trade_date',(symbol,))]
    if not rows:raise ValueError('No historical prices for '+symbol)
    digest=hashlib.sha256((VERSION+json.dumps(rows,sort_keys=True)).encode()).hexdigest()
    with get_connection(db_path) as c:
        old=c.execute('SELECT result_json FROM learning_runs WHERE run_id=?',(digest,)).fetchone()
        if old:return json.loads(old[0])
    result=research_model(rows);result.update(symbol=symbol,as_of=rows[-1]['trade_date'],run_id=digest)
    with get_connection(db_path) as c:
        c.execute('INSERT OR IGNORE INTO learning_runs(run_id,symbol,as_of,result_json,created_at) VALUES (?,?,?,?,?)',(digest,symbol,rows[-1]['trade_date'],json.dumps(result),datetime.now(timezone.utc).isoformat()));c.commit()
    return result
