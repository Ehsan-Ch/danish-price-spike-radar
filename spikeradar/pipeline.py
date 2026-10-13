"""Chronological evaluation and chronological paper settlement."""
from collections import Counter, defaultdict
from datetime import timedelta
import csv
import json
from pathlib import Path
import numpy as np
from .data import load, stamp, AREAS
from .model import Logistic, samples, metrics
from .ledger import Ledger

TRAIN_END = stamp("2026-05-01")
VALID_START, VALID_END = stamp("2026-05-04"), stamp("2026-06-29")
LOCK_TIME = stamp("2026-06-30")
TEST_START, TEST_END = stamp("2026-07-02"), stamp("2026-09-30")
TRIGGER = 0.20

def rolling_probability(series, target, threshold):
    return (1+sum(series[target-timedelta(hours=h)]>threshold for h in range(72,240)))/170

def fit_area(series):
    rows = samples(series)
    train = [r for r in rows if r[0]<TRAIN_END]
    valid = [r for r in rows if VALID_START<=r[0]<VALID_END]
    test = [r for r in rows if TEST_START<=r[0]<TEST_END]
    if min(len(train),len(valid),len(test))<100:
        raise ValueError("Insufficient observations for fixed train/validation/test windows")
    threshold = float(np.quantile([r[1] for r in train],0.9))
    xtrain = np.array([r[2] for r in train])
    ytrain = np.array([r[1]>threshold for r in train],int)
    model = Logistic().fit(xtrain,ytrain)
    rate = float(ytrain.mean())
    xv = np.array([r[2] for r in valid])
    yv = np.array([r[1]>threshold for r in valid],int)
    pv = model.predict(xv)
    val_model,val_base = metrics(yv,pv),metrics(yv,np.full(len(yv),rate))
    rv = np.array([rolling_probability(series,r[0],threshold) for r in valid])
    validation = {"logistic":val_model,"climatology":val_base,"rolling_week":metrics(yv,rv)}
    selected = min(validation,key=lambda name: validation[name]["brier"])
    xt = np.array([r[2] for r in test])
    yt = np.array([r[1]>threshold for r in test],int)
    pt = model.predict(xt)
    rt = np.array([rolling_probability(series,r[0],threshold) for r in test])
    candidates = {"logistic":pt,"climatology":np.full(len(yt),rate),"rolling_week":rt}
    chosen = candidates[selected]
    summary = {"strike_eur_mwh":threshold,"train_spike_rate":rate,"train_n":len(train),
        "validation_n":len(valid),"selected":selected,
        "validation":validation,
        "test":{"logistic":metrics(yt,pt),"climatology":metrics(yt,np.full(len(yt),rate)),"rolling_week":metrics(yt,rt),
                "selected":metrics(yt,chosen)},"model":model.export()}
    forecasts = [{"delivery":t.isoformat(),"issue":(t-timedelta(hours=48)).isoformat(),
        "latest_feature":(t-timedelta(hours=72)).isoformat(),"price":price,
        "strike":threshold,"spike":int(price>threshold),"logistic_probability":float(p),
        "rolling_probability":float(rp),"probability":float(q),"selected_model":selected}
        for (t,price,_),p,rp,q in zip(test,pt,rt,chosen)]
    return forecasts,summary

def tail_summary(values):
    values = np.asarray(values,float)
    if not len(values):
        return {"days":0,"mean":None,"p95":None,"worst_5pct_mean":None,"tail_days":0}
    count=max(1,int(np.ceil(len(values)*0.05)))
    return {"days":len(values),"mean":float(values.mean()),"p95":float(np.quantile(values,0.95)),
        "worst_5pct_mean":float(np.sort(values)[-count:].mean()),"tail_days":count}

