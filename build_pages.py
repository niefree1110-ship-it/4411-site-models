#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
4411.site · 模型工作台「下级页面」生成器

产出：
  models/leaderboard.html   AI 模型榜     ← aihot.news/leaderboard
  models/resets.html        额度重置监控   ← aihot.news/resets
  models/free-tokens.html   Token 羊毛全集 ← aihot.news/free-tokens
  （并在 models/index.html 注入下级页面入口，重复运行幂等）

三个子页面共享：
  - 工作台的三段内联 CSS（基础 / 深色皮肤 / Orbit Nav），视觉与站点完全一致
  - 工作台修好的 Orbit Nav 动画脚本
  - models/aihot-data.js（由 build.py 每日生成的数据快照）

用法：python build_pages.py
"""
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(__file__).resolve().parent
MODELS = ROOT / "models"
PAGE = MODELS / "index.html"

NAV_HTML = '''<nav class="onav" aria-label="站点导航">
  <div class="onav-rail">
    <canvas class="onav-canvas" aria-hidden="true"></canvas>
    <a class="onav-item" href="/"><span class="ico">◉</span>首页</a>
    <span class="onav-sep"></span>
    <a class="onav-item" href="/models/" aria-current="page"><span class="ico">✦</span>AI 模型工作台</a>
    <span class="onav-sep"></span>
    <a class="onav-item" href="/tools/"><span class="ico">🛠</span>免费工具</a>
  </div>
</nav>'''

SUBNAV = '''<div class="subnav" aria-label="模型工作台下级页面">
    <a href="index.html" data-p="index">⌂ 工作台</a>
    <a href="leaderboard.html" data-p="leaderboard">▤ AI 模型榜</a>
    <a href="resets.html" data-p="resets">◷ 额度重置监控</a>
    <a href="free-tokens.html" data-p="free-tokens">◎ Token 羊毛全集</a>
  </div>'''

# 子页面专属样式：二级导航、榜单、时间线、日历、移动端表格横向滚动
EXTRA_CSS = r'''
/* ===== 下级页面专用（2026-11-13）===== */
.subnav{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}
.subnav a{display:inline-flex;align-items:center;gap:6px;padding:8px 15px;border-radius:999px;font-size:13px;font-weight:600;text-decoration:none;
  background:var(--card);border:1px solid var(--border);color:var(--muted);transition:.18s;backdrop-filter:blur(10px)}
.subnav a:hover{border-color:var(--brand);color:var(--brand);transform:translateY(-1px)}
.subnav a[aria-current="page"]{background:var(--brand-soft);border-color:var(--brand);color:var(--brand);box-shadow:0 0 0 1px rgba(255,180,92,.18)}
.tbl-wrap{overflow-x:auto;border-radius:var(--radius);border:1px solid var(--border);background:var(--card);box-shadow:var(--shadow)}
.tbl-wrap table{border:none;box-shadow:none;border-radius:0;min-width:820px}
.rank{font-family:"SFMono-Regular",Consolas,monospace;font-size:14px;font-weight:700;color:var(--muted)}
.rank.top{color:var(--brand)}
.score{font-size:19px;font-weight:700;color:var(--brand);font-variant-numeric:tabular-nums}
.score-bar{display:block;height:4px;border-radius:4px;background:rgba(255,255,255,.08);margin-top:5px;overflow:hidden}
.score-bar i{display:block;height:100%;background:linear-gradient(90deg,var(--orange),var(--brand));border-radius:4px}
.vendor{font-size:11px;color:var(--muted)}
.cov{font-size:12px;color:var(--muted)}
.cov b{color:var(--text);font-weight:600}
.notice-card{background:var(--card);border:1px solid rgba(255,180,92,.28);border-radius:var(--radius);padding:18px 20px;margin-bottom:18px;box-shadow:var(--shadow);position:relative;overflow:hidden}
.notice-card::before{content:'';position:absolute;inset:0 auto 0 0;width:3px;background:linear-gradient(180deg,var(--brand),var(--orange))}
.notice-card h2{font-size:17px;margin-bottom:6px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.notice-card .win{display:inline-block;background:var(--orange-soft);color:var(--orange);border-radius:999px;padding:3px 12px;font-size:12px;font-weight:700}
.notice-card p{font-size:13px;color:var(--muted);margin-top:8px;line-height:1.9}
.notice-card blockquote{margin-top:10px;padding:10px 14px;border-left:2px solid var(--brand);background:rgba(255,180,92,.06);font-size:13px;color:var(--text);border-radius:0 8px 8px 0}
.timeline{position:relative;padding-left:22px;margin-bottom:8px}
.timeline::before{content:'';position:absolute;left:6px;top:6px;bottom:6px;width:1px;background:linear-gradient(180deg,var(--brand),rgba(255,180,92,.1))}
.tl-item{position:relative;background:var(--card);border:1px solid var(--border);border-radius:12px;padding:12px 16px;margin-bottom:10px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;box-shadow:var(--shadow)}
.tl-item::before{content:'';position:absolute;left:-21px;top:18px;width:9px;height:9px;border-radius:50%;background:var(--brand);box-shadow:0 0 0 4px var(--brand-soft)}
.tl-item.pending::before{background:var(--orange);box-shadow:0 0 0 4px var(--orange-soft);animation:tl-pulse 2.4s ease-in-out infinite}
@keyframes tl-pulse{0%,100%{opacity:.5}50%{opacity:1}}
.tl-date{font-family:"SFMono-Regular",Consolas,monospace;font-size:13px;font-weight:700;min-width:96px}
.hist-month{font-size:13px;font-weight:700;color:var(--brand);margin:16px 0 8px}
.hist-grid{display:flex;flex-wrap:wrap;gap:7px}
.hist-grid a{font-family:"SFMono-Regular",Consolas,monospace;font-size:12px;padding:5px 10px;border-radius:8px;background:var(--card);border:1px solid var(--border);color:var(--muted);text-decoration:none;transition:.15s}
.hist-grid a:hover{border-color:var(--brand);color:var(--brand)}
.src-line{font-size:12px;color:var(--muted);margin-top:10px}
.src-line a{color:var(--brand)}
@media(max-width:700px){
  table{display:table!important}
  .mob{display:none!important}
  .tl-date{min-width:auto}
}
'''

COMMON_JS = r'''
/* ===== 下级页面公共层 ===== */
const D = window.AIHOT || {leaderboard:[],resets:{},freebies:[]};
const esc = s => String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money = v => (v==null?'—':'¥'+Number(v).toFixed(2));
const STAMP = D.updated || '—';
document.getElementById('stamp').textContent = '快照：'+(STAMP.length>16?STAMP.slice(5,16):STAMP);
document.getElementById('stampInline').textContent = STAMP;
document.querySelectorAll('.subnav a').forEach(a=>{
  if(a.dataset.p===PAGE_KEY) a.setAttribute('aria-current','page');
});
function bindSearch(inputId, clearId, cb){
  const i=document.getElementById(inputId), c=document.getElementById(clearId);
  const sync=()=>{ c.style.display=i.value?'block':'none'; cb(); };
  i.addEventListener('input',sync);
  c.addEventListener('click',()=>{ i.value=''; i.focus(); sync(); });
}
function bindSort(scope, state, rerender){
  document.querySelectorAll(scope+' th[data-sort]').forEach(th=>{
    th.tabIndex=0; th.title='点击排序';
    const go=()=>{
      const k=th.dataset.sort;
      if(state.key===k) state.dir=state.dir==='desc'?'asc':'desc';
      else { state.key=k; state.dir=(k==='name'||k==='vendor')?'asc':'desc'; }
      document.querySelectorAll(scope+' th[data-sort]').forEach(x=>x.classList.remove('asc','desc'));
      th.classList.add(state.dir); rerender();
    };
    th.addEventListener('click',go);
    th.addEventListener('keydown',e=>{ if(e.key==='Enter'||e.key===' '){ e.preventDefault(); go(); } });
  });
}
function sortRows(list, state, get){
  const d=state.dir==='asc'?1:-1;
  return list.slice().sort((a,b)=>{
    const va=get(a,state.key), vb=get(b,state.key);
    if(va==null&&vb==null) return 0;
    if(va==null) return 1;
    if(vb==null) return -1;
    return va<vb?-d:(va>vb?d:0);
  });
}
'''

TPL = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>%%TITLE%% · AI 模型工作台 · 4411.site</title>
<style>
%%CSS%%
</style>
</head>
<body>
%%NAV%%
<div class="wrap">
  <header>
    <div>
      <h1><span class="dot"></span>%%H1%%</h1>
      <div class="sub">%%SUB%%</div>
    </div>
    <div class="head-right">
      <a class="btn-key" href="index.html"><span class="k">↩</span>返回模型工作台</a>
      <div class="badge" id="stamp">快照：--</div>
    </div>
  </header>

  %%SUBNAV%%

  <div class="note">
    数据来源 <a class="klink" href="%%SOURCE_URL%%" target="_blank" rel="noopener">%%SOURCE_LABEL%% ↗</a> ·
    快照时间 <b id="stampInline">--</b> · 全部为<b>北京时间 UTC+8</b>。
    本站只做数据快照与再呈现，评分口径、额度与活动规则均以<b>原站及厂商官方公告</b>为准。
    %%NOTE_EXTRA%%
  </div>

%%BODY%%

  <footer>4411.site · AI 模型工作台下级页面 · 数据快照 <span id="genFoot">--</span> · <a href="index.html">返回工作台</a></footer>
</div>

<script src="aihot-data.js"></script>
<script>
const PAGE_KEY = '%%PAGE_KEY%%';
%%COMMON_JS%%
document.getElementById('genFoot').textContent = STAMP;
%%JS%%
</script>
<script>
%%NAVJS%%
</script>
</body>
</html>
'''


def common_assets():
    t = PAGE.read_text(encoding="utf-8")
    styles = re.findall(r"<style>(.*?)</style>", t, re.S)
    scripts = re.findall(r"<script>(.*?)</script>", t, re.S)
    if len(styles) < 3 or len(scripts) < 2:
        sys.exit("工作台页面的样式/脚本结构异常，无法提取共用资源")
    return "\n".join(styles) + "\n" + EXTRA_CSS, scripts[1]


def render(*, title, h1, sub, source_url, source_label, page_key, body, js, note_extra=""):
    css, navjs = common_assets()
    out = (TPL.replace("%%TITLE%%", title)
              .replace("%%H1%%", h1)
              .replace("%%SUB%%", sub)
              .replace("%%SOURCE_URL%%", source_url)
              .replace("%%SOURCE_LABEL%%", source_label)
              .replace("%%PAGE_KEY%%", page_key)
              .replace("%%NOTE_EXTRA%%", note_extra)
              .replace("%%NAV%%", NAV_HTML)
              .replace("%%SUBNAV%%", SUBNAV)
              .replace("%%CSS%%", css)
              .replace("%%COMMON_JS%%", COMMON_JS)
              .replace("%%NAVJS%%", navjs)
              .replace("%%BODY%%", body)
              .replace("%%JS%%", js))
    return out


# ---------------------------------------------------------------- 模型榜
LB_BODY = r'''  <div class="cards" id="cards"></div>
  <div class="toolbar">
    <div class="search-wrap"><input class="search" id="q" type="text" placeholder="搜索模型名 / 厂商…"><button class="search-clear" id="qClear" type="button" aria-label="清空搜索">×</button></div>
    <div class="filters" id="filters">
      <span class="chip on" data-f="all">全部</span>
      <span class="chip" data-f="cn">国产模型</span>
      <span class="chip" data-f="global">海外模型</span>
      <span class="chip" data-f="full">评测覆盖 100%</span>
    </div>
    <span class="result-count" id="cnt"></span>
  </div>
  <div class="tbl-wrap" id="lbTbl"><table>
    <thead><tr>
      <th class="sortable" data-sort="rank">名次</th>
      <th class="sortable" data-sort="name">模型 / 厂商</th>
      <th class="sortable" data-sort="date">上线日期</th>
      <th class="sortable" data-sort="coverage">评测覆盖</th>
      <th class="sortable" data-sort="cache">缓存价</th>
      <th class="sortable" data-sort="input">输入价</th>
      <th class="sortable" data-sort="output">输出价</th>
      <th class="sortable desc" data-sort="score">AIHOT 评分</th>
    </tr></thead>
    <tbody id="tb"></tbody>
  </table></div>
  <div class="src-line">价格单位：人民币 / 百万 Token。点模型名可查看 AIHOT 原始评测明细。</div>'''

LB_JS = r'''const LB = D.leaderboard || [];
const CN_VENDORS = new Set(['Alibaba','DeepSeek','Moonshot AI','Tencent','Xiaomi','Z.ai','ByteDance','Baidu','MiniMax','Meituan','StepFun','InclusionAI','Huawei','01.AI']);
const LB_SORT = {key:'score',dir:'desc'};
const LB_GET = (m,k)=> k==='name' ? String(m.name||'').toLowerCase() : (m[k]==null?null:Number(m[k]));
const LB_DATE = m => m.date || '';
function lbVal(m,k){ if(k==='date') return LB_DATE(m); return LB_GET(m,k); }
function lbCards(){
  const vendors=new Set(LB.map(m=>m.vendor)).size;
  const top=LB.length?Math.max(...LB.map(m=>m.score||0)).toFixed(1):'—';
  const cn=LB.filter(m=>CN_VENDORS.has(m.vendor)).length;
  document.getElementById('cards').innerHTML=
    '<div class="card"><div class="k">上榜模型</div><div class="v">'+LB.length+' <small>个</small></div></div>'+
    '<div class="card"><div class="k">最高评分</div><div class="v">'+top+'</div></div>'+
    '<div class="card"><div class="k">国产模型</div><div class="v">'+cn+' <small>个</small></div></div>'+
    '<div class="card"><div class="k">涉及厂商</div><div class="v">'+vendors+' <small>家</small></div></div>';
}
function lbRows(){
  const q=(document.getElementById('q').value||'').trim().toLowerCase();
  const f=document.querySelector('#filters .chip.on').dataset.f;
  const list=LB.filter(m=>{
    if(q && !((m.name||'')+' '+(m.vendor||'')).toLowerCase().includes(q)) return false;
    if(f==='cn') return CN_VENDORS.has(m.vendor);
    if(f==='global') return !CN_VENDORS.has(m.vendor);
    if(f==='full') return m.coverage>=100;
    return true;
  });
  return sortRows(list, LB_SORT, lbVal);
}
function lbRender(){
  const list=lbRows();
  document.getElementById('cnt').textContent = list.length===LB.length ? '共 '+list.length+' 个模型' : '匹配 '+list.length+' / '+LB.length;
  const tb=document.getElementById('tb');
  if(!list.length){ tb.innerHTML='<tr><td colspan="8" class="empty">没有匹配的模型</td></tr>'; return; }
  tb.innerHTML=list.map(m=>{
    const pct=Math.max(0,Math.min(100,(m.score||0)));
    return '<tr>'+
      '<td><span class="rank'+(m.rank<=3?' top':'')+'">'+String(m.rank).padStart(2,'0')+'</span></td>'+
      '<td><div class="mname"><a href="https://aihot.news/leaderboard/'+esc(m.slug)+'" target="_blank" rel="noopener" style="color:inherit;text-decoration:none;border-bottom:1px dotted var(--border)">'+esc(m.name)+'</a></div><div class="vendor">'+esc(m.vendor)+'</div></td>'+
      '<td class="num">'+esc(m.date||'—')+'</td>'+
      '<td><div class="cov"><b>'+m.evals+'</b> 项 · <b>'+m.coverage+'</b>% 覆盖</div></td>'+
      '<td class="num">'+money(m.cache)+'</td>'+
      '<td class="num">'+money(m.input)+'</td>'+
      '<td class="num">'+money(m.output)+'</td>'+
      '<td><span class="score">'+(m.score==null?'—':Number(m.score).toFixed(1))+'</span><span class="score-bar"><i style="width:'+pct+'%"></i></span></td>'+
    '</tr>';
  }).join('');
}
lbCards();
bindSearch('q','qClear',lbRender);
document.getElementById('filters').addEventListener('click',e=>{
  const c=e.target.closest('.chip'); if(!c) return;
  document.querySelectorAll('#filters .chip').forEach(x=>x.classList.remove('on'));
  c.classList.add('on'); lbRender();
});
bindSort('#lbTbl', LB_SORT, lbRender);
lbRender();'''


# ---------------------------------------------------------------- 重置监控
RS_BODY = r'''  <div class="notice-card" id="notice"></div>
  <div class="cards" id="cards"></div>

  <div class="fb-group"><h3>本月重置日历</h3><span class="gcount" id="evCount"></span></div>
  <div class="timeline" id="events"></div>

  <div class="fb-group"><h3>历史重置记录</h3><span class="gcount" id="histCount"></span></div>
  <div id="history"></div>
  <div style="margin-top:14px"><button class="chip" id="moreHist" style="cursor:pointer">展开全部记录</button></div>
  <div class="src-line">每个日期对应 AIHOT 收录的原帖与事件明细，点日期可跳转查看。统计口径为近 90 天。</div>'''

RS_JS = r'''const RS = D.resets || {};
const N = RS.notice || {};
const EV = (RS.events||[]).slice().sort((a,b)=>b.date.localeCompare(a.date));
const HIST = (RS.history||[]).slice();
document.getElementById('notice').innerHTML =
  '<h2>◷ '+esc(N.title||'额度重置监控')+' <span class="win">预计 '+esc(N.window||'以官方公告为准')+'</span></h2>'+
  (N.quote?'<blockquote>“'+esc(N.quote)+'”</blockquote>':'')+
  '<p>'+esc(N.note||'')+'</p>'+
  '<p>盯着 OpenAI 的 Tibo 与 Andrew 公布的 Codex 额度重置和重置卡发放：什么时候生效、谁能用上、原话怎么说。</p>';
const S = RS.stats || {};
const statKeys=['近 90 天额度重置','近 90 天发重置卡','重置间隔中位数','上次额度重置'];
document.getElementById('cards').innerHTML = statKeys.map(k=>
  '<div class="card"><div class="k">'+esc(k)+'</div><div class="v">'+esc(S[k]||'—')+'</div></div>').join('');
document.getElementById('evCount').textContent = EV.length+' 条';
const typePill = t => t==='待生效' ? '<span class="pill promo">待生效</span>'
  : t==='发重置卡' ? '<span class="pill free">发重置卡</span>'
  : '<span class="pill paid">额度重置</span>';
document.getElementById('events').innerHTML = EV.length ? EV.map(e=>
  '<div class="tl-item'+(e.types.indexOf('待生效')>=0?' pending':'')+'">'+
    '<span class="tl-date">'+esc(e.date)+'</span>'+
    '<span>'+e.types.map(typePill).join(' ')+'</span>'+
    '<a class="btn-connect" style="margin-left:auto;text-decoration:none" href="'+esc(e.url)+'" target="_blank" rel="noopener">看原帖 ↗</a>'+
  '</div>').join('') : '<div class="empty">本月暂无记录</div>';
document.getElementById('histCount').textContent = HIST.length+' 天';
let expanded=false;
function renderHist(){
  const list = expanded ? HIST : HIST.slice(0,30);
  const groups={};
  list.forEach(h=>{ const m=h.date.slice(0,7); (groups[m]=groups[m]||[]).push(h); });
  document.getElementById('history').innerHTML = Object.keys(groups).sort().reverse().map(m=>
    '<div class="hist-month">'+esc(m)+' · '+groups[m].length+' 天</div>'+
    '<div class="hist-grid">'+groups[m].map(h=>
      '<a href="'+esc(h.url)+'" target="_blank" rel="noopener">'+esc(h.date.slice(5))+'</a>').join('')+'</div>').join('')
    || '<div class="empty">暂无历史记录</div>';
  document.getElementById('moreHist').textContent = expanded ? '收起' : ('展开全部 '+HIST.length+' 条');
  document.getElementById('moreHist').style.display = HIST.length>30 ? '' : 'none';
}
document.getElementById('moreHist').addEventListener('click',()=>{ expanded=!expanded; renderHist(); });
renderHist();'''


# ---------------------------------------------------------------- Token 羊毛
FT_BODY = r'''  <div class="cards" id="cards"></div>
  <div class="toolbar">
    <div class="search-wrap"><input class="search" id="q" type="text" placeholder="搜索厂商 / 额度 / 条件…"><button class="search-clear" id="qClear" type="button" aria-label="清空搜索">×</button></div>
    <div class="filters" id="filters">
      <span class="chip on" data-f="all">全部</span>
      <span class="chip" data-f="daily">每天可领</span>
      <span class="chip" data-f="monthly">每月可领</span>
      <span class="chip" data-f="new">新人礼包</span>
      <span class="chip" data-f="api">可直调 API</span>
      <span class="chip" data-f="soon">即将截止</span>
      <span class="chip" data-f="valid">仅看有效</span>
    </div>
    <span class="result-count" id="cnt"></span>
  </div>
  <div id="list"></div>'''

FT_JS = r'''const FB = D.freebies || [];
const GROUPS = {daily:'每天都能领',monthly:'每月都能领',new:'新人 / 一次性礼包',api:'限时免费 · 可直调 API'};
const days = dl => dl ? (new Date(dl+'T23:59:59+08:00')-Date.now())/86400000 : null;
const expired = x => { const d=days(x.dl); return d!=null && d<0; };
const soon = x => { const d=days(x.dl); return d!=null && d>=0 && d<30; };
function fbPill(dl){
  const d=days(dl);
  if(d==null) return '';
  if(d<0) return '<span class="pill na">已截止</span>';
  return '<span class="pill '+(d<30?'exp':'paid')+'">'+(d<1?'今天截止':'剩 '+Math.ceil(d)+' 天')+'</span>';
}
function ftCards(){
  const n=c=>FB.filter(x=>x.c===c).length;
  document.getElementById('cards').innerHTML=
    '<div class="card"><div class="k">收录额度</div><div class="v">'+FB.length+' <small>条</small></div></div>'+
    '<div class="card"><div class="k">每天可领</div><div class="v">'+n('daily')+' <small>项</small></div></div>'+
    '<div class="card"><div class="k">每月可领</div><div class="v">'+n('monthly')+' <small>项</small></div></div>'+
    '<div class="card"><div class="k">即将截止</div><div class="v">'+FB.filter(soon).length+' <small>条</small></div></div>';
}
function ftRender(){
  const q=(document.getElementById('q').value||'').trim().toLowerCase();
  const f=document.querySelector('#filters .chip.on').dataset.f;
  let html='', shown=0;
  ['daily','monthly','new','api'].forEach(g=>{
    const list=FB.filter(x=>{
      if(x.c!==g) return false;
      if(f==='valid' && expired(x)) return false;
      if(f==='soon' && !soon(x)) return false;
      if(f!=='all'&&f!=='valid'&&f!=='soon'&&f!==g) return false;
      return !q || ((x.t||'')+' '+(x.n||'')+' '+(x.a||'')+' '+(x.conds||[]).join(' ')).toLowerCase().includes(q);
    });
    if(!list.length) return;
    shown+=list.length;
    html+='<div class="fb-group"><h3>'+GROUPS[g]+'</h3><span class="gcount">'+list.length+' 条</span></div>';
    html+=list.map(x=>{
      const dead=expired(x);
      return '<div class="fb-row'+(dead?' is-expired':'')+'"><div class="fb-main">'+
        '<div class="fb-name">'+esc(x.t)+'<small>'+esc(x.n||'')+'</small></div>'+
        '<div class="fb-conds">'+(x.conds||[]).map(c=>'<span class="tag">'+esc(c)+'</span>').join('')+'</div>'+
        '<div class="fb-src">'+esc(D.verified||'')+' 核实 · <a href="'+esc(x.u)+'" target="_blank" rel="noopener">官方页面 ↗</a></div></div>'+
        '<div class="fb-right">'+fbPill(x.dl)+'<span class="fb-amt">'+esc(x.a)+'</span>'+
        (dead?'<button class="btn-connect" disabled>已结束</button>':'<a class="btn-connect" href="'+esc(x.u)+'" target="_blank" rel="noopener" style="text-decoration:none">去领</a>')+
        '</div></div>';
    }).join('');
  });
  if(!html) html='<div class="empty">没有匹配的额度</div>';
  document.getElementById('list').innerHTML=html;
  document.getElementById('cnt').textContent = shown===FB.length ? '共 '+shown+' 条额度' : '匹配 '+shown+' / '+FB.length;
}
ftCards();
bindSearch('q','qClear',ftRender);
document.getElementById('filters').addEventListener('click',e=>{
  const c=e.target.closest('.chip'); if(!c) return;
  document.querySelectorAll('#filters .chip').forEach(x=>x.classList.remove('on'));
  c.classList.add('on'); ftRender();
});
ftRender();'''


# ---------------------------------------------------------------- 工作台入口
HUB_CSS = r'''
/* ===== 下级页面入口 ===== */
.hub-links{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:18px;padding:12px 14px;
  background:var(--card);border:1px solid var(--border);border-radius:12px;box-shadow:var(--shadow)}
.hub-label{font-size:12px;color:var(--muted);font-weight:600;margin-right:2px}
.hub-links a{display:inline-flex;align-items:center;gap:6px;padding:6px 13px;border-radius:999px;font-size:12.5px;font-weight:600;
  text-decoration:none;color:var(--text);background:rgba(255,255,255,.04);border:1px solid var(--border);transition:.18s}
.hub-links a:hover{border-color:var(--brand);color:var(--brand);transform:translateY(-1px)}
.hub-links a .ico{opacity:.8}
@media(max-width:700px){.hub-links{padding:10px}.hub-label{width:100%}}
'''
HUB_HTML = '''  <div class="hub-links">
    <span class="hub-label">下级页面</span>
    <a href="leaderboard.html"><span class="ico">▤</span>AI 模型榜</a>
    <a href="resets.html"><span class="ico">◷</span>额度重置监控</a>
    <a href="free-tokens.html"><span class="ico">◎</span>Token 羊毛全集</a>
  </div>
'''


def inject_hub():
    t = PAGE.read_text(encoding="utf-8")
    changed = False
    if 'class="hub-links"' not in t:
        anchor = '  <div class="src-tabs">'
        assert t.count(anchor) == 1, "找不到 src-tabs 锚点"
        t = t.replace(anchor, HUB_HTML + anchor, 1)
        changed = True
    if '.hub-links{' not in t:
        t = t.replace('</style>', HUB_CSS + '</style>', 1)
        changed = True
    # 免费额度视图里补一个「完整清单」入口
    old = '整理自 <a class="klink" href="https://aihot.news/free-tokens" target="_blank" rel="noopener">aihot.news · Token 羊毛</a>，'
    new = ('整理自 <a class="klink" href="https://aihot.news/free-tokens" target="_blank" rel="noopener">aihot.news · Token 羊毛</a>，'
           '<a class="klink" href="free-tokens.html">查看完整清单页 →</a>；')
    if old in t and '查看完整清单页' not in t:
        t = t.replace(old, new, 1)
        changed = True
    if changed:
        PAGE.write_text(t, encoding="utf-8")
    return changed


def main():
    pages = [
        dict(file="leaderboard.html", title="AI 模型榜", h1="AI 模型榜",
             sub="第三方实测评分 · 30 个模型 · 价格与评测覆盖一屏看清",
             source_url="https://aihot.news/leaderboard", source_label="aihot.news · 模型榜",
             page_key="leaderboard", body=LB_BODY, js=LB_JS,
             note_extra="评分口径：只用第三方评测机构实测成绩，按编程 38% / 科研 19% / 专业办公 19% / 知识问答 14% / 真人盲选 10% 加权；分差不到 3 分时换一组评测可能换位。"),
        dict(file="resets.html", title="额度重置监控", h1="额度重置监控",
             sub="Codex 额度重置与重置卡发放 · 下次生效时间 · 90 天历史",
             source_url="https://aihot.news/resets", source_label="aihot.news · 重置监控",
             page_key="resets", body=RS_BODY, js=RS_JS,
             note_extra="预告时段为模型推算，非官方承诺。"),
        dict(file="free-tokens.html", title="Token 羊毛全集", h1="Token 羊毛 · 免费额度全集",
             sub="厂商官方免费额度 · 每天 / 每月 / 新人 / 可直调 API",
             source_url="https://aihot.news/free-tokens", source_label="aihot.news · Token 羊毛",
             page_key="free-tokens", body=FT_BODY, js=FT_JS,
             note_extra="只收厂商官方活动，不收返利、中转站、二手积分。"),
    ]
    for p in pages:
        cfg = {k: v for k, v in p.items() if k != "file"}
        (MODELS / p["file"]).write_text(render(**cfg), encoding="utf-8")
        print("  生成", p["file"])
    print("  工作台入口", "已注入" if inject_hub() else "已是最新")
    print("完成。数据快照由 build.py 生成，页面模板由本脚本生成。")


if __name__ == "__main__":
    main()
