# -*- coding: utf-8 -*-
"""HTML 交互式报告生成器。

生成单个离线 HTML 文件：树形目录浏览、搜索筛选、表头排序、
勾选收集、操作清单导出（JSON/CSV）。网页本身不做任何文件操作。
"""
from __future__ import annotations

import datetime
import json
import os
from typing import List

from .model import CATEGORY_LABEL, RISK_EMOJI, RISK_LABEL, FileEntry, ScanResult


def fmt_size(n: int) -> str:
    if n is None:
        return "-"
    try:
        n = int(n)
    except Exception:
        return "-"
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    if n < 1024 ** 3:
        return f"{n / (1024 ** 2):.1f} MB"
    return f"{n / (1024 ** 3):.2f} GB"


def fmt_time(t: float) -> str:
    if not t:
        return "-"
    try:
        return datetime.datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "-"


def generate_html(result: ScanResult, cfg, out_path: str) -> str:
    """生成 HTML 报告并写入 out_path，返回路径。"""
    stats = result.stats
    meta = {
        "title": "磁盘文件检视报告",
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "深度全盘扫描" if result.mode == "deep" else "极速扫描",
        "roots": result.roots,
        "threshold": cfg.large_threshold_mb,
        "elapsed": f"{result.elapsed:.1f} 秒",
        "total_files": stats.get("files", 0),
        "total_dirs": stats.get("dirs", 0),
        "total_size": stats.get("size", 0),
        "large": stats.get("large", 0),
        "junk": stats.get("junk", 0),
        "locked": stats.get("locked", 0),
        "duplicates": stats.get("duplicates", 0),
        "by_risk": stats.get("by_risk", {}),
        "by_category": stats.get("by_category", {}),
    }
    # 流式生成：先写不含 entries 的前部，再分块序列化 entries 数组，
    # 避免一次性构造数百万条目的大 dict + 大 JSON 字符串（内存峰值可差数 GB）。
    head, tail = TEMPLATE.split("__DATA_PRE_JSON__", 1)
    mid, tail = tail.split("__DATA_ENTRIES_JSON__", 1)
    d = os.path.dirname(out_path)
    if d:
        os.makedirs(d, exist_ok=True)
    pre = {
        "meta": meta,
        "cat_label": CATEGORY_LABEL,
        "risk_label": RISK_LABEL,
        "risk_emoji": RISK_EMOJI,
    }
    pre_json = json.dumps(pre, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")
    entries = [e.to_dict() for e in result.entries]
    CHUNK = 5000
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(head)
        f.write(pre_json)
        f.write(mid)
        f.write("[")
        for i in range(0, len(entries), CHUNK):
            chunk = json.dumps(entries[i:i + CHUNK], ensure_ascii=False)
            chunk = chunk.replace("</", "<\\/").replace("<!--", "<\\!--")
            if i:
                f.write(",\n")
            f.write(chunk[1:-1])
        f.write("];")
        f.write(tail)
    return out_path


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>磁盘文件检视报告</title>
<style>
:root{--blue:#2D7FF9;--blue-l:#E8F1FE;--red:#E5484D;--red-l:#FDECEC;--orange:#F5A524;--orange-l:#FEF6E7;--green:#30A46C;--green-l:#E9F8F0;--gray:#8B949E;--gray-l:#F6F7F9;--ink:#1F2328;--line:#E4E8EE;--card:#FFFFFF;--bg:#F3F6FB;--shadow:0 1px 3px rgba(16,24,40,.08);}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:"Microsoft YaHei","PingFang SC",sans-serif;background:var(--bg);color:var(--ink);font-size:13px}
.wrap{max-width:1700px;margin:0 auto;padding:16px}
/* 头部 */
header{background:linear-gradient(135deg,#2D7FF9,#1B5FD9);color:#fff;border-radius:14px;padding:20px 24px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;box-shadow:var(--shadow)}
header h1{font-size:22px;font-weight:700}
header .sub{opacity:.9;font-size:12px;margin-top:4px}
header .meta{text-align:right;font-size:12px;opacity:.95;line-height:1.7}
/* 统计卡片 */
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:14px 0}
.card{background:var(--card);border-radius:12px;padding:14px 16px;box-shadow:var(--shadow);border:1px solid var(--line)}
.card .num{font-size:24px;font-weight:700;color:var(--blue)}
.card .lbl{color:var(--gray);font-size:12px;margin-top:2px}
.card.warn .num{color:var(--red)}
.card.good .num{color:var(--green)}
.card.org .num{color:var(--orange)}
/* 图表区 */
.dash{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px}
.chart-card{background:var(--card);border-radius:12px;padding:14px 16px;box-shadow:var(--shadow);border:1px solid var(--line)}
.chart-card h3{font-size:14px;margin-bottom:8px}
.chart-flex{display:flex;align-items:center;gap:16px}
.legend{font-size:12px;line-height:1.9;flex:1}
.legend .dot{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px}
@media(max-width:900px){.dash{grid-template-columns:1fr}}
/* 工具栏 */
.toolbar{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 14px;display:flex;gap:8px;flex-wrap:wrap;align-items:center;box-shadow:var(--shadow);position:sticky;top:8px;z-index:20}
.toolbar input[type=text]{padding:7px 10px;border:1px solid var(--line);border-radius:8px;width:220px;font-size:13px;outline:none}
.toolbar input[type=text]:focus{border-color:var(--blue)}
.toolbar select{padding:7px 8px;border:1px solid var(--line);border-radius:8px;font-size:13px;background:#fff}
.tbtn{padding:7px 12px;border-radius:8px;border:1px solid var(--line);background:#fff;cursor:pointer;font-size:13px;color:var(--ink)}
.tbtn:hover{border-color:var(--blue);color:var(--blue)}
.tbtn.primary{background:var(--blue);border-color:var(--blue);color:#fff}
.tbtn.primary:hover{background:#1B6FE0}
.tbtn.danger{background:var(--red);border-color:var(--red);color:#fff}
.tbtn.danger:hover{background:#D13438}
.selinfo{margin-left:auto;font-size:13px;color:var(--gray);white-space:nowrap}
.selinfo b{color:var(--blue)}
/* 表格 */
.table-wrap{background:var(--card);border:1px solid var(--line);border-radius:12px;margin-top:12px;box-shadow:var(--shadow);overflow:auto;max-height:62vh}
table{border-collapse:collapse;width:100%;min-width:1500px;font-size:12.5px}
thead th{position:sticky;top:0;background:#F0F4FA;z-index:5;padding:9px 10px;text-align:left;border-bottom:1px solid var(--line);cursor:pointer;user-select:none;white-space:nowrap}
thead th:hover{color:var(--blue)}
thead th .arr{font-size:10px;color:var(--blue)}
tbody td{padding:6px 10px;border-bottom:1px solid #F0F2F5;vertical-align:top;white-space:nowrap}
tbody tr:hover{background:#F7FAFF}
tr.high td{background:var(--red-l)}
tr.med td{background:var(--orange-l)}
tr.low td{background:var(--green-l)}
tr.locked td{opacity:.85}
td.name-cell{padding-left:0}
.name-ico{display:inline-block;width:16px;text-align:center;margin-right:4px}
.tw{display:inline-block;transition:transform .12s}
.tw.open{transform:rotate(90deg)}
.name-text{font-weight:500}
.lock-tag{color:var(--red);font-size:11px;margin-left:4px}
.occ-tag{color:var(--gray);font-size:11px;margin-left:4px}
/* 徽章 */
.badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11.5px;white-space:nowrap}
.b-high{background:var(--red-l);color:var(--red);font-weight:600}
.b-med{background:var(--orange-l);color:#B45309;font-weight:600}
.b-low{background:var(--green-l);color:var(--green);font-weight:600}
.b-norm{background:var(--gray-l);color:#57606A}
.cat{font-size:11.5px;color:#57606A}
.advice{white-space:pre-line;max-width:340px;color:#424A53;line-height:1.5}
.sz{font-variant-numeric:tabular-nums}
.lg-tag{color:var(--orange);font-weight:600}
.dup-tag{color:#8E4EC6}
/* 底部操作面板 */
.action-bar{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin-top:12px;box-shadow:var(--shadow);display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.action-bar .sum{font-size:13px}
.action-bar .sum b{color:var(--blue)}
.action-bar .hint{font-size:11.5px;color:var(--gray);flex-basis:100%}
footer{color:var(--gray);font-size:11.5px;text-align:center;padding:18px 0 8px;line-height:1.8}
input[type=checkbox]{width:15px;height:15px;accent-color:var(--blue);cursor:pointer}
input[type=checkbox]:disabled{cursor:not-allowed}
.note{background:var(--orange-l);color:#B45309;border-radius:8px;padding:6px 10px;font-size:12px;margin-top:8px;display:none}
</style>
</head>
<body>
<div class="wrap">
<header>
  <div>
    <h1>📋 磁盘文件检视报告</h1>
    <div class="sub" id="subline">生成时间：<span id="genTime"></span></div>
  </div>
  <div class="meta" id="metaLine"></div>
</header>

<div class="cards" id="cards"></div>

<div class="dash">
  <div class="chart-card"><h3>风险等级分布（按数量）</h3><div class="chart-flex"><div id="donutRisk"></div><div class="legend" id="legRisk"></div></div></div>
  <div class="chart-card"><h3>文件大类分布（按数量）</h3><div class="chart-flex"><div id="donutCat"></div><div class="legend" id="legCat"></div></div></div>
</div>

<div class="toolbar">
  <input type="text" id="search" placeholder="🔍 搜索名称 / 路径 / 用途…">
  <select id="fRisk"><option value="">风险：全部</option></select>
  <select id="fCat"><option value="">大类：全部</option></select>
  <select id="fSize"><option value="">大小：全部</option><option value="large">仅大型文件</option><option value="junk">仅可清理项</option><option value="residue">仅卸载残留</option><option value="dup">仅重复文件</option></select>
  <button class="tbtn" id="btnExpandAll">展开全部</button>
  <button class="tbtn" id="btnCollapseAll">折叠全部</button>
  <button class="tbtn" id="btnSelAll">全选可操作</button>
  <button class="tbtn" id="btnSelInv">反选</button>
  <button class="tbtn" id="btnSelClear">清空</button>
  <span class="selinfo">已选 <b id="selCount">0</b> 项 · <b id="selSize">0 B</b></span>
</div>
<div class="note" id="truncNote"></div>

<div class="table-wrap">
<table id="grid">
  <thead><tr>
    <th style="width:34px"></th>
    <th data-k="n">名称<span class="arr"></span></th>
    <th data-k="t">类型</th>
    <th data-k="pu">用途</th>
    <th data-k="rq">必需</th>
    <th data-k="cd">可删</th>
    <th data-k="cm">可迁移</th>
    <th data-k="rs">残留</th>
    <th data-k="lg">大文件</th>
    <th data-k="c">创建时间</th>
    <th data-k="s">大小</th>
    <th data-k="g">大类</th>
    <th data-k="r">风险</th>
    <th data-k="av">处理建议</th>
  </tr></thead>
  <tbody id="tbody"></tbody>
</table>
</div>

<div class="action-bar">
  <div class="sum">勾选 <b id="actCount">0</b> 项，合计 <b id="actSize">0 B</b></div>
  <button class="tbtn primary" id="btnExport">📤 导出勾选清单（执行操作用）</button>
  <button class="tbtn" id="btnExportCsv">导出 CSV</button>
  <div class="hint">⚠️ 浏览器出于安全限制无法直接操作你的文件。请点击「导出勾选清单」，得到 JSON 清单后，打开【磁盘文件检视工具】→「批量操作」→「导入勾选清单」，即可仅对你勾选的条目执行 安全删除 / 备份 / 迁移。系统高危文件已锁定，无法勾选。</div>
</div>
<footer>本报告为离线文件，不联网、不上传任何数据。所有操作以工具内二次确认为准。</footer>
</div>

<script>
window.onerror=function(msg,src,line){var d=document.createElement("div");d.style.cssText="position:fixed;bottom:0;left:0;background:#E5484D;color:#fff;z-index:99999;padding:10px;font-size:13px;max-width:100%";d.textContent="页面脚本错误: "+msg+" @第"+line+"行";document.body.appendChild(d);};
var DATA = __DATA_PRE_JSON__;
DATA.entries = __DATA_ENTRIES_JSON__;
var E = DATA.entries, M = DATA.meta;
var catLabel = DATA.cat_label, riskLabel = DATA.risk_label, riskEmoji = DATA.risk_emoji;
var checked = new Set();
var expanded = new Set();
var sortKey = "n", sortDir = 1;
var MAXROWS = 30000;

// ---------- 工具 ----------
function esc(s){ return String(s==null?"":s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }
function fmtSize(n){ if(n==null) return "-"; n=Number(n); if(n<1024) return n+" B"; if(n<1048576) return (n/1024).toFixed(1)+" KB"; if(n<1073741824) return (n/1048576).toFixed(1)+" MB"; return (n/1073741824).toFixed(2)+" GB"; }
function fmtTime(t){ if(!t) return "-"; var d=new Date(t*1000); function p(x){return (x<10?"0":"")+x;} return d.getFullYear()+"-"+p(d.getMonth()+1)+"-"+p(d.getDate())+" "+p(d.getHours())+":"+p(d.getMinutes()); }
function riskClass(r){ return r>=3?"b-high":r==2?"b-med":r==1?"b-low":"b-norm"; }
function rowClass(r,locked){ if(locked) return "locked"; return r>=3?"high":r==2?"med":r==1?"low":""; }

// ---------- 树索引 ----------
var byPath = {}, children = {};
E.forEach(function(e,i){ byPath[e.p]=i; var pr=e.p.lastIndexOf("\\"); var par = pr>1? e.p.slice(0,pr) : (e.p[1]===":"?e.p.slice(0,2)+"\\" : ""); if(par==="") par=e.p.slice(0,2)+"\\"; (children[par]=children[par]||[]).push(i); });
M.roots.forEach(function(r){ r=r.replace(/\\+$/,""); if(!children[r]) children[r]=[]; });
var roots = M.roots.map(function(r){ return r.replace(/\\+$/,""); });
Object.keys(children).forEach(function(k){ children[k].sort(function(a,b){ var A=E[a],B=E[b]; if(A.d!==B.d) return A.d?-1:1; return A.n.toLowerCase()<B.n.toLowerCase()?-1:1; }); });

// ---------- 过滤 ----------
function matches(e){
  var q = (document.getElementById("search").value||"").trim().toLowerCase();
  if(q && (e.n.toLowerCase().indexOf(q)<0) && (e.p.toLowerCase().indexOf(q)<0) && (e.pu||"").toLowerCase().indexOf(q)<0) return false;
  var fr=document.getElementById("fRisk").value, fc=document.getElementById("fCat").value, fs=document.getElementById("fSize").value;
  if(fr && e.r!==Number(fr)) return false;
  if(fc && e.g!==fc) return false;
  if(fs==="large" && !e.lg) return false;
  if(fs==="junk" && !(e.g==="temp"||e.rs||e.cd==="safe")) return false;
  if(fs==="residue" && !e.rs) return false;
  if(fs==="dup" && !e.dp) return false;
  return true;
}

// ---------- 渲染 ----------
var tbody = document.getElementById("tbody");
function render(){
  tbody.innerHTML="";
  var q=(document.getElementById("search").value||"").trim().toLowerCase();
  var html=[], count=0, truncated=false;
  function subHas(p){ // 子树是否存在过滤匹配项
    var st=[p], seen={};
    while(st.length){
      var cur=st.pop(); if(seen[cur]) continue; seen[cur]=1;
      var kk=children[cur]||[];
      for(var j=0;j<kk.length;j++){
        var e=E[kk[j]];
        if(matches(e)) return true;
        if(e.d) st.push(e.p);
      }
    }
    return false;
  }
  function walk(nodePath, depth){
    var kids=children[nodePath]||[];
    for(var i=0;i<kids.length;i++){
      if(count>=MAXROWS){truncated=true;break;}
      var e=E[kids[i]];
      var selfOk=matches(e);
      var show = selfOk || (e.d && subHas(e.p)); // 目录：自身或子项匹配则显示
      if(!show) continue;
      var isOpen=expanded.has(e.p)||(q!=="");
      var indent = depth*18;
      var ico = e.d ? (isOpen?"📂":"📁") : (extIco(e.n));
      var lock = e.lk?"<span class='lock-tag'>🔒已锁定</span>":"";
      var occ = e.oc?"<span class='occ-tag'>占用中</span>":"";
      var cb = e.lk||e.oc
        ? "<input type='checkbox' disabled title='锁定/占用，禁止操作'>"
        : "<input type='checkbox' data-idx='"+kids[i]+"' "+(checked.has(e.p)?"checked":"")+">";
      html.push("<tr class='"+rowClass(e.r,e.lk)+"' data-path='"+esc(e.p)+"'>"
        +"<td>"+cb+"</td>"
        +"<td class='name-cell'><span style='display:inline-block;width:"+indent+"px'></span>"
        + (e.d?"<span class='tw "+(isOpen?"open":"")+"' data-path='"+esc(e.p)+"' style='cursor:pointer'>▶</span>":"")
        + "<span class='name-ico'>"+ico+"</span><span class='name-text'>"+esc(e.n)+"</span>"+lock+occ+"</td>"
        +"<td>"+esc(e.d?"文件夹":(e.t?e.t.slice(1).toUpperCase():"-"))+"</td>"
        +"<td>"+esc(e.pu||"-")+"</td>"
        +"<td>"+(e.rq==="yes"?"是":e.rq==="no"?"否":"不确定")+"</td>"
        +"<td>"+(e.cd==="safe"?"可删":e.cd==="forbidden"?"<span style='color:var(--red);font-weight:600'>禁止</span>":"谨慎")+"</td>"
        +"<td>"+(e.cm?"可迁移":"<span style='color:var(--gray)'>不可迁移</span>")+"</td>"
        +"<td>"+(e.rs?"<span class='badge b-low'>残留</span>":"否")+"</td>"
        +"<td>"+(e.lg?"<span class='lg-tag'>是</span>":"否")+(e.dp?"<span class='dup-tag'> 重复</span>":"")+"</td>"
        +"<td>"+fmtTime(e.c)+"</td>"
        +"<td class='sz'>"+fmtSize(e.s)+"</td>"
        +"<td><span class='cat'>"+(catLabel[e.g]||"其他")+"</span></td>"
        +"<td><span class='badge "+riskClass(e.r)+"'>"+riskEmoji[e.r]+" "+riskLabel[e.r]+"</span></td>"
        +"<td class='advice'>"+esc(e.av||"-")+"</td>"
        +"</tr>");
      count++;
      if(e.d && isOpen){ walk(e.p, depth+1); }
    }
  }
  roots.forEach(function(r){ walk(r,0); });
  tbody.innerHTML=html.join("");
  document.getElementById("truncNote").style.display = truncated?"block":"none";
  if(truncated) document.getElementById("truncNote").textContent="⚠️ 数据量较大，仅显示前 "+MAXROWS+" 条。请使用搜索/筛选缩小范围。";
  bindChecks();
}
function extIco(name){
  var ext=name.split(".").pop().toLowerCase();
  var m={jpg:"🖼️",jpeg:"🖼️",png:"🖼️",gif:"🖼️",bmp:"🖼️",webp:"🖼️",mp4:"🎬",mkv:"🎬",avi:"🎬",mov:"🎬",mp3:"🎵",wav:"🎵",flac:"🎵",doc:"📄",docx:"📄",pdf:"📄",txt:"📄",md:"📄",xls:"📊",xlsx:"📊",ppt:"📽️",pptx:"📽️",zip:"🗜️",rar:"🗜️","7z":"🗜️",exe:"⚙️",msi:"📦",dll:"🧩",log:"📃",tmp:"🗑️",iso:"💿"};
  return m[ext]||"📄";
}
function bindChecks(){
  tbody.querySelectorAll("input[type=checkbox]").forEach(function(c){
    c.addEventListener("change",function(){ var i=c.getAttribute("data-idx"); var e=E[i]; if(c.checked) checked.add(e.p); else checked.delete(e.p); updateSel(); });
  });
}
// 展开/折叠
tbody.addEventListener("click",function(ev){
  var t=ev.target;
  if(t.classList&&t.classList.contains("tw")){
    var p=t.getAttribute("data-path");
    if(expanded.has(p)) expanded.delete(p); else expanded.add(p);
    render(); return;
  }
});

// ---------- 排序 ----------
document.querySelectorAll("thead th[data-k]").forEach(function(th){
  th.addEventListener("click",function(){
    var k=th.getAttribute("data-k");
    if(sortKey===k) sortDir*=-1; else {sortKey=k; sortDir=1;}
    sortTree(roots, k, sortDir);
    document.querySelectorAll("thead th .arr").forEach(function(a){a.textContent="";});
    th.querySelector(".arr").textContent=sortDir>0?" ▲":" ▼";
    render();
  });
});
function sortTree(nodes,k,dir){
  nodes.forEach(function(nodePath){
    var kids=children[nodePath]; if(!kids) return;
    kids.sort(function(a,b){
      var A=E[a],B=E[b];
      if(A.d!==B.d) return A.d?-1:1;
      var va=val(A,k), vb=val(B,k);
      if(typeof va==="number"&&typeof vb==="number") return (va-vb)*dir;
      return String(va).localeCompare(String(vb),"zh-Hans-CN")*dir;
    });
    kids.forEach(function(i){ if(E[i].d) sortTree([E[i].p],k,dir); });
  });
}
function val(e,k){
  switch(k){
    case "n": return e.n.toLowerCase();
    case "t": return e.d?"":(e.t||"");
    case "pu": return e.pu||"";
    case "rq": return e.rq==="yes"?1:e.rq==="no"?0:2;
    case "cd": return e.cd==="safe"?0:e.cd==="caution"?1:2;
    case "cm": return e.cm?1:0;
    case "rs": return e.rs?1:0;
    case "lg": return e.lg?1:0;
    case "c": return e.c||0;
    case "s": return e.s||0;
    case "g": return e.g||"";
    case "r": return e.r;
    case "av": return e.av||"";
  }
  return "";
}

// ---------- 勾选 ----------
function updateSel(){
  var n=0,s=0;
  checked.forEach(function(p){ var e=byPath[p]; if(e){n++; s+=e.s;} });
  ["selCount","actCount"].forEach(function(id){document.getElementById(id).textContent=n;});
  ["selSize","actSize"].forEach(function(id){document.getElementById(id).textContent=fmtSize(s);});
}
document.getElementById("btnSelAll").onclick=function(){ E.forEach(function(e,i){ if(!e.lk&&!e.oc) checked.add(e.p); }); render(); updateSel(); };
document.getElementById("btnSelInv").onclick=function(){ var tmp=new Set(); E.forEach(function(e,i){ if(!e.lk&&!e.oc&&!checked.has(e.p)) tmp.add(e.p); }); checked=tmp; render(); updateSel(); };
document.getElementById("btnSelClear").onclick=function(){ checked=new Set(); render(); updateSel(); };
document.getElementById("btnExpandAll").onclick=function(){ E.forEach(function(e){ if(e.d) expanded.add(e.p); }); render(); };
document.getElementById("btnCollapseAll").onclick=function(){ expanded=new Set(); render(); };

// ---------- 导出 ----------
function download(name, content, type){
  var blob=new Blob([content],{type:type||"application/octet-stream"});
  var a=document.createElement("a"); a.href=URL.createObjectURL(blob); a.download=name;
  document.body.appendChild(a); a.click(); setTimeout(function(){URL.revokeObjectURL(a.href);},500);
}
document.getElementById("btnExport").onclick=function(){
  var items=[]; checked.forEach(function(p){ var e=byPath[p]; if(e) items.push({path:e.p,size:e.s,is_dir:e.d}); });
  items.sort(function(a,b){return a.path<b.path?-1:1;});
  if(!items.length){ alert("尚未勾选任何可操作的条目"); return; }
  var manifest={app:"磁盘文件检视工具",version:1,op_request:true,
    generated:new Date().toISOString().slice(0,19).replace("T"," "),
    scan:{mode:M.mode,roots:M.roots,generated:M.generated},
    count:items.length,total_size:items.reduce(function(s,i){return s+i.size;},0),
    items:items};
  var ts=new Date(); function p(x){return (x<10?"0":"")+x;}
  var fn="磁盘操作清单_"+ts.getFullYear()+p(ts.getMonth()+1)+p(ts.getDate())+"_"+p(ts.getHours())+p(ts.getMinutes())+p(ts.getSeconds())+".json";
  download(fn, JSON.stringify(manifest,null,1), "application/json");
  alert("勾选清单已导出："+fn+"\n\n下一步：打开【磁盘文件检视工具】→ 批量操作 → 导入勾选清单，即可对选中条目执行操作。");
};
document.getElementById("btnExportCsv").onclick=function(){
  var rows=[["路径","类型","大小(字节)","创建时间","大类","风险","用途","处理建议"]];
  checked.forEach(function(p){ var e=byPath[p]; if(!e)return; rows.push([e.p,e.d?"文件夹":(e.t||""),e.s,new Date((e.c||0)*1000).toLocaleString(),catLabel[e.g]||"",riskLabel[e.r]||"",e.pu||"",(e.av||"").replace(/\n/g," ")]); });
  var csv=rows.map(function(r){return r.map(function(c){return '"'+String(c).replace(/"/g,'""')+'"';}).join(",");}).join("\r\n");
  download("磁盘勾选清单.csv","\ufeff"+csv,"text/csv;charset=utf-8");
};

// ---------- 工具栏联动 ----------
["search","fRisk","fCat","fSize"].forEach(function(id){
  document.getElementById(id).addEventListener("input",function(){ render(); });
});

// ---------- 初始化 ----------
function donut(el, data){
  var total=data.reduce(function(s,d){return s+d.value;},0)||1;
  var R=40,C=2*Math.PI*R,off=0;
  var svg='<svg width="110" height="110" viewBox="0 0 110 110"><g transform="rotate(-90 55 55)">';
  data.forEach(function(d){
    var frac=d.value/total;
    svg+='<circle cx="55" cy="55" r="'+R+'" fill="none" stroke="'+d.color+'" stroke-width="18" stroke-dasharray="'+(frac*C)+' '+(C-frac*C)+'" stroke-dashoffset="'+(-off*C)+'"></circle>';
    off+=frac;
  });
  svg+='</g><text x="55" y="52" text-anchor="middle" font-size="15" font-weight="700">'+total+'</text><text x="55" y="68" text-anchor="middle" font-size="9" fill="#8B949E">项</text></svg>';
  document.getElementById(el).innerHTML=svg;
  return data;
}
function legend(el, data){
  document.getElementById(el).innerHTML=data.map(function(d){return '<div><span class="dot" style="background:'+d.color+'"></span>'+esc(d.label)+' &nbsp; <b>'+d.value+'</b>（'+(100*d.value/(data.reduce(function(s,x){return s+x.value;},0)||1)).toFixed(1)+'%）</div>';}).join("");
}
(function init(){
  document.getElementById("genTime").textContent=M.generated;
  document.getElementById("metaLine").innerHTML=
    "扫描模式："+esc(M.mode)+"<br>范围："+esc(M.roots.join("、"))+"<br>耗时："+esc(M.elapsed)+"<br>大文件阈值："+M.threshold+" MB";
  var catColor={system:"#E5484D",app:"#F5A524",user:"#2D7FF9",temp:"#30A46C",empty:"#B7BEC9",other:"#8B949E"};
  var riskColor={3:"#E5484D",2:"#F5A524",1:"#30A46C",0:"#8B949E"};
  var byRisk=[3,2,1,0].map(function(r){return {label:riskLabel[r],value:M.by_risk[r]||0,color:riskColor[r]};}).filter(function(d){return d.value>0;});
  var byCat=Object.keys(M.by_category).map(function(k){return {label:catLabel[k]||k,value:M.by_category[k],color:catColor[k]||"#8B949E"};}).filter(function(d){return d.value>0;});
  donut("donutRisk",byRisk); legend("legRisk",byRisk);
  donut("donutCat",byCat); legend("legCat",byCat);
  var cards=document.getElementById("cards");
  cards.innerHTML=
    '<div class="card"><div class="num">'+M.total_files.toLocaleString()+'</div><div class="lbl">扫描文件数</div></div>'
    +'<div class="card"><div class="num">'+fmtSize(M.total_size)+'</div><div class="lbl">扫描总占用</div></div>'
    +'<div class="card org"><div class="num">'+M.large.toLocaleString()+'</div><div class="lbl">大型文件（≥'+M.threshold+'MB）</div></div>'
    +'<div class="card good"><div class="num">'+M.junk.toLocaleString()+'</div><div class="lbl">可清理项（临时/缓存/残留）</div></div>'
    +'<div class="card warn"><div class="num">'+M.locked.toLocaleString()+'</div><div class="lbl">已锁定保护的系统文件</div></div>'
    +(M.duplicates? '<div class="card"><div class="num">'+M.duplicates+'</div><div class="lbl">重复文件</div></div>':"");
  // 筛选下拉
  var riskSel=document.getElementById("fRisk");
  [3,2,1,0].forEach(function(r){ riskSel.insertAdjacentHTML("beforeend",'<option value="'+r+'">'+riskLabel[r]+'</option>'); });
  var catSel=document.getElementById("fCat");
  Object.keys(catLabel).forEach(function(k){ if(M.by_category[k]) catSel.insertAdjacentHTML("beforeend",'<option value="'+k+'">'+catLabel[k]+'</option>'); });
  render();
})();
</script>
</body>
</html>
"""