def simulate(forecasts, premium=8.0, volume=0.5, trigger=TRIGGER, path=":memory:"):
    ledger = Ledger(path)
    try:
        if ledger.orders():
            raise ValueError("Use a fresh ledger database to avoid mixing backtests")
        actions=[]
        for row in forecasts:
            t,issue=stamp(row["delivery"]),stamp(row["issue"])
            if issue<LOCK_TIME or t-issue!=timedelta(hours=48):
                raise ValueError("Decision before model lock or incorrect horizon")
            if row["probability"]>=trigger:
                oid=row["area"]+"-"+row["delivery"]
                actions.extend([(issue,1,oid,row),(t+timedelta(hours=1),0,oid,row)])
        active=set()
        for when,kind,oid,row in sorted(actions,key=lambda a:(a[0],a[1],a[2])):
            if kind==1:
                status=ledger.submit(oid,row["area"],row["issue"],row["delivery"],volume,
                    row["strike"],premium,row["probability"])
                if status=="OPEN":
                    active.add(oid)
            elif oid in active:
                ledger.settle(oid,when.isoformat(),row["price"])
                active.remove(oid)
        orders,events=ledger.orders(),ledger.events()
    finally:
        ledger.close()
    settled={o["id"]:o for o in orders if o["status"]=="SETTLED"}
    hourly=[]
    for r in forecasts:
        o=settled.get(r["area"]+"-"+r["delivery"])
        payment=o["volume"]*o["premium"] if o else 0
        payout=o["payout"] if o else 0
        hourly.append({**r,"hedge_mwh":o["volume"] if o else 0,
            "premium_paid":payment,"payout":payout,
            "unhedged_cost":r["price"],"hedged_cost":r["price"]+payment-payout})
    grouped=defaultdict(list)
    for r in hourly:
        grouped[r["delivery"][:10]].append(r)
    daily=[]
    for day,rows in sorted(grouped.items()):
        # Portfolio assumes 1 MWh/hour in each area, with both complete UTC days.
        if Counter(r["area"] for r in rows)!=Counter({"DK1":24,"DK2":24}):
            continue
        daily.append({"date":day,"unhedged_cost":sum(r["unhedged_cost"] for r in rows),
                      "hedged_cost":sum(r["hedged_cost"] for r in rows),
                      "premium_paid":sum(r["premium_paid"] for r in rows),
                      "payout":sum(r["payout"] for r in rows)})
    summary={"premium_eur_mwh":premium,"requested_hedge_mwh":volume,"trigger":trigger,
        "premium_paid":sum(r["premium_paid"] for r in hourly),
        "payout":sum(r["payout"] for r in hourly),
        "net_cost_change":sum(r["premium_paid"]-r["payout"] for r in hourly),
        "status_counts":dict(Counter(o["status"] for o in orders)),
        "rejection_reasons":dict(Counter(o["reason"] for o in orders if o["status"]=="REJECTED")),
        "unhedged_daily":tail_summary([r["unhedged_cost"] for r in daily]),
        "hedged_daily":tail_summary([r["hedged_cost"] for r in daily])}
    return {"summary":summary,"orders":orders,"events":events,"hourly":hourly,"daily":daily}

def write_csv(path,rows):
    if not rows:
        path.write_text("",encoding="utf-8")
        return
    with path.open("w",newline="",encoding="utf-8") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def run(data_folder,output_folder):
    from .report import render
    series,quality,manifest=load(data_folder)
    forecasts,areas=[],{}
    for area in AREAS:
        rows,areas[area]=fit_area(series[area])
        forecasts.extend({"area":area,**r} for r in rows)
    forecasts.sort(key=lambda r:(r["delivery"],r["area"]))
    output=Path(output_folder)
    output.mkdir(parents=True,exist_ok=True)
    db=output/"paper-ledger.sqlite"
    if db.exists():
        raise ValueError("Output already has a ledger; choose a fresh output folder")
    scenarios=[simulate(forecasts,p,v) for p in (3.0,8.0,15.0) for v in (0.25,0.5)]
    default=simulate(forecasts,path=str(db))
    meta={"title":"Danish Price Spike Radar","quality":quality,"source":manifest,
        "windows":{"train_end_exclusive":TRAIN_END.isoformat(),
        "validation_start":VALID_START.isoformat(),"validation_end_exclusive":VALID_END.isoformat(),
        "model_locked":LOCK_TIME.isoformat(),"test_start":TEST_START.isoformat(),
        "test_end_exclusive":TEST_END.isoformat()},
        "assumptions":{"horizon_hours":48,"latest_feature_lag_hours":72,"load_mwh_hour_per_area":1,
        "daily_premium_budget_eur":60,"maximum_open_mwh":8,"maximum_order_mwh":0.5,
        "premium_eur_mwh":8,"trigger":TRIGGER,"spike_definition":"Above training 90th percentile"},
        "areas":areas,"default_hedge":default["summary"],
        "scenarios":[s["summary"] for s in scenarios]}
    for name,rows in [("forecasts",forecasts),("orders",default["orders"]),
                      ("events",default["events"]),("daily_costs",default["daily"])]:
        write_csv(output/(name+".csv"),rows)
    (output/"metrics.json").write_text(json.dumps(meta,indent=2,allow_nan=False),encoding="utf-8")
    render(output/"report.html",meta,forecasts,default,scenarios)
    return meta

