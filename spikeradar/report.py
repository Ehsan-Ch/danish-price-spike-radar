"""Self-contained, offline report with area, week, scenario and ledger replay controls."""
import json

def render(path, meta, forecasts, default, scenarios):
    payload={"meta":meta,"forecasts":forecasts,
        "orders":default["orders"],"events":default["events"],
        "scenarios":[{"summary":s["summary"],"daily":s["daily"]} for s in scenarios]}
    data=json.dumps(payload,separators=(",",":"),allow_nan=False).replace("<","\\u003c")
    path.write_text(TEMPLATE.replace("__DATA__",data),encoding="utf-8")

TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Danish Price Spike Radar</title><style>
:root{--ink:#172c39;--muted:#526675;--bg:#f4f5f0;--line:#d8dfda;--orange:#b74b2b;--teal:#007b75}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,sans-serif}
.wrap{max-width:1240px;margin:auto;padding:30px 34px}header{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line);padding-bottom:18px}
.brand{font-weight:800;letter-spacing:.06em}.brand span{color:var(--teal)}.badge{border:1px solid #b8c9be;border-radius:30px;padding:5px 12px;font-size:12px}
.hero{display:grid;grid-template-columns:1.45fr 1fr;gap:50px;padding:42px 0 28px}.eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:.15em;color:var(--teal);font-weight:750}
h1{font-size:clamp(32px,4.4vw,56px);line-height:1.07;letter-spacing:-.04em;margin:14px 0 18px;max-width:720px}h2{font-size:23px;letter-spacing:-.02em;margin:0 0 8px}h3{font-size:15px;margin:0}
p{margin:8px 0;color:var(--muted)}.hero p{max-width:660px;font-size:16px}.note{background:#e6eeea;border:1px solid #cadbd0;border-radius:12px;padding:22px;align-self:center}
.note strong{display:block;margin-bottom:7px}.note p{font-size:14px}.controls{display:flex;gap:16px;flex-wrap:wrap;align-items:end;margin-bottom:22px}
label{display:flex;flex-direction:column;gap:5px;font-size:12px;color:var(--muted);font-weight:650}select{padding:9px 35px 9px 11px;border:1px solid #bbc9c2;border-radius:7px;background:white;color:var(--ink);font:inherit;min-width:130px}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:18px 0 24px}.card{background:white;border:1px solid var(--line);border-radius:12px;padding:18px}.card .value{font-size:28px;letter-spacing:-.04em;margin:5px 0}.small{font-size:12px;color:var(--muted)}
.panel{background:white;border:1px solid var(--line);border-radius:14px;padding:24px;margin-bottom:20px}.panelhead{display:flex;justify-content:space-between;gap:20px;align-items:start;margin-bottom:15px}
.grid{display:grid;grid-template-columns:1.45fr 1fr;gap:20px}.grid .panel{min-width:0}.legend{font-size:12px;display:flex;gap:15px}.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px}
svg{width:100%;height:auto;display:block;overflow:visible}svg text{font:11px system-ui;fill:var(--muted)}.notice{background:#fff4e5;color:#734626;padding:12px 16px;border-left:3px solid #d69b55;margin:14px 0;font-size:13px}
table{width:100%;border-collapse:collapse;font-size:12px}th{text-align:left;font-weight:650;color:var(--muted);white-space:nowrap}td,th{padding:10px 12px;border-bottom:1px solid #e8ece8}td{font-variant-numeric:tabular-nums}tr:last-child td{border:0}
.scroll{overflow:auto;max-height:440px}.state{display:inline-block;padding:3px 7px;border-radius:5px;font-size:10px;letter-spacing:.04em;background:#e2f0e8;color:#196345}.state.REJECTED{background:#fae8e0;color:#9c4326}.state.OPEN{background:#e2effa;color:#23608c}
.replay{display:grid;grid-template-columns:1fr 260px;gap:25px;margin:20px 0}input[type=range]{width:100%;accent-color:var(--teal)}button{border:1px solid #bbc9c2;background:white;color:var(--ink);padding:7px 13px;border-radius:6px;cursor:pointer}
button:hover{background:#e6eeea}details{margin-top:20px}summary{cursor:pointer;font-weight:700}details li{margin:8px 0;color:var(--muted)}a{color:var(--teal)}footer{display:flex;justify-content:space-between;gap:15px;margin:28px 0;color:var(--muted);font-size:12px}
@media(max-width:850px){.wrap{padding:20px}.hero,.grid{grid-template-columns:1fr;gap:12px}.cards{grid-template-columns:repeat(2,1fr)}.hero{padding:28px 0}.replay{grid-template-columns:1fr}.panel{padding:17px}.panelhead,header,footer{flex-wrap:wrap}.hero h1{font-size:42px}}
</style></head><body><div class="wrap">
<header><div class="brand">NORD / <span>SPIKE RADAR</span></div><span class="badge">Historical research · DK1 + DK2 · Paper only</span></header>
<section class="hero"><div><div class="eyebrow">Energy risk research / 03</div><h1>See the price risk.<br>Account for the hedge.</h1><p>A 48-hour risk signal for unusually expensive Danish electricity, connected to an auditable paper hedge book.</p><p class="small">Held-out evaluation: 2 July–29 September 2026 · All times UTC</p></div>
<div class="note"><strong>Real prices. Hypothetical protection.</strong><p>Hourly caps and their premiums are assumptions, not traded quotes. A profitable paper result does not establish that this hedge could have been bought.</p><p>“Spike” means exceeding a fixed training-period threshold. A change in price levels can make these events frequent.</p></div></section>
<div class="controls"><label>Price area<select id="area"><option>DK1</option><option>DK2</option></select></label><label>Chart week<select id="week"></select></label><span class="small" id="selection"></span></div>
<div id="cards" class="cards"></div>
<div class="grid"><section class="panel"><div class="panelhead"><div><h2>Where the alerts land</h2><p class="small">Hourly average price (EUR/MWh). Orange dots: probability ≥20%.</p></div></div><svg id="priceChart" viewBox="0 0 650 240" role="img" aria-label="Hourly prices, strike and model alerts"></svg><p class="small" id="chartDates"></p><div class="legend"><span><i class="dot" style="background:var(--ink)"></i>Observed price</span><span><i class="dot" style="background:var(--orange)"></i>Alert</span><span>Dashed: fixed spike threshold</span></div></section>
<section class="panel"><h2>Do probabilities match reality?</h2><p class="small">Full holdout: predicted probability versus observed spike rate.</p><svg id="calibration" viewBox="0 0 360 245" role="img" aria-label="Reliability plot against perfect calibration"></svg><p class="small">Above the diagonal = risk understated. Hover a point for the bin sample count.</p></section></div>
<div class="notice" id="drift"></div>
<section class="panel"><h2>Compare the models before using the signal</h2><p class="small">Selection uses May–June validation Brier score only. These are held-out results. Lower Brier is better; AUC measures ranking, not calibration. The recent-week benchmark has lower test Brier scores in both zones.</p><div class="scroll"><table><thead><tr><th>Candidate</th><th>Brier score</th><th>ROC AUC</th><th>Alert precision</th><th>Spike recall</th><th>Selection</th></tr></thead><tbody id="modelRows"></tbody></table></div></section>
<section class="panel"><div class="panelhead"><div><div class="eyebrow">Portfolio protection</div><h2>What does the hedge cost?</h2><p class="small">1 MWh each hour in each zone. All scenarios enforce a shared €60 daily premium budget and 8 MWh open-volume limit.</p></div><div class="controls"><label>Assumed premium<select id="premium"><option value="3">€3 / MWh</option><option value="8" selected>€8 / MWh</option><option value="15">€15 / MWh</option></select></label><label>Requested hedge<select id="volume"><option value="0.25">25% of load</option><option value="0.5" selected>50% of load</option></select></label></div></div>
<div id="hedgeCards" class="cards"></div><svg id="costChart" viewBox="0 0 1100 235" role="img" aria-label="Daily unhedged and hedged electricity procurement cost"></svg><div class="legend"><span><i class="dot" style="background:var(--ink)"></i>Unhedged</span><span><i class="dot" style="background:var(--teal)"></i>With paper caps</span></div><p class="small" id="tail"></p><p class="small">Cost = spot price × load + premium paid − cap payout. Payout = hedged MWh × max(hourly price − strike, 0). Premiums are attributed to delivery days for cost comparison; risk checks charge them on issue days.</p></section>
<section class="panel"><div class="eyebrow">Trade management / default €8, 50% scenario</div><h2>Replay the paper book</h2><p class="small">Orders move through SUBMITTED → APPROVED → OPEN → SETTLED, or REJECTED. At the end, all accepted contracts have settled. Move the replay time to see open positions.</p>
<div class="replay"><label>Replay time (UTC)<input id="replay" type="range" min="0" step="1"><output id="replayTime"></output></label><div><button id="firstActive">Show an active book</button><label>Status filter<select id="status"><option value="ALL">All statuses</option><option>OPEN</option><option>SETTLED</option><option>REJECTED</option></select></label></div></div>
<p class="small" id="bookSummary" aria-live="polite"></p><div class="scroll"><table><thead><tr><th>Zone</th><th>Delivery UTC</th><th>Risk signal</th><th>MWh</th><th>Status at replay time</th><th>Rejection / settled payout</th></tr></thead><tbody id="orderRows"></tbody></table></div>
<p class="small">Latest 30 matching orders at the selected time. Risk checks allocate capacity chronologically; DK1 is processed first when timestamps tie. Full order and event histories are exported as CSV.</p></section>
<details class="panel"><summary>Method, audit trail and limitations</summary><ul>
<li>Source: <a href="https://www.energidataservice.dk/tso-electricity/DayAheadPrices">Energinet Day-Ahead Prices</a>. Four 15-minute EUR/MWh observations are averaged into one hourly reference price. No missing-value interpolation.</li>
<li>Training: first eligible observation through 30 April 2026. Validation: 4 May–28 June. Simulated model lock: 30 June. Test: 2 July–29 September. No refit on validation or test.</li>
<li>Decision = delivery minus 48 hours. Newest price feature starts 24 hours before decision. Calendar features refer to delivery time in UTC. Archived revisions are not point-in-time publication records.</li>
<li>One L2-regularized logistic model per zone, compared with the training spike frequency and a trailing-week frequency. The 90th-percentile strike, scaling and coefficients use training only. Candidate selection uses validation Brier only.</li>
<li>20% alert trigger is illustrative, not an optimal option-pricing rule. It ignores expected spike severity. Contract premiums do not vary with market risk.</li>
<li>No exchange connection, real fills, collateral, taxes, transaction costs or counterparty risk. Open-volume and daily-budget limits are portfolio-wide. Kill-switch behavior is implemented and tested in the ledger.</li>
<li>Hourly-average caps may have different payoffs from quarter-hour products. Risk summaries use 90 complete UTC days, and only five days in the worst-5% mean; these are historical cost statistics, not forward loss guarantees.</li>
<li>Probabilities may deteriorate under a new price regime. Ranking skill is insufficient evidence of reliable probabilities or an executable hedge.</li></ul>
<p class="small"><a href="metrics.json">Metrics & source fingerprint</a> · <a href="forecasts.csv">Forecasts</a> · <a href="orders.csv">Orders</a> · <a href="events.csv">Event history</a> · <a href="daily_costs.csv">Daily costs</a></p></details>
<footer><span>Danish Price Spike Radar · Reproducible Python + SQLite research</span><span id="dataFoot"></span></footer>
</div><script id="data" type="application/json">__DATA__</script><script>
"use strict";
const D=JSON.parse(document.getElementById("data").textContent), $=id=>document.getElementById(id);
const fmt=(n,d=2)=>n==null?"—":Number(n).toLocaleString("en-GB",{minimumFractionDigits:d,maximumFractionDigits:d});
const pct=n=>n==null?"—":fmt(100*n,1)+"%";
const names={logistic:"Logistic regression",climatology:"Training frequency",rolling_week:"Recent 7-day frequency"};
function card(label,value,note){return '<div class="card"><div class="small">'+label+'</div><div class="value">'+value+'</div><div class="small">'+note+'</div></div>'}
function path(values,w,h,min,max){return values.map((v,i)=>(i?"L":"M")+(48+i*(w-66)/Math.max(1,values.length-1)).toFixed(1)+","+(h-34-(v-min)/(max-min)*(h-54)).toFixed(1)).join(" ")}
function axes(w,h,min,max){let s="";for(let i=0;i<4;i++){let v=min+(max-min)*i/3,y=h-34-i*(h-54)/3;s+='<line x1="48" x2="'+(w-18)+'" y1="'+y+'" y2="'+y+'" stroke="#e1e7e2"/><text x="40" y="'+(y+4)+'" text-anchor="end">'+fmt(v,0)+'</text>'}return s}
const start=Date.parse("2026-07-02T00:00:00Z"), end=Date.parse("2026-09-30T00:00:00Z"),weekMs=7*86400000;
for(let i=0;start+i*weekMs<end;i++){let option=document.createElement("option");option.value=i;option.textContent=new Date(start+i*weekMs).toISOString().slice(0,10);$("week").appendChild(option)}
function drawArea(){
 const a=$("area").value,m=D.meta.areas[a],metric=m.test.selected;
 $("selection").textContent=names[m.selected]+" selected on validation";
 $("cards").innerHTML=card("Fixed spike threshold","€"+fmt(m.strike_eur_mwh),"Training 90th percentile / MWh")+card("Observed spike frequency",pct(metric.spike_rate),metric.spikes+" of "+metric.n+" test hours")+card("Ranking · ROC AUC",fmt(metric.auc,3),"0.5 = chance ranking; 1 = perfect")+card("Alerts that were spikes",pct(metric.precision),"At the 20% risk trigger");
 const lo=start+Number($("week").value)*weekMs,hi=Math.min(lo+weekMs,end),rows=D.forecasts.filter(r=>r.area===a&&Date.parse(r.delivery)>=lo&&Date.parse(r.delivery)<hi);
 const prices=rows.map(r=>r.price),min=Math.min(0,...prices),max=Math.max(m.strike_eur_mwh,...prices)*1.08+1,w=650,h=240;
 let s=axes(w,h,min,max),sy=h-34-(m.strike_eur_mwh-min)/(max-min)*(h-54);
 s+='<line x1="48" x2="632" y1="'+sy+'" y2="'+sy+'" stroke="#b74b2b" stroke-dasharray="4 4"/><path d="'+path(prices,w,h,min,max)+'" fill="none" stroke="#172c39" stroke-width="1.6"/>';
 rows.forEach((r,i)=>{if(r.probability>=0.2){let x=48+i*(w-66)/Math.max(1,rows.length-1),y=h-34-(r.price-min)/(max-min)*(h-54);s+='<circle cx="'+x+'" cy="'+y+'" r="2.7" fill="#b74b2b"><title>'+r.delivery+' | €'+fmt(r.price)+' | risk '+pct(r.probability)+'</title></circle>'}});
 for(let i=0;i<rows.length;i+=24)s+='<text x="'+(48+i*(w-66)/Math.max(1,rows.length-1))+'" y="227">'+rows[i].delivery.slice(5,10)+'</text>';
 $("priceChart").innerHTML=s;
 $("chartDates").textContent=rows.length+" hours · "+new Date(lo).toISOString().slice(0,10)+" to "+new Date(hi-3600000).toISOString().slice(0,10)+" UTC";
 s='<line x1="42" y1="207" x2="335" y2="20" stroke="#9eafa7" stroke-dasharray="4 4"/>';
 for(let i=0;i<=4;i++){let v=i/4,x=42+293*v,y=207-187*v;s+='<text x="'+x+'" y="226" text-anchor="middle">'+Math.round(v*100)+'%</text><text x="32" y="'+(y+4)+'" text-anchor="end">'+Math.round(v*100)+'</text>'}
 s+='<text x="188" y="244" text-anchor="middle">Predicted probability</text>';
 metric.reliability.forEach(b=>{s+='<circle cx="'+(42+293*b.mean_probability)+'" cy="'+(207-187*b.spike_rate)+'" r="'+(4+Math.sqrt(b.n)/7)+'" fill="#007b75" opacity=".8"><title>'+b.n+' hours | predicted '+pct(b.mean_probability)+' | observed '+pct(b.spike_rate)+'</title></circle>'});
 $("calibration").innerHTML=s;
 $("drift").textContent="Calibration check: the training event rate was "+pct(m.train_spike_rate)+", compared with "+pct(metric.spike_rate)+" in this holdout. Treat these probabilities as research signals, not calibrated guarantees.";
 $("modelRows").innerHTML=Object.keys(names).map(k=>{const v=m.test[k];return "<tr><td>"+names[k]+"</td><td>"+fmt(v.brier,4)+"</td><td>"+fmt(v.auc,3)+"</td><td>"+pct(v.precision)+"</td><td>"+pct(v.recall)+"</td><td>"+(k===m.selected?"Used for paper book":"Benchmark")+"</td></tr>"}).join("");
}
function drawScenario(){
 const sc=D.scenarios.find(s=>s.summary.premium_eur_mwh===Number($("premium").value)&&s.summary.requested_hedge_mwh===Number($("volume").value)),s=sc.summary;
 $("hedgeCards").innerHTML=card("Premium paid","€"+fmt(s.premium_paid,0),"Assumed contract prices")+card("Cap payouts","€"+fmt(s.payout,0),"Historical synthetic settlement")+card("Change in procurement cost","€"+fmt(s.net_cost_change,0),"Negative = lower historical cost")+card("Accepted / rejected",fmt(s.status_counts.SETTLED||0,0)+" / "+fmt(s.status_counts.REJECTED||0,0),"Same risk limits in every scenario");
 const u=sc.daily.map(r=>r.unhedged_cost),v=sc.daily.map(r=>r.hedged_cost),min=Math.min(0,...u,...v),max=Math.max(...u,...v)*1.05+1,w=1100,h=235;
 let svg=axes(w,h,min,max)+'<path d="'+path(u,w,h,min,max)+'" fill="none" stroke="#172c39" stroke-width="1.6"/><path d="'+path(v,w,h,min,max)+'" fill="none" stroke="#007b75" stroke-width="2"/>';
 for(let i=0;i<sc.daily.length;i+=14)svg+='<text x="'+(48+i*(w-66)/Math.max(1,sc.daily.length-1))+'" y="224">'+sc.daily[i].date.slice(5)+'</text>';
 $("costChart").innerHTML=svg;
 $("tail").textContent="Daily 95th percentile: €"+fmt(s.unhedged_daily.p95,0)+" → €"+fmt(s.hedged_daily.p95,0)+". Mean of worst "+s.hedged_daily.tail_days+" days: €"+fmt(s.unhedged_daily.worst_5pct_mean,0)+" → €"+fmt(s.hedged_daily.worst_5pct_mean,0)+". Computed separately for each cost series; "+s.hedged_daily.days+" complete days.";
}
const eventTimes=D.events.map(e=>Date.parse(e.time)),first=eventTimes.length?Math.min(...eventTimes):start,last=eventTimes.length?Math.max(...eventTimes):end;
$("replay").max=Math.ceil((last-first)/3600000);$("replay").value=$("replay").max;
function drawBook(){
 const time=first+Number($("replay").value)*3600000,states={};
 D.events.forEach(e=>{if(Date.parse(e.time)<=time)states[e.order_id]=e.status});
 const existing=D.orders.filter(o=>states[o.id]),counts={};existing.forEach(o=>{let s=states[o.id];counts[s]=(counts[s]||0)+1});
 $("replayTime").textContent=new Date(time).toISOString().slice(0,16).replace("T"," ")+" UTC";
 $("bookSummary").textContent=(counts.OPEN||0)+" open · "+(counts.SETTLED||0)+" settled · "+(counts.REJECTED||0)+" rejected. Showing the default scenario, independent of premium controls above.";
 const rows=existing.filter(o=>$("status").value==="ALL"||states[o.id]===$("status").value).slice(-30).reverse();
 $("orderRows").innerHTML=rows.length?rows.map(o=>{let s=states[o.id];return "<tr><td>"+o.area+"</td><td>"+o.delivery.slice(0,16).replace("T"," ")+"</td><td>"+pct(o.probability)+"</td><td>"+fmt(o.volume)+"</td><td><span class='state "+s+"'>"+s+"</span></td><td>"+(s==="REJECTED"?o.reason:s==="SETTLED"?"€"+fmt(o.payout):"Awaiting delivery")+"</td></tr>"}).join(""):'<tr><td colspan="6">No matching orders at this time.</td></tr>';
}
$("firstActive").onclick=()=>{$("replay").value=0;$("status").value="OPEN";drawBook()};
["area","week"].forEach(id=>$(id).onchange=drawArea);
["premium","volume"].forEach(id=>$(id).onchange=drawScenario);
$("replay").oninput=drawBook;$("status").onchange=drawBook;
$("dataFoot").textContent=fmt(D.meta.source.records,0)+" source intervals · 4,320 held-out predictions";
drawArea();drawScenario();drawBook();
</script></body></html>"""

