"""Offline Plotly presentation of saved estimates, independent of model estimation."""

import html
import json
from pathlib import Path

import pandas as pd
from plotly.offline import get_plotlyjs

from portfolio_backtester.config import Settings, validate_phase2_paths
from portfolio_backtester.data.storage import atomic_json, atomic_target, pipeline_lock
from .download import file_hash
from .run import INTERPRETATION, load_regression_artifacts, input_locks, _read_inputs


def render_dashboard(results: pd.DataFrame, report: dict) -> str:
    """Embed result records, JavaScript, styles, and Plotly in one portable HTML page."""
    records = results.copy()
    for column in ("regression_start_date", "regression_end_date", "as_of_date"):
        records[column] = records[column].dt.strftime("%Y-%m-%d")
    payload = {"results": json.loads(records.to_json(orient="records", double_precision=15)), "report": report,
               "csv": results.to_csv(index=False, date_format="%Y-%m-%d", float_format="%.15g")}
    data = json.dumps(payload, allow_nan=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return TEMPLATE.replace("__PLOTLY_LIBRARY__", get_plotlyjs()).replace("__RESEARCH_DATA__", data).replace("__DISCLAIMER__", html.escape(INTERPRETATION))


def generate_factor_report(settings: Settings) -> Path:
    """Generate a report only from validated persisted regression artifacts."""
    validate_phase2_paths(settings)
    with pipeline_lock(settings.path("regression_report_path").parent / ".regression.lock"):
        results, report = load_regression_artifacts(settings)
        with input_locks(settings):
            _, _, current = _read_inputs(settings)
            if any(current[key] != report["input_provenance"][key] for key in ("stock_returns_sha256", "factor_data_sha256")):
                raise ValueError("Research inputs changed before dashboard publication; rerun regression")
            output = settings.path("dashboard_path")
            with atomic_target(output) as temporary:
                temporary.write_text(render_dashboard(results, report), encoding="utf-8")
            atomic_json({"regression_run_id": report["run_id"], "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
                         "html_path": str(output.relative_to(settings.root)), "html_sha256": file_hash(output),
                         "results_sha256": report["outputs"]["results"]["sha256"], "offline": True},
                        settings.path("regression_report_path").parent / "phase2" / "dashboard_manifest.json")
            return output


TEMPLATE = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SGC | Six-Factor Research</title>
<style>
:root{--navy:#142b40;--ink:#1e3447;--muted:#647487;--blue:#256b98;--teal:#237e76;--border:#dce4eb;--paper:#f3f6f9}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
header{background:var(--navy);color:white;padding:30px max(24px,calc((100vw - 1380px)/2)) 26px}.eyebrow{text-transform:uppercase;letter-spacing:.14em;font-size:11px;font-weight:700;opacity:.75}
h1{font-size:30px;line-height:1.2;margin:8px 0 10px;font-weight:650}header p{margin:0;color:#c4d8e7;max-width:930px}.badge{display:inline-block;background:#29485f;color:#e1eef5;border:1px solid #52728a;border-radius:20px;padding:4px 12px;font-size:12px;margin-top:16px}
main{max-width:1428px;margin:auto;padding:24px}.overview{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px;margin-bottom:20px}.card,.panel{background:white;border:1px solid var(--border);border-radius:9px}.card{padding:17px 16px}.label{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);font-weight:650}.value{font-size:25px;font-weight:700;margin-top:6px;line-height:1.25}.small-value{font-size:15px}.sub{font-size:12px;color:var(--muted);margin-top:5px}.panel{padding:22px;margin-bottom:20px}h2{font-size:19px;margin:0 0 4px}h3{font-size:14px;margin:0 0 9px}.intro{color:var(--muted);font-size:13px;margin:0 0 18px}.split{display:grid;grid-template-columns:1.5fr 1fr;gap:22px}.toolbar{display:flex;gap:14px;align-items:end;flex-wrap:wrap;margin-bottom:18px}label.control{display:flex;flex-direction:column;gap:5px;font-size:12px;font-weight:600}select,input[type=search]{font:inherit;padding:9px 12px;border:1px solid #bccbd7;border-radius:5px;color:var(--ink);background:white;min-width:180px}button{font:inherit;cursor:pointer;border-radius:5px;padding:9px 14px;border:1px solid var(--border);background:white;color:var(--ink)}button.primary{background:var(--teal);color:white;border-color:var(--teal)}button:hover{filter:brightness(.96)}select:focus,input:focus,button:focus{outline:2px solid #62a6d2;outline-offset:2px}.chart{height:330px;min-width:0}.stats{display:grid;grid-template-columns:1fr 1fr;gap:12px;align-content:start}.stat{background:#f6f8fb;border-radius:6px;padding:14px}.stat .value{font-size:23px}.note{background:#eef5f9;padding:12px 14px;border-left:3px solid var(--blue);font-size:12px;color:#486278;margin:12px 0 0}.choices{display:grid;grid-template-columns:repeat(8,1fr);gap:8px 12px;max-height:140px;overflow:auto;border:1px solid var(--border);padding:12px;border-radius:5px;margin:0 0 18px}.choices label{font-size:12px;display:flex;gap:5px;align-items:center}.comparison-chart{height:350px}.table-wrap{overflow:auto;max-height:560px;border:1px solid var(--border);border-radius:5px}table{border-collapse:collapse;width:100%;font-size:12px;font-variant-numeric:tabular-nums}th,td{padding:11px 12px;text-align:right;border-bottom:1px solid #e7edf2;white-space:nowrap}th{position:sticky;top:0;background:#edf3f7;color:#345269;z-index:1}th:first-child,td:first-child{text-align:left}th button{padding:0;border:0;background:none;font-size:11px;font-weight:700;border-radius:0}tbody tr:hover{background:#f1f8fb}.result-count{margin-left:auto;color:var(--muted);font-size:12px}.warning{border:1px solid #e3cfaa;background:#fffaf0;border-radius:7px;padding:16px 18px;margin-bottom:20px}.warning h2{font-size:16px}.failure-list{font-size:13px;margin:8px 0 0;padding-left:18px}.failure-list li{padding:3px}.footer{font-size:12px;color:var(--muted);padding:5px 0 20px}.footer p{margin:6px 0}.factor-key{display:flex;gap:8px;flex-wrap:wrap;font-size:11px;color:var(--muted)}.factor-key span{background:#f0f4f7;padding:4px 7px;border-radius:4px}.status{color:#a66a19;font-size:12px;font-weight:600}
@media(max-width:1100px){.overview{grid-template-columns:repeat(3,1fr)}.choices{grid-template-columns:repeat(6,1fr)}}
@media(max-width:760px){header{padding:22px}main{padding:14px}h1{font-size:25px}.overview{grid-template-columns:repeat(2,1fr)}.split{grid-template-columns:1fr}.panel{padding:16px}.choices{grid-template-columns:repeat(3,1fr)}.result-count{margin-left:0}.chart{height:310px}}
</style>
<script>__PLOTLY_LIBRARY__</script>
</head>
<body>
<header><div class="eyebrow">University of Toronto · St. George Capital</div><h1>Six-Factor Research Dashboard</h1><p>Fama–French Five-Factor + Momentum · Daily OLS estimates from observed stock excess returns.</p><div class="badge" id="as-of-badge"></div></header>
<main>
<div class="overview" id="overview"></div>
<section class="panel"><h2>Stock Factor Profile</h2><p class="intro">Select a security to inspect its historical factor exposures and model fit.</p>
<div class="toolbar"><label class="control" for="stock-select">Stock selection<select id="stock-select" aria-label="Stock selection"></select></label><span id="sample-label" class="sub"></span></div>
<div class="split"><div><h3>Factor Exposures</h3><div id="exposure-chart" class="chart" aria-label="Six factor beta bar chart"></div><div class="factor-key"><span>Mkt-RF · Market</span><span>SMB · Size</span><span>HML · Value</span><span>RMW · Profitability</span><span>CMA · Investment</span><span>Mom · Momentum</span></div></div><div><h3>Alpha and Model Fit</h3><div class="stats" id="stock-stats"></div><p class="note">Historical annualized alpha is the daily intercept multiplied by the annualization factor. It is a linear approximation, not a realized annual investment return.</p></div></div></section>
<section class="panel"><h2>Stock Comparison</h2><p class="intro">Compare observed exposures or historical model diagnostics across selected securities.</p><div class="toolbar"><label class="control" for="comparison-metric">Comparison metric<select id="comparison-metric"><option value="beta_mkt">Market Beta</option><option value="beta_hml">Value Beta</option><option value="beta_mom">Momentum Beta</option><option value="r_squared">R-Squared</option><option value="alpha_annualized">Historical Annualized Alpha</option></select></label><button id="compare-defaults">Select core stocks</button><button id="compare-clear">Clear selection</button></div><div id="comparison-choices" class="choices" aria-label="Stocks to compare"></div><div id="comparison-chart" class="comparison-chart"></div></section>
<section class="panel"><h2>Full Regression Results</h2><p class="intro">All successful estimates. Select any column header to sort; search by ticker or export the complete result set.</p><div class="toolbar"><label class="control" for="result-filter">Filter by ticker<input type="search" id="result-filter" placeholder="Search ticker" autocomplete="off"></label><button class="primary" id="export-csv">Download all results (CSV)</button><span class="result-count" id="result-count"></span></div><div class="table-wrap"><table id="results-table"><thead><tr id="table-head"></tr></thead><tbody id="table-body"></tbody></table></div></section>
<section class="warning" id="failures" hidden><h2>Skipped Regressions</h2><p class="intro">These securities were not silently excluded. The candidate window was not extended to obtain more observations.</p><ul class="failure-list" id="failure-list"></ul></section>
<section class="panel"><h2>Methodology and Data Availability</h2><p class="intro" id="methodology"></p><p class="note">__DISCLAIMER__</p><p class="sub" id="data-gap-note"></p><p class="sub">Current revised factor snapshots are not a point-in-time database. An observation-date cutoff does not establish historical publication availability or eliminate Look-Ahead Bias. Current stock selection retains survivorship bias. Conventional OLS t-tests do not adjust for heteroskedasticity, serial correlation, or multiple testing.</p></section>
<footer class="footer"><p id="provenance"></p><p>This self-contained HTML embeds its data and Plotly library. No server, CDN, or internet connection is needed to view it.</p></footer>
</main>
<script id="research-data" type="application/json">__RESEARCH_DATA__</script>
<script>
'use strict';
const DATA=JSON.parse(document.getElementById('research-data').textContent);
const rows=DATA.results, report=DATA.report, alignment=report.alignment, method=report.methodology;
const get=id=>document.getElementById(id), pct=v=>Number.isFinite(v)?(v*100).toFixed(2)+'%':'—', num=(v,d=3)=>Number.isFinite(v)?v.toFixed(d):'—';
const defaultTickers=['AAPL','MSFT','NVDA','GOOGL','JPM'].filter(t=>rows.some(r=>r.ticker===t));
if(!defaultTickers.length)defaultTickers.push(...rows.slice(0,5).map(r=>r.ticker));
const layout={font:{family:'-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif',size:12,color:'#365067'},paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',margin:{t:15,b:45,l:55,r:15},xaxis:{gridcolor:'#e8eef3',zerolinecolor:'#c6d1db'},yaxis:{gridcolor:'#e8eef3',zerolinecolor:'#a8b9c6'},showlegend:false};
const config={responsive:true,displaylogo:false,modeBarButtonsToRemove:['lasso2d','select2d']};
function card(label,value,sub='',small=false){const box=document.createElement('div');box.className='card';const l=document.createElement('div');l.className='label';l.textContent=label;const v=document.createElement('div');v.className='value'+(small?' small-value':'');v.textContent=value;const s=document.createElement('div');s.className='sub';s.textContent=sub;box.append(l,v,s);return box;}
get('overview').append(card('Stocks Analyzed',String(rows.length),'of '+report.configured_tickers.length+' configured'),card('Regression Window',String(method.regression_window),'common-date candidates; min '+method.minimum_valid_observations),card('Factor Data Coverage',alignment.factor_complete_start_date,'through '+alignment.factor_complete_end_date,true),card('Latest Factor Date',alignment.factor_complete_end_date,'complete seven-field daily data',true),card('Median R-Squared',pct(report.median_r_squared),'in-sample explanatory fit'),card('Failed Regressions',String(Object.keys(report.failed_tickers).length),'reasons listed below'));
get('as-of-badge').textContent='Analysis as of '+alignment.as_of_date+' · '+method.regression_window+'-day window · Offline report';
for(const row of rows){const option=document.createElement('option');option.value=row.ticker;option.textContent=row.ticker;get('stock-select').append(option);}
get('stock-select').value=rows.some(r=>r.ticker==='AAPL')?'AAPL':rows[0].ticker;
function stockProfile(){const r=rows.find(r=>r.ticker===get('stock-select').value);get('sample-label').textContent=r.regression_start_date+' to '+r.regression_end_date+' · '+r.observations+' valid observations';const betas=['beta_mkt','beta_smb','beta_hml','beta_rmw','beta_cma','beta_mom'].map(k=>r[k]);Plotly.react('exposure-chart',[{type:'bar',x:['Mkt-RF','SMB','HML','RMW','CMA','Mom'],y:betas,marker:{color:betas.map(v=>v>=0?'#286f9a':'#be7750')},hovertemplate:'%{x}<br>Beta %{y:.4f}<extra></extra>'}],{...layout,yaxis:{...layout.yaxis,title:{text:'Factor Beta'}}},config);get('stock-stats').replaceChildren();for(const [label,value] of [['Historical Annualized Alpha',pct(r.alpha_annualized)],['R-Squared',pct(r.r_squared)],['Adjusted R-Squared',pct(r.adjusted_r_squared)],['Annualized Residual Volatility',pct(r.residual_volatility_annualized)],['Regression Observations',String(r.observations)],['Alpha t-Stat / p-Value',num(r.alpha_t_stat,2)+' / '+num(r.alpha_p_value,4)]]){const el=card(label,value);el.className='stat';get('stock-stats').append(el);}}
get('stock-select').addEventListener('change',stockProfile);
for(const r of rows){const label=document.createElement('label'),checkbox=document.createElement('input');checkbox.type='checkbox';checkbox.value=r.ticker;checkbox.checked=defaultTickers.includes(r.ticker);checkbox.addEventListener('change',compare);label.append(checkbox,document.createTextNode(r.ticker));get('comparison-choices').append(label);}
function compare(){const selected=[...get('comparison-choices').querySelectorAll('input:checked')].map(e=>e.value);const subset=rows.filter(r=>selected.includes(r.ticker)), metric=get('comparison-metric').value,percentage=['alpha_annualized','r_squared'].includes(metric);const title=get('comparison-metric').selectedOptions[0].textContent;Plotly.react('comparison-chart',[{type:'bar',x:subset.map(r=>r.ticker),y:subset.map(r=>r[metric]),marker:{color:subset.map(r=>r[metric]>=0?'#237e76':'#be7750')},hovertemplate:percentage?'%{x}<br>%{y:.2%}<extra></extra>':'%{x}<br>%{y:.4f}<extra></extra>'}],{...layout,yaxis:{...layout.yaxis,title:{text:title},tickformat:percentage?'.0%':'.2f'},annotations:subset.length?[]:[{text:'Select one or more stocks to compare',xref:'paper',yref:'paper',x:.5,y:.5,showarrow:false}]},config);}
get('comparison-metric').addEventListener('change',compare);get('compare-clear').addEventListener('click',()=>{get('comparison-choices').querySelectorAll('input').forEach(e=>e.checked=false);compare();});get('compare-defaults').addEventListener('click',()=>{get('comparison-choices').querySelectorAll('input').forEach(e=>e.checked=defaultTickers.includes(e.value));compare();});
const columns=[['ticker','Ticker'],['alpha_daily','Alpha Daily'],['alpha_annualized','Historical Alpha (Annualized)'],['beta_mkt','Market Beta'],['beta_smb','Size Beta'],['beta_hml','Value Beta'],['beta_rmw','Profitability Beta'],['beta_cma','Investment Beta'],['beta_mom','Momentum Beta'],['r_squared','R-Squared'],['adjusted_r_squared','Adjusted R-Squared'],['residual_volatility_annualized','Residual Volatility (Annualized)'],['alpha_t_stat','Alpha t-Stat'],['alpha_p_value','Alpha p-Value'],['observations','Observations'],['regression_start_date','Start Date'],['regression_end_date','End Date'],['as_of_date','As-of Date'],['model_version','Model Version']];
let sortKey='ticker',direction=1;
for(const [key,title] of columns){const th=document.createElement('th'),button=document.createElement('button');button.textContent=title;button.title='Sort by '+title;button.addEventListener('click',()=>{direction=sortKey===key?-direction:1;sortKey=key;table();});th.append(button);get('table-head').append(th);}
function table(){const filter=get('result-filter').value.trim().toUpperCase();const filtered=rows.filter(r=>r.ticker.includes(filter)).slice().sort((a,b)=>{const x=a[sortKey],y=b[sortKey];return(typeof x==='number'?x-y:String(x).localeCompare(String(y)))*direction;});get('table-body').replaceChildren();for(const row of filtered){const tr=document.createElement('tr');for(const [key] of columns){const td=document.createElement('td'),value=row[key];td.textContent=['alpha_annualized','r_squared','adjusted_r_squared','residual_volatility_annualized'].includes(key)?pct(value):key==='observations'?String(value):typeof value==='number'?num(value,key==='alpha_daily'?6:4):value;tr.append(td);}get('table-body').append(tr);}get('result-count').textContent=filtered.length+' of '+rows.length+' estimates';}
get('result-filter').addEventListener('input',table);get('export-csv').addEventListener('click',()=>{const blob=new Blob([DATA.csv],{type:'text/csv;charset=utf-8;'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='factor_regression_results_'+alignment.as_of_date+'.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
const failures=Object.entries(report.failed_tickers);get('failures').hidden=failures.length===0;for(const [ticker,failure] of failures){const li=document.createElement('li');li.textContent=ticker+': '+failure.reason+' · '+failure.observations+' valid observations'+(failure.minimum_required?' / '+failure.minimum_required+' required':'');get('failure-list').append(li);}
get('methodology').textContent='OLS with an intercept and six factor loadings. Excess Return = Stock Daily Return − same-date RF. The last '+method.regression_window+' common dates form a fixed candidate window; each stock needs at least '+method.minimum_valid_observations+' complete observations. Residual volatility uses sample residual standard deviation × √'+method.annualization_factor+'. No forward fill or zero fill is applied.';
get('data-gap-note').textContent=alignment.stock_dates_without_complete_factors.length+' stock dates lack complete factor observations within the requested information horizon. They are recorded in the alignment report and are not imputed. The latest stock date is '+alignment.stock_end_date+'; the latest complete factor date is '+alignment.factor_complete_end_date+'.';
get('provenance').textContent='Generated '+report.generated_at+' · Model '+report.model_version+' · Factor snapshot '+report.input_provenance.factor_downloaded_at+' · Source: Kenneth R. French Data Library · Regression run '+report.run_id.slice(0,12);
stockProfile();compare();table();
</script>
</body>
</html>
'''
