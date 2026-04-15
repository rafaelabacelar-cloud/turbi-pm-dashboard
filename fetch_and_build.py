"""
Turbi PM Dashboard v2 — Gerador automático
Busca dados do Jira (CF + SF) e gera o index.html atualizado.
Roda via GitHub Actions todo dia de manhã.
"""

import os
import json
import base64
import urllib.request
from datetime import datetime, timezone, timedelta
from collections import defaultdict

# ── Config ───────────────────────────────────────────────────
JIRA_BASE  = "https://turbi-team.atlassian.net"
JIRA_EMAIL = os.environ["JIRA_EMAIL"]
JIRA_TOKEN = os.environ["JIRA_API_TOKEN"]

_creds  = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_TOKEN}".encode()).decode()
HEADERS = {
    "Authorization": f"Basic {_creds}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

PROJECTS = {
    "CF": {"name": "Core Financeiro",  "id": "10775"},
    "SF": {"name": "Tech Salesforce",  "id": "11209"},
}

FIELDS = "summary,status,assignee,priority,issuetype,project,created,updated"


# ── Jira fetcher ─────────────────────────────────────────────
def jira_search(jql: str, max_results: int = 100) -> list[dict]:
    url = f"{JIRA_BASE}/rest/api/3/search/jql"
    payload = json.dumps({
        "jql": jql,
        "maxResults": max_results,
        "fields": FIELDS.split(","),
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers=HEADERS, method="POST")
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
    return data.get("issues", [])


def compact(issue: dict) -> dict:
    f = issue.get("fields", {})
    proj = f.get("project", {})
    assignee = f.get("assignee")
    return {
        "key":          issue["key"],
        "summary":      f.get("summary", ""),
        "status":       f.get("status", {}).get("name", ""),
        "project_key":  proj.get("key", ""),
        "project_name": proj.get("name", ""),
        "assignee":     assignee.get("displayName", "Unassigned") if assignee else "Unassigned",
        "issuetype":    f.get("issuetype", {}).get("name", ""),
        "priority":     (f.get("priority") or {}).get("name", "Medium"),
        "created":      f.get("created", ""),
        "updated":      f.get("updated", ""),
    }


def fetch_all() -> list[dict]:
    issues = []
    for key, info in PROJECTS.items():
        print(f"  Buscando {key} ({info['name']})…")
        raw = jira_search(f"project = {info['id']} ORDER BY updated DESC", max_results=100)
        issues.extend([compact(i) for i in raw])
        print(f"    → {len(raw)} issues")
    return issues


# ── Timeline builder ──────────────────────────────────────────
def build_timeline(issues: list[dict], days: int = 30) -> dict:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    by_day: dict[str, list] = defaultdict(list)
    for i in issues:
        day = i["updated"][:10]
        if day >= cutoff:
            by_day[day].append({
                "key":         i["key"],
                "summary":     i["summary"],
                "status":      i["status"],
                "assignee":    i["assignee"],
                "project_key": i["project_key"],
                "issuetype":   i["issuetype"],
            })
    return dict(sorted(by_day.items(), reverse=True))


# ── HTML template ─────────────────────────────────────────────
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Turbi · PM Intelligence</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Instrument+Serif:ital@0;1&family=Manrope:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root {
  --bg: #0D0F14;
  --surface: #13161E;
  --surface2: #1A1E28;
  --surface3: #222736;
  --border: rgba(255,255,255,0.07);
  --border2: rgba(255,255,255,0.12);
  --text: #F0F2F7;
  --muted: #7A8299;
  --muted2: #4E5570;
  --accent: #4F7CFF;
  --accent2: #7B5EA7;
  --done: #22C87A;
  --warn: #F0A830;
  --danger: #F05252;
  --rev: #A78BFA;
  --cf: #4F7CFF;
  --sf: #7B5EA7;
  --font: 'Manrope', sans-serif;
  --mono: 'DM Mono', monospace;
  --serif: 'Instrument Serif', serif;
}
*{margin:0;padding:0;box-sizing:border-box}
html,body{height:100%;overflow:hidden}
body{font-family:var(--font);background:var(--bg);color:var(--text);font-size:13px}
.app{display:flex;height:100vh}

/* SIDEBAR */
.sidebar{width:228px;background:var(--surface);border-right:1px solid var(--border);display:flex;flex-direction:column;flex-shrink:0;overflow-y:auto}
.logo-area{padding:22px 20px 18px;border-bottom:1px solid var(--border)}
.logo-row{display:flex;align-items:center;gap:10px;margin-bottom:4px}
.logo-mark{width:30px;height:30px;background:linear-gradient(135deg,#4F7CFF,#7B5EA7);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:14px}
.logo-name{font-size:15px;font-weight:700;letter-spacing:-0.3px}
.logo-sub{font-size:10px;color:var(--muted);letter-spacing:0.5px;text-transform:uppercase;margin-left:40px}
.nav-section{padding:16px 12px 6px;font-size:9px;font-weight:700;color:var(--muted2);text-transform:uppercase;letter-spacing:1.2px}
.nav-item{display:flex;align-items:center;gap:9px;padding:8px 12px;border-radius:8px;cursor:pointer;font-size:12.5px;font-weight:500;color:var(--muted);transition:all .15s;margin:1px 8px;position:relative}
.nav-item:hover{background:var(--surface2);color:var(--text)}
.nav-item.active{background:rgba(79,124,255,0.12);color:var(--accent)}
.nav-item.active::before{content:'';position:absolute;left:0;top:50%;transform:translateY(-50%);width:3px;height:18px;background:var(--accent);border-radius:2px}
.nav-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.nav-badge{margin-left:auto;background:rgba(240,168,48,0.15);color:var(--warn);font-size:10px;font-weight:700;padding:1px 6px;border-radius:10px;font-family:var(--mono)}
.nav-badge.danger{background:rgba(240,82,82,0.15);color:var(--danger)}
.sidebar-footer{margin-top:auto;padding:14px 16px;border-top:1px solid var(--border);font-size:10px;color:var(--muted2);line-height:1.5}
.footer-pulse{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--done);margin-right:5px;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}

/* MAIN */
.main{flex:1;overflow:hidden;display:flex;flex-direction:column}
.topbar{background:var(--surface);border-bottom:1px solid var(--border);padding:0 24px;height:52px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0}
.topbar-left{display:flex;align-items:center;gap:16px}
.page-title{font-size:14px;font-weight:600;letter-spacing:-0.2px}
.topbar-right{display:flex;align-items:center;gap:10px}
.pill{font-size:10.5px;padding:4px 10px;border-radius:20px;font-weight:600;font-family:var(--mono)}
.pill-blue{background:rgba(79,124,255,0.12);color:var(--accent);border:1px solid rgba(79,124,255,0.2)}
.pill-gray{background:var(--surface2);color:var(--muted);border:1px solid var(--border)}
.pill-warn{background:rgba(240,168,48,0.1);color:var(--warn);border:1px solid rgba(240,168,48,0.2)}

.content{flex:1;overflow-y:auto;padding:22px 24px}

/* VIEWS */
.view{display:none}
.view.active{display:block}

/* KPI ROW */
.kpi-row{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:20px}
.kpi{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:14px 16px;position:relative;overflow:hidden}
.kpi::after{content:'';position:absolute;right:-10px;top:-10px;width:60px;height:60px;border-radius:50%;opacity:0.06}
.kpi.blue::after{background:var(--accent)}
.kpi.green::after{background:var(--done)}
.kpi.warn::after{background:var(--warn)}
.kpi.purple::after{background:var(--rev)}
.kpi.red::after{background:var(--danger)}
.kpi-label{font-size:10px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:0.6px;margin-bottom:6px}
.kpi-val{font-size:24px;font-weight:700;font-family:var(--mono);letter-spacing:-1px;line-height:1}
.kpi-sub{font-size:10px;color:var(--muted);margin-top:4px;display:flex;align-items:center;gap:4px}
.kpi-val.blue{color:var(--accent)}.kpi-val.green{color:var(--done)}.kpi-val.warn{color:var(--warn)}.kpi-val.purple{color:var(--rev)}.kpi-val.red{color:var(--danger)}
.trend-up{color:var(--done);font-size:9px}
.trend-down{color:var(--danger);font-size:9px}

/* GRID LAYOUTS */
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}
.grid-3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin-bottom:16px}
.grid-hero{display:grid;grid-template-columns:2fr 1fr;gap:16px;margin-bottom:16px}
.mb16{margin-bottom:16px}

/* CARDS */
.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;overflow:hidden}
.card-hdr{padding:14px 16px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between}
.card-title{font-size:12.5px;font-weight:600;display:flex;align-items:center;gap:7px}
.card-body{padding:16px}
.card-body.np{padding:0}

/* SQUAD CARDS */
.squad-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:18px;cursor:pointer;transition:all .2s}
.squad-card:hover{border-color:var(--border2);background:var(--surface2)}
.squad-hdr{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px}
.squad-name{font-size:13.5px;font-weight:700;margin-bottom:2px}
.squad-key{font-size:10px;color:var(--muted);font-family:var(--mono)}
.health-ring{width:36px;height:36px;position:relative}
.health-ring svg{transform:rotate(-90deg)}
.health-pct{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;font-family:var(--mono)}
.squad-stat-row{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:12px}
.squad-stat{background:var(--surface2);border-radius:7px;padding:7px 0;text-align:center}
.squad-stat-n{font-size:14px;font-weight:700;font-family:var(--mono)}
.squad-stat-l{font-size:9px;color:var(--muted);margin-top:2px;text-transform:uppercase;letter-spacing:0.3px}

/* RISK ALERTS */
.risk-item{display:flex;align-items:flex-start;gap:10px;padding:10px 14px;border-bottom:1px solid var(--border);transition:background .15s}
.risk-item:last-child{border-bottom:none}
.risk-item:hover{background:var(--surface2)}
.risk-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0;margin-top:4px}
.risk-dot.high{background:var(--danger)}
.risk-dot.mid{background:var(--warn)}
.risk-dot.low{background:var(--muted)}
.risk-label{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:2px}
.risk-label.high{color:var(--danger)}.risk-label.mid{color:var(--warn)}.risk-label.low{color:var(--muted)}
.risk-text{font-size:12px;color:var(--text);line-height:1.4}
.risk-meta{font-size:10.5px;color:var(--muted);margin-top:3px;font-family:var(--mono)}

/* TIMELINE */
.tl-day{margin-bottom:18px}
.tl-day-hdr{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.tl-day-label{font-size:11px;font-weight:700;color:var(--muted)}
.tl-day-today{color:var(--accent);font-family:var(--mono)}
.tl-line{flex:1;height:1px;background:var(--border)}
.tl-cnt{font-size:10px;font-family:var(--mono);color:var(--muted);background:var(--surface2);padding:2px 7px;border-radius:10px}
.tl-items{display:flex;flex-direction:column;gap:5px}
.tl-item{display:flex;align-items:center;gap:9px;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:9px 12px;transition:all .15s;cursor:default}
.tl-item:hover{border-color:var(--border2);background:var(--surface2)}
.tl-key{font-family:var(--mono);font-size:11px;color:var(--accent);font-weight:500;text-decoration:none;flex-shrink:0}
.tl-key:hover{text-decoration:underline}
.tl-title{flex:1;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--text)}
.tl-right{display:flex;align-items:center;gap:7px;flex-shrink:0}

/* BADGES */
.badge{display:inline-flex;align-items:center;padding:3px 8px;border-radius:20px;font-size:10.5px;font-weight:600;font-family:var(--mono)}
.b-done{background:rgba(34,200,122,0.12);color:var(--done);border:1px solid rgba(34,200,122,0.2)}
.b-prog{background:rgba(240,168,48,0.12);color:var(--warn);border:1px solid rgba(240,168,48,0.2)}
.b-rev{background:rgba(167,139,250,0.12);color:var(--rev);border:1px solid rgba(167,139,250,0.2)}
.b-back{background:var(--surface2);color:var(--muted);border:1px solid var(--border)}
.b-can{background:rgba(240,82,82,0.08);color:var(--danger);border:1px solid rgba(240,82,82,0.15)}
.proj-pill{font-size:10px;padding:2px 7px;border-radius:10px;font-weight:700;font-family:var(--mono)}
.proj-cf{background:rgba(79,124,255,0.1);color:var(--cf);border:1px solid rgba(79,124,255,0.2)}
.proj-sf{background:rgba(123,94,167,0.1);color:var(--sf);border:1px solid rgba(123,94,167,0.2)}

/* AVATAR */
.av{width:22px;height:22px;border-radius:50%;color:#fff;font-size:8.5px;font-weight:700;display:inline-flex;align-items:center;justify-content:center;flex-shrink:0}
.av-row{display:inline-flex;align-items:center;gap:5px}

/* TABLE */
.tbl-wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse}
th{text-align:left;padding:8px 12px;font-size:10px;font-weight:600;color:var(--muted2);text-transform:uppercase;letter-spacing:0.5px;background:var(--surface2);border-bottom:1px solid var(--border)}
td{padding:9px 12px;font-size:12px;border-bottom:1px solid rgba(255,255,255,0.04);vertical-align:middle}
tr:last-child td{border-bottom:none}
tr:hover td{background:rgba(255,255,255,0.02)}
.ikey a{font-family:var(--mono);font-size:11.5px;color:var(--accent);font-weight:500;text-decoration:none}
.ikey a:hover{text-decoration:underline}

/* AI PANEL */
.ai-panel{background:var(--surface);border:1px solid var(--border);border-radius:12px;overflow:hidden;margin-bottom:16px}
.ai-hdr{padding:14px 18px;background:linear-gradient(135deg,rgba(79,124,255,0.08),rgba(123,94,167,0.08));border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px}
.ai-icon{font-size:16px}
.ai-title{font-size:13px;font-weight:600}
.ai-sub{font-size:11px;color:var(--muted);margin-left:auto}
.ai-body{padding:16px}
.fgroup{margin-bottom:12px}
.flabel{font-size:11px;font-weight:600;color:var(--muted);margin-bottom:5px;display:block;text-transform:uppercase;letter-spacing:0.4px}
.finput,.fselect,.ftextarea{width:100%;padding:8px 10px;background:var(--surface2);border:1px solid var(--border2);border-radius:7px;font-size:12.5px;outline:none;font-family:var(--font);color:var(--text);transition:border-color .15s}
.finput:focus,.fselect:focus,.ftextarea:focus{border-color:var(--accent)}
.fselect option{background:var(--surface2)}
.ftextarea{resize:vertical;min-height:60px}
.ai-out{background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:12px;font-size:12px;min-height:80px;white-space:pre-wrap;line-height:1.7;color:var(--muted);font-family:var(--mono)}
.ai-out.loaded{color:var(--text)}
.ai-out.streaming{color:var(--text);border-color:rgba(79,124,255,0.3)}
.btn-row{display:flex;gap:8px;margin-top:10px}
.btn{padding:7px 14px;border-radius:7px;font-size:12px;font-weight:600;cursor:pointer;border:none;display:inline-flex;align-items:center;gap:5px;font-family:var(--font);transition:all .15s}
.btn-primary{background:var(--accent);color:#fff}.btn-primary:hover{background:#3d6aee}
.btn-secondary{background:var(--surface2);color:var(--text);border:1px solid var(--border2)}.btn-secondary:hover{background:var(--surface3)}
.btn:disabled{opacity:0.5;cursor:not-allowed}
.spinner{display:inline-block;width:12px;height:12px;border:2px solid rgba(255,255,255,0.3);border-top-color:#fff;border-radius:50%;animation:spin .7s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}

/* FILTERS */
.filter-row{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.fbtn{font-size:11px;padding:4px 10px;border-radius:6px;border:1px solid var(--border);background:transparent;cursor:pointer;color:var(--muted);font-family:var(--font);transition:all .15s}
.fbtn:hover,.fbtn.active{background:rgba(79,124,255,0.12);color:var(--accent);border-color:rgba(79,124,255,0.3)}
.search-inp{padding:6px 10px;background:var(--surface2);border:1px solid var(--border2);border-radius:6px;font-size:12px;width:190px;outline:none;font-family:var(--font);color:var(--text)}
.search-inp:focus{border-color:var(--accent)}

/* METRICS */
.chart-wrap{position:relative;height:200px}
.legend-row{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:10px;font-size:11px;color:var(--muted)}
.legend-dot{width:8px;height:8px;border-radius:2px;flex-shrink:0}

/* INSIGHT CARDS */
.insight-row{display:flex;flex-direction:column;gap:6px}
.insight-item{background:var(--surface2);border-radius:8px;padding:10px 12px;border-left:3px solid transparent;font-size:12px;line-height:1.5}
.insight-item.info{border-color:var(--accent)}
.insight-item.warn{border-color:var(--warn)}
.insight-item.success{border-color:var(--done)}
.insight-item.danger{border-color:var(--danger)}
.insight-title{font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:3px}
.insight-title.info{color:var(--accent)}.insight-title.warn{color:var(--warn)}.insight-title.success{color:var(--done)}.insight-title.danger{color:var(--danger)}

/* TOAST */
.toast{position:fixed;bottom:20px;right:20px;background:var(--surface3);color:var(--text);border:1px solid var(--border2);padding:10px 16px;border-radius:9px;font-size:12.5px;z-index:9999;opacity:0;transform:translateY(8px);transition:all .2s;pointer-events:none}
.toast.show{opacity:1;transform:translateY(0)}

/* PROGRESS BAR */
.prog-bar{height:5px;background:var(--surface3);border-radius:3px;overflow:hidden;margin-top:5px}
.prog-fill{height:100%;border-radius:3px;transition:width .4s ease}

/* ASSIGNEE TAG */
.asgn{font-size:11px;color:var(--muted);display:flex;align-items:center;gap:5px;max-width:130px}
.asgn-name{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

/* DAILY TODAY BOX */
.today-banner{background:linear-gradient(135deg,rgba(79,124,255,0.08),rgba(123,94,167,0.08));border:1px solid rgba(79,124,255,0.15);border-radius:12px;padding:16px 18px;margin-bottom:18px;display:flex;align-items:center;justify-content:space-between}
.today-title{font-family:var(--serif);font-style:italic;font-size:16px;color:var(--text);margin-bottom:6px}
.today-stats-row{display:flex;gap:24px}
.today-stat-n{font-size:20px;font-weight:700;font-family:var(--mono)}
.today-stat-l{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:0.3px}
.today-date{font-size:11px;font-family:var(--mono);color:var(--muted)}

/* SECTION HEADER */
.sec-hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
.sec-title{font-size:12.5px;font-weight:700;color:var(--text);display:flex;align-items:center;gap:7px}
.sec-link{font-size:11px;color:var(--accent);cursor:pointer;text-decoration:none}
.sec-link:hover{text-decoration:underline}

/* EMPTY STATE */
.empty{text-align:center;padding:32px;color:var(--muted);font-size:12px}

/* SPRINT HEALTH */
.health-bar-row{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.health-bar-label{font-size:11px;color:var(--muted);width:90px;flex-shrink:0}
.health-bar-outer{flex:1;height:6px;background:var(--surface3);border-radius:3px;overflow:hidden}
.health-bar-fill{height:100%;border-radius:3px}
.health-bar-val{font-size:11px;font-family:var(--mono);color:var(--muted);width:32px;text-align:right;flex-shrink:0}

/* SUMMARY CARD (AI generated) */
.summary-card{background:linear-gradient(135deg,rgba(79,124,255,0.05),rgba(123,94,167,0.05));border:1px solid rgba(79,124,255,0.12);border-radius:12px;padding:18px;margin-bottom:16px}
.summary-title{font-family:var(--serif);font-style:italic;font-size:15px;color:var(--text);margin-bottom:10px;display:flex;align-items:center;gap:8px}
.summary-body{font-size:12.5px;color:var(--muted);line-height:1.7;white-space:pre-wrap;font-family:var(--mono)}
.summary-body.loaded{color:var(--text);font-family:var(--font)}
</style>
</head>
<body>
<div class="app">
  <!-- SIDEBAR -->
  <div class="sidebar">
    <div class="logo-area">
      <div class="logo-row">
        <div class="logo-mark">🚗</div>
        <div class="logo-name">Turbi</div>
      </div>
      <div class="logo-sub">PM Intelligence</div>
    </div>
    <nav>
      <div class="nav-section">Visão</div>
      <div class="nav-item active" onclick="show('overview',this)"><div class="nav-dot" style="background:#4F7CFF"></div>Overview</div>
      <div class="nav-item" onclick="show('daily',this)"><div class="nav-dot" style="background:#F0A830"></div>Resumo Diário<span class="nav-badge" id="today-badge">0</span></div>
      <div class="nav-section">Squads</div>
      <div class="nav-item" onclick="show('cf',this)"><div class="nav-dot" style="background:#4F7CFF"></div>Core Financeiro</div>
      <div class="nav-item" onclick="show('sf',this)"><div class="nav-dot" style="background:#7B5EA7"></div>Tech Salesforce</div>
      <div class="nav-section">Análise</div>
      <div class="nav-item" onclick="show('risks',this)"><div class="nav-dot" style="background:#F05252"></div>Riscos &amp; Alertas<span class="nav-badge danger" id="risk-badge">0</span></div>
      <div class="nav-item" onclick="show('issues',this)"><div class="nav-dot" style="background:#7A8299"></div>Todas as Issues</div>
      <div class="nav-item" onclick="show('metrics',this)"><div class="nav-dot" style="background:#22C87A"></div>Métricas</div>
      <div class="nav-section">IA</div>
      <div class="nav-item" onclick="show('ai',this)"><div class="nav-dot" style="background:linear-gradient(135deg,#4F7CFF,#7B5EA7)"></div>Assistente PM</div>
    </nav>
    <div class="sidebar-footer"><span class="footer-pulse"></span><span id="footer-ts">Atualizando…</span><br><span id="footer-total">—</span></div>
  </div>

  <!-- MAIN -->
  <div class="main">
    <div class="topbar">
      <div class="topbar-left">
        <div class="page-title" id="page-title">Overview</div>
        <span class="pill pill-blue">turbi-team.atlassian.net</span>
      </div>
      <div class="topbar-right">
        <span class="pill pill-gray" id="topbar-date">—</span>
      </div>
    </div>

    <div class="content">

      <!-- ═══ OVERVIEW ═══ -->
      <div id="view-overview" class="view active">
        <div class="kpi-row" id="kpis-overview"></div>

        <div class="grid-hero">
          <div>
            <div class="sec-hdr"><div class="sec-title">💰 Core Financeiro · Saúde do Sprint</div><a class="sec-link" onclick="show('cf',document.querySelectorAll('.nav-item')[2])">ver detalhes →</a></div>
            <div id="squad-cf-card"></div>
          </div>
          <div>
            <div class="sec-hdr"><div class="sec-title">🔗 Tech Salesforce · Saúde do Sprint</div><a class="sec-link" onclick="show('sf',document.querySelectorAll('.nav-item')[3])">ver detalhes →</a></div>
            <div id="squad-sf-card"></div>
          </div>
        </div>

        <div class="grid-2">
          <div class="card">
            <div class="card-hdr"><div class="card-title">⚡ Movimentações Recentes</div><span style="font-size:10px;color:var(--muted);font-family:var(--mono)">últimas 24h</span></div>
            <div id="recent-list"></div>
          </div>
          <div class="card">
            <div class="card-hdr"><div class="card-title">🚨 Alertas de Risco</div><span class="pill pill-warn" id="risk-count-pill">0 alertas</span></div>
            <div id="risk-list-mini"></div>
          </div>
        </div>
      </div>

      <!-- ═══ DAILY ═══ -->
      <div id="view-daily" class="view">
        <div class="today-banner" id="today-banner"></div>
        <div id="timeline-container"></div>
      </div>

      <!-- ═══ CF ═══ -->
      <div id="view-cf" class="view">
        <div class="kpi-row" id="kpis-cf"></div>
        <div class="summary-card" id="cf-summary">
          <div class="summary-title">✨ Resumo Automático · Core Financeiro</div>
          <div class="summary-body" id="cf-summary-body">Carregando análise…</div>
        </div>
        <div class="grid-2 mb16">
          <div class="card">
            <div class="card-hdr"><div class="card-title">Distribuição de Status</div></div>
            <div class="card-body">
              <div id="cf-legend" class="legend-row"></div>
              <div class="chart-wrap"><canvas id="cfChart" role="img" aria-label="Status distribution for Core Financeiro">Status chart</canvas></div>
            </div>
          </div>
          <div class="card">
            <div class="card-hdr"><div class="card-title">Insights Automáticos</div></div>
            <div class="card-body">
              <div class="insight-row" id="cf-insights"></div>
            </div>
          </div>
        </div>
        <div class="card">
          <div class="card-hdr">
            <div class="card-title">💰 Core Financeiro · Issues</div>
            <div class="filter-row">
              <input class="search-inp" placeholder="🔍 Buscar…" oninput="filterTable('cf','',this.value)"/>
              <button class="fbtn active" onclick="filterTable('cf','all',null,this)">Todas</button>
              <button class="fbtn" onclick="filterTable('cf','Em andamento',null,this)">Em andamento</button>
              <button class="fbtn" onclick="filterTable('cf','Revisar',null,this)">Revisar</button>
              <button class="fbtn" onclick="filterTable('cf','Concluído',null,this)">Concluído</button>
              <button class="fbtn" onclick="filterTable('cf','Backlog',null,this)">Backlog</button>
            </div>
          </div>
          <div class="tbl-wrap"><table><thead><tr><th>Chave</th><th>Título</th><th>Status</th><th>Tipo</th><th>Responsável</th><th>Atualizado</th></tr></thead><tbody id="cf-tbody"></tbody></table></div>
        </div>
      </div>

      <!-- ═══ SF ═══ -->
      <div id="view-sf" class="view">
        <div class="kpi-row" id="kpis-sf"></div>
        <div class="summary-card" id="sf-summary">
          <div class="summary-title">✨ Resumo Automático · Tech Salesforce</div>
          <div class="summary-body" id="sf-summary-body">Carregando análise…</div>
        </div>
        <div class="grid-2 mb16">
          <div class="card">
            <div class="card-hdr"><div class="card-title">Distribuição de Status</div></div>
            <div class="card-body">
              <div id="sf-legend" class="legend-row"></div>
              <div class="chart-wrap"><canvas id="sfChart" role="img" aria-label="Status distribution for Tech Salesforce">Status chart</canvas></div>
            </div>
          </div>
          <div class="card">
            <div class="card-hdr"><div class="card-title">Insights Automáticos</div></div>
            <div class="card-body">
              <div class="insight-row" id="sf-insights"></div>
            </div>
          </div>
        </div>
        <div class="card">
          <div class="card-hdr">
            <div class="card-title">🔗 Tech Salesforce · Issues</div>
            <div class="filter-row">
              <input class="search-inp" placeholder="🔍 Buscar…" oninput="filterTable('sf','',this.value)"/>
              <button class="fbtn active" onclick="filterTable('sf','all',null,this)">Todas</button>
              <button class="fbtn" onclick="filterTable('sf','Em andamento',null,this)">Em andamento</button>
              <button class="fbtn" onclick="filterTable('sf','Concluído',null,this)">Concluído</button>
              <button class="fbtn" onclick="filterTable('sf','Backlog',null,this)">Backlog</button>
            </div>
          </div>
          <div class="tbl-wrap"><table><thead><tr><th>Chave</th><th>Título</th><th>Status</th><th>Tipo</th><th>Responsável</th><th>Atualizado</th></tr></thead><tbody id="sf-tbody"></tbody></table></div>
        </div>
      </div>

      <!-- ═══ RISKS ═══ -->
      <div id="view-risks" class="view">
        <div class="kpi-row" id="kpis-risks"></div>
        <div class="grid-2">
          <div class="card">
            <div class="card-hdr"><div class="card-title">🔴 Issues Sem Responsável</div></div>
            <div id="unassigned-list"></div>
          </div>
          <div class="card">
            <div class="card-hdr"><div class="card-title">🟡 Em Andamento Há Mais de 7 Dias</div></div>
            <div id="stale-list"></div>
          </div>
        </div>
        <div class="grid-2">
          <div class="card">
            <div class="card-hdr"><div class="card-title">⏳ Spikes Sem Conclusão</div></div>
            <div id="spikes-list"></div>
          </div>
          <div class="card">
            <div class="card-hdr"><div class="card-title">👀 Aguardando Revisão</div></div>
            <div id="review-list"></div>
          </div>
        </div>
      </div>

      <!-- ═══ ALL ISSUES ═══ -->
      <div id="view-issues" class="view">
        <div class="card">
          <div class="card-hdr">
            <div class="card-title">Todas as Issues</div>
            <div class="filter-row">
              <input class="search-inp" placeholder="🔍 Buscar…" oninput="filterTable('all','',this.value)"/>
              <button class="fbtn active" onclick="filterTable('all','all',null,this)">Todas</button>
              <button class="fbtn" onclick="filterTable('all','Em andamento',null,this)">⚡ Andamento</button>
              <button class="fbtn" onclick="filterTable('all','Revisar',null,this)">👀 Revisar</button>
              <button class="fbtn" onclick="filterTable('all','Concluído',null,this)">✅ Concluído</button>
              <button class="fbtn" onclick="filterTable('all','Backlog',null,this)">📥 Backlog</button>
            </div>
          </div>
          <div class="tbl-wrap"><table><thead><tr><th>Chave</th><th>Título</th><th>Squad</th><th>Status</th><th>Tipo</th><th>Responsável</th><th>Atualizado</th></tr></thead><tbody id="all-tbody"></tbody></table></div>
        </div>
      </div>

      <!-- ═══ METRICS ═══ -->
      <div id="view-metrics" class="view">
        <div class="kpi-row" id="kpis-metrics"></div>
        <div class="grid-2">
          <div class="card">
            <div class="card-hdr"><div class="card-title">Workload por Responsável (CF)</div></div>
            <div class="card-body">
              <div id="wl-legend" class="legend-row"></div>
              <div class="chart-wrap" style="height:240px"><canvas id="wlChart" role="img" aria-label="Workload by assignee in CF">Workload chart</canvas></div>
            </div>
          </div>
          <div class="card">
            <div class="card-hdr"><div class="card-title">Atividade Diária (últimas 2 semanas)</div></div>
            <div class="card-body">
              <div class="chart-wrap"><canvas id="actChart" role="img" aria-label="Daily activity last 2 weeks">Activity chart</canvas></div>
            </div>
          </div>
        </div>
        <div class="grid-2">
          <div class="card">
            <div class="card-hdr"><div class="card-title">Status CF vs SF</div></div>
            <div class="card-body">
              <div id="compare-legend" class="legend-row"></div>
              <div class="chart-wrap"><canvas id="compareChart" role="img" aria-label="CF vs SF status comparison">Compare chart</canvas></div>
            </div>
          </div>
          <div class="card">
            <div class="card-hdr"><div class="card-title">Tipos de Issue</div></div>
            <div class="card-body">
              <div id="type-legend" class="legend-row"></div>
              <div class="chart-wrap"><canvas id="typeChart" role="img" aria-label="Issue type distribution">Type chart</canvas></div>
            </div>
          </div>
        </div>
      </div>

      <!-- ═══ AI ASSISTANT ═══ -->
      <div id="view-ai" class="view">
        <div style="font-size:12.5px;color:var(--muted);margin-bottom:18px;font-style:italic">Assistente PM com IA real. Preencha → gere → use direto ou adapte no Claude.</div>
        <div class="grid-2">
          <div class="ai-panel">
            <div class="ai-hdr"><div class="ai-icon">📝</div><div><div class="ai-title">Escrever Task/História</div><div class="ai-sub" style="font-size:11px;color:var(--muted)">Descrição + AC + DoD</div></div></div>
            <div class="ai-body">
              <div class="fgroup"><label class="flabel">Squad</label><select class="fselect" id="t-sq"><option>Core Financeiro (CF)</option><option>Tech Salesforce (SF)</option></select></div>
              <div class="fgroup"><label class="flabel">Título</label><input class="finput" id="t-ti" placeholder="Ex: Implementar conciliação automática Adyen"/></div>
              <div class="fgroup"><label class="flabel">Contexto</label><textarea class="ftextarea" id="t-cx" placeholder="O que precisa ser feito e por quê…"></textarea></div>
              <div class="fgroup"><label class="flabel">Tipo</label><select class="fselect" id="t-ty"><option>História</option><option>Tarefa Técnica</option><option>Bug</option><option>Spike</option></select></div>
              <div class="btn-row"><button class="btn btn-primary" id="btn-task" onclick="callAI('task')">✨ Gerar com IA</button><button class="btn btn-secondary" onclick="cp('t-out')">📋 Copiar</button></div>
              <div style="margin-top:12px"><label class="flabel">Resultado:</label><div class="ai-out" id="t-out" style="margin-top:5px">Preencha os campos acima.</div></div>
            </div>
          </div>
          <div class="ai-panel">
            <div class="ai-hdr"><div class="ai-icon">💬</div><div><div class="ai-title">Comentário de Issue</div><div class="ai-sub" style="font-size:11px;color:var(--muted)">Atualização, bloqueio, handoff</div></div></div>
            <div class="ai-body">
              <div class="fgroup"><label class="flabel">Issue</label><input class="finput" id="c-is" placeholder="CF-320"/></div>
              <div class="fgroup"><label class="flabel">Tipo</label><select class="fselect" id="c-ty"><option>Atualização de progresso</option><option>Reportar bloqueio</option><option>Handoff para QA</option><option>Resolução de bloqueio</option><option>Pedido de revisão</option></select></div>
              <div class="fgroup"><label class="flabel">Contexto</label><textarea class="ftextarea" id="c-cx" placeholder="O que aconteceu…"></textarea></div>
              <div class="btn-row"><button class="btn btn-primary" id="btn-comment" onclick="callAI('comment')">✨ Gerar com IA</button><button class="btn btn-secondary" onclick="cp('c-out')">📋 Copiar</button></div>
              <div style="margin-top:12px"><label class="flabel">Resultado:</label><div class="ai-out" id="c-out" style="margin-top:5px">Preencha os campos acima.</div></div>
            </div>
          </div>
          <div class="ai-panel">
            <div class="ai-hdr"><div class="ai-icon">📊</div><div><div class="ai-title">Resumo de Sprint</div><div class="ai-sub" style="font-size:11px;color:var(--muted)">Para stakeholders</div></div></div>
            <div class="ai-body">
              <div class="fgroup"><label class="flabel">Squad</label><select class="fselect" id="s-sq"><option>Core Financeiro (CF)</option><option>Tech Salesforce (SF)</option></select></div>
              <div class="fgroup"><label class="flabel">Audiência</label><select class="fselect" id="s-au"><option>C-Level</option><option>Stakeholders de produto</option><option>Time técnico</option><option>Slack do time</option></select></div>
              <div class="fgroup"><label class="flabel">Principais entregas</label><textarea class="ftextarea" id="s-de" placeholder="Features ou fixes entregues…"></textarea></div>
              <div class="btn-row"><button class="btn btn-primary" id="btn-sprint" onclick="callAI('sprint')">✨ Gerar com IA</button><button class="btn btn-secondary" onclick="cp('s-out')">📋 Copiar</button></div>
              <div style="margin-top:12px"><label class="flabel">Resultado:</label><div class="ai-out" id="s-out" style="margin-top:5px">Preencha os campos acima.</div></div>
            </div>
          </div>
          <div class="ai-panel">
            <div class="ai-hdr"><div class="ai-icon">☀️</div><div><div class="ai-title">Daily Standup</div><div class="ai-sub" style="font-size:11px;color:var(--muted)">Resumo para o time</div></div></div>
            <div class="ai-body">
              <div class="fgroup"><label class="flabel">Squad</label><select class="fselect" id="d-sq"><option>Core Financeiro (CF)</option><option>Tech Salesforce (SF)</option><option>CF + SF</option></select></div>
              <div class="fgroup"><label class="flabel">Destaques / impedimentos</label><textarea class="ftextarea" id="d-im" placeholder="Algo além das issues do Jira?"></textarea></div>
              <div class="btn-row"><button class="btn btn-primary" id="btn-daily" onclick="callAI('daily')">✨ Gerar com IA</button><button class="btn btn-secondary" onclick="cp('d-out')">📋 Copiar</button></div>
              <div style="margin-top:12px"><label class="flabel">Resultado:</label><div class="ai-out" id="d-out" style="margin-top:5px">Preencha os campos acima.</div></div>
            </div>
          </div>
        </div>
      </div>

    </div><!-- /content -->
  </div><!-- /main -->
</div><!-- /app -->
<div class="toast" id="toast"></div>

<script>
const ISSUES = __ISSUES_JSON__;
const TIMELINE = __TIMELINE_JSON__;
const GENERATED_AT = "__GENERATED_AT__";
const TODAY = "__TODAY__";

// ── Constants ──────────────────────────────────────────────
const PROJ = {
  CF:{color:'#4F7CFF',bg:'rgba(79,124,255,0.1)',board:'https://turbi-team.atlassian.net/jira/software/c/projects/CF/boards/1034'},
  SF:{color:'#7B5EA7',bg:'rgba(123,94,167,0.1)',board:'https://turbi-team.atlassian.net/jira/software/c/projects/SF/boards/1599'}
};
const STATUS_CLS = {'Concluído':'b-done','Em andamento':'b-prog','Revisar':'b-rev','Backlog':'b-back','Ready To Develop':'b-back','Cancelado':'b-can'};
const STATUS_ICON = {'Concluído':'✅','Em andamento':'⚡','Revisar':'👀','Backlog':'📥','Ready To Develop':'📋','Cancelado':'❌'};
const STATUS_COLORS = {'Concluído':'#22C87A','Em andamento':'#F0A830','Revisar':'#A78BFA','Backlog':'#4E5570','Ready To Develop':'#4F7CFF','Cancelado':'#F05252'};
const AV_COLS = ['#4F7CFF','#7B5EA7','#F0A830','#22C87A','#F05252','#06B6D4','#EC4899'];
const VIEWS = {overview:'Overview',daily:'Resumo Diário',cf:'Core Financeiro',sf:'Tech Salesforce',risks:'Riscos & Alertas',issues:'Todas as Issues',metrics:'Métricas',ai:'Assistente PM'};
const FILTERS = {cf:{status:'all',search:''},sf:{status:'all',search:''},all:{status:'all',search:''}};
let chartsRendered = false;

// ── Helpers ─────────────────────────────────────────────────
function badge(s){const c=STATUS_CLS[s]||'b-back';const i=STATUS_ICON[s]||'•';return`<span class="badge ${c}">${i} ${s}</span>`}
function projPill(k){const p=PROJ[k]||{color:'#7A8299'};return`<span class="proj-pill proj-${k.toLowerCase()}">${k}</span>`}
function avatar(n){
  if(!n||n==='Unassigned')return`<div class="av" style="background:#2C3040;color:#7A8299">?</div>`;
  const p=n.trim().split(/[\\s.\\-_]+/);
  const init=p.length>=2?p[0][0]+p[p.length-1][0]:n.substring(0,2);
  const c=AV_COLS[n.charCodeAt(0)%AV_COLS.length];
  return`<div class="av" style="background:${c}">${init.toUpperCase()}</div>`;
}
function fmtDate(iso){if(!iso)return'—';return new Date(iso).toLocaleDateString('pt-BR',{day:'2-digit',month:'2-digit'})}
function fmtDaysAgo(iso){if(!iso)return'—';const d=Math.round((Date.now()-new Date(iso))/86400000);return d===0?'hoje':d===1?'ontem':`${d}d atrás`}
function fmtDateLong(s){
  const d=new Date(s+'T12:00:00');const t=new Date(TODAY+'T12:00:00');
  const diff=Math.round((t-d)/86400000);
  if(diff===0)return'Hoje';if(diff===1)return'Ontem';
  return d.toLocaleDateString('pt-BR',{weekday:'long',day:'2-digit',month:'long'});
}
function shortName(n){if(!n||n==='Unassigned')return'<i style="color:var(--muted2)">—</i>';const p=n.trim().split(/[\\s.\\-_]+/);return p.length>=2?p[0]+' '+p[p.length-1]:p[0]}
function getStats(pk){
  const l=pk?ISSUES.filter(i=>i.project_key===pk):ISSUES;
  return{total:l.length,done:l.filter(i=>i.status==='Concluído').length,prog:l.filter(i=>i.status==='Em andamento').length,
    rev:l.filter(i=>i.status==='Revisar').length,back:l.filter(i=>['Backlog','Ready To Develop'].includes(i.status)).length,
    can:l.filter(i=>i.status==='Cancelado').length};
}
function toast(msg,type=''){const e=document.getElementById('toast');e.textContent=msg;e.className='toast show '+(type||'');setTimeout(()=>e.classList.remove('show'),2800)}
function cp(id){const t=document.getElementById(id).textContent;if(t.startsWith('Preencha')){toast('Gere primeiro');return}navigator.clipboard.writeText(t).then(()=>toast('Copiado ✅'))}

// ── Navigation ───────────────────────────────────────────────
function show(name,el){
  document.querySelectorAll('.view').forEach(v=>v.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));
  document.getElementById('view-'+name).classList.add('active');
  if(el)el.classList.add('active');
  document.getElementById('page-title').textContent=VIEWS[name]||name;
  if(name==='metrics'&&!chartsRendered){setTimeout(renderCharts,80);chartsRendered=true;}
  if(name==='cf'){renderSquadSummary('CF');renderInsights('CF');}
  if(name==='sf'){renderSquadSummary('SF');renderInsights('SF');}
}

// ── KPIs ─────────────────────────────────────────────────────
function kpiHTML(label,val,sub,cls){return`<div class="kpi ${cls}"><div class="kpi-label">${label}</div><div class="kpi-val ${cls}">${val}</div><div class="kpi-sub">${sub}</div></div>`}

function renderKPIs(containerId,pk){
  const s=getStats(pk);const pct=s.total>0?Math.round(s.done/s.total*100):0;
  const today=pk?(TIMELINE[TODAY]||[]).filter(i=>i.project_key===pk).length:(TIMELINE[TODAY]||[]).length;
  document.getElementById(containerId).innerHTML=
    kpiHTML('Total',s.total,pk?pk:'CF+SF','blue')+
    kpiHTML('Concluídas',s.done,pct+'%','green')+
    kpiHTML('Em Andamento',s.prog,'ativas','warn')+
    kpiHTML('Revisar',s.rev,'aguardando','purple')+
    kpiHTML('Hoje',today,'movimentações','blue');
}

// ── Squad Cards ──────────────────────────────────────────────
function renderSquadCard(containerId,pk){
  const s=getStats(pk);const p=PROJ[pk];
  const pct=s.total>0?Math.round(s.done/s.total*100):0;
  const inProg=s.prog;const hasCritical=inProg>0&&s.rev>2;
  const c=document.getElementById(containerId);
  c.innerHTML=`
    <div class="squad-card" onclick="window.open('${p.board}','_blank')">
      <div class="squad-hdr">
        <div>
          <div class="squad-name" style="color:${p.color}">${pk==='CF'?'💰 Core Financeiro':'🔗 Tech Salesforce'}</div>
          <div class="squad-key">${pk}</div>
        </div>
        <div class="health-ring">
          <svg width="36" height="36" viewBox="0 0 36 36">
            <circle cx="18" cy="18" r="14" fill="none" stroke="#1A1E28" stroke-width="4"/>
            <circle cx="18" cy="18" r="14" fill="none" stroke="${pct>=60?'#22C87A':pct>=30?'#F0A830':'#F05252'}" stroke-width="4" stroke-dasharray="${Math.round(2*Math.PI*14*pct/100)} ${Math.round(2*Math.PI*14)}" stroke-linecap="round"/>
          </svg>
          <div class="health-pct" style="color:${pct>=60?'#22C87A':pct>=30?'#F0A830':'#F05252'}">${pct}%</div>
        </div>
      </div>
      <div style="margin-bottom:10px">
        <div class="health-bar-row"><div class="health-bar-label" style="color:#22C87A;font-size:10px">Concluído</div><div class="health-bar-outer"><div class="health-bar-fill" style="width:${s.total>0?Math.round(s.done/s.total*100):0}%;background:#22C87A"></div></div><div class="health-bar-val">${s.done}</div></div>
        <div class="health-bar-row"><div class="health-bar-label" style="color:#F0A830;font-size:10px">Em andamento</div><div class="health-bar-outer"><div class="health-bar-fill" style="width:${s.total>0?Math.round(s.prog/s.total*100):0}%;background:#F0A830"></div></div><div class="health-bar-val">${s.prog}</div></div>
        <div class="health-bar-row"><div class="health-bar-label" style="color:#A78BFA;font-size:10px">Revisar</div><div class="health-bar-outer"><div class="health-bar-fill" style="width:${s.total>0?Math.round(s.rev/s.total*100):0}%;background:#A78BFA"></div></div><div class="health-bar-val">${s.rev}</div></div>
        <div class="health-bar-row"><div class="health-bar-label" style="color:var(--muted);font-size:10px">Backlog</div><div class="health-bar-outer"><div class="health-bar-fill" style="width:${s.total>0?Math.round(s.back/s.total*100):0}%;background:var(--muted2)"></div></div><div class="health-bar-val">${s.back}</div></div>
      </div>
    </div>`;
}

// ── Risk Computation ─────────────────────────────────────────
function computeRisks(){
  const risks=[];
  const now=new Date();
  // Sem responsável em andamento
  ISSUES.filter(i=>i.status==='Em andamento'&&i.assignee==='Unassigned').forEach(i=>risks.push({level:'high',issue:i.key,text:`Issue em andamento sem responsável: ${i.summary.slice(0,55)}...`,meta:i.project_key}));
  // Issues em andamento há mais de 7 dias
  ISSUES.filter(i=>i.status==='Em andamento').forEach(i=>{const d=Math.round((now-new Date(i.updated))/86400000);if(d>7)risks.push({level:'mid',issue:i.key,text:`Sem movimentação há ${d} dias: ${i.summary.slice(0,50)}...`,meta:i.project_key})});
  // Spikes em aberto
  ISSUES.filter(i=>i.issuetype==='Spike'&&!['Concluído','Cancelado'].includes(i.status)).forEach(i=>risks.push({level:'mid',issue:i.key,text:`Spike sem conclusão: ${i.summary.slice(0,55)}...`,meta:i.project_key}));
  // Muitas coisas em revisar
  const rev=ISSUES.filter(i=>i.status==='Revisar');if(rev.length>2)risks.push({level:'mid',issue:'GERAL',text:`${rev.length} issues aguardando revisão — pode criar gargalo`,meta:'CF/SF'});
  // Backlog grande sem owner
  const unownedBack=ISSUES.filter(i=>['Backlog','Ready To Develop'].includes(i.status)&&i.assignee==='Unassigned');
  if(unownedBack.length>10)risks.push({level:'low',issue:'GERAL',text:`${unownedBack.length} issues no backlog sem responsável`,meta:'CF/SF'});
  return risks;
}

function renderRisks(){
  const risks=computeRisks();
  document.getElementById('risk-badge').textContent=risks.filter(r=>r.level==='high').length;
  document.getElementById('risk-count-pill').textContent=`${risks.length} alertas`;

  // Mini list on overview
  const mini=document.getElementById('risk-list-mini');
  const top=risks.slice(0,5);
  mini.innerHTML=top.length?top.map(r=>`
    <div class="risk-item">
      <div class="risk-dot ${r.level}"></div>
      <div>
        <div class="risk-label ${r.level}">${r.level==='high'?'CRÍTICO':r.level==='mid'?'ATENÇÃO':'INFO'}</div>
        <div class="risk-text">${r.text}</div>
        <div class="risk-meta">${r.issue} · ${r.meta}</div>
      </div>
    </div>`).join(''):`<div class="empty">Nenhum risco identificado 🎉</div>`;

  // Full risks view
  const unassigned=ISSUES.filter(i=>i.assignee==='Unassigned'&&i.status==='Em andamento');
  document.getElementById('unassigned-list').innerHTML=unassigned.length?unassigned.map(i=>`
    <div class="risk-item"><div class="risk-dot high"></div><div>
      <div class="risk-label high">SEM RESPONSÁVEL</div>
      <div class="risk-text">${i.summary.slice(0,70)}</div>
      <div class="risk-meta">${i.key} · ${i.project_key}</div>
    </div></div>`).join(''):`<div class="empty">Nenhuma issue</div>`;

  const now=new Date();
  const stale=ISSUES.filter(i=>i.status==='Em andamento'&&Math.round((now-new Date(i.updated))/86400000)>7);
  document.getElementById('stale-list').innerHTML=stale.length?stale.map(i=>{const d=Math.round((now-new Date(i.updated))/86400000);return`
    <div class="risk-item"><div class="risk-dot mid"></div><div>
      <div class="risk-label mid">${d} DIAS PARADO</div>
      <div class="risk-text">${i.summary.slice(0,65)}</div>
      <div class="risk-meta">${i.key} · ${i.assignee!=='Unassigned'?shortName(i.assignee):'sem responsável'}</div>
    </div></div>`}).join(''):`<div class="empty">Nenhuma issue estagnada</div>`;

  const spikes=ISSUES.filter(i=>i.issuetype==='Spike'&&!['Concluído','Cancelado'].includes(i.status));
  document.getElementById('spikes-list').innerHTML=spikes.length?spikes.map(i=>`
    <div class="risk-item"><div class="risk-dot mid"></div><div>
      <div class="risk-label mid">SPIKE ABERTO</div>
      <div class="risk-text">${i.summary.slice(0,65)}</div>
      <div class="risk-meta">${i.key} · ${i.assignee!=='Unassigned'?shortName(i.assignee):'sem responsável'}</div>
    </div></div>`).join(''):`<div class="empty">Nenhum spike em aberto</div>`;

  const revs=ISSUES.filter(i=>i.status==='Revisar');
  document.getElementById('review-list').innerHTML=revs.length?revs.map(i=>`
    <div class="risk-item"><div class="risk-dot low"></div><div>
      <div class="risk-label low">REVISAR</div>
      <div class="risk-text">${i.summary.slice(0,65)}</div>
      <div class="risk-meta">${i.key} · ${i.project_key}</div>
    </div></div>`).join(''):`<div class="empty">Nenhuma issue aguardando revisão</div>`;

  // Risk KPIs
  const s=getStats(null);
  document.getElementById('kpis-risks').innerHTML=
    kpiHTML('Críticos',risks.filter(r=>r.level==='high').length,'sem responsável','red')+
    kpiHTML('Atenção',risks.filter(r=>r.level==='mid').length,'monitorar','warn')+
    kpiHTML('Stale',stale.length,'>7 dias','warn')+
    kpiHTML('Em Revisão',ISSUES.filter(i=>i.status==='Revisar').length,'aguardando','purple')+
    kpiHTML('Spikes',spikes.length,'em aberto','blue');
}

// ── Timeline / Daily ────────────────────────────────────────
function renderDaily(){
  const todayItems=TIMELINE[TODAY]||[];
  const done=todayItems.filter(i=>i.status==='Concluído').length;
  const prog=todayItems.filter(i=>['Em andamento','Revisar'].includes(i.status)).length;
  const back=todayItems.filter(i=>['Backlog','Ready To Develop'].includes(i.status)).length;
  const todayFmt=new Date(TODAY+'T12:00:00').toLocaleDateString('pt-BR',{day:'2-digit',month:'long',year:'numeric'});
  document.getElementById('today-banner').innerHTML=`
    <div>
      <div class="today-title">Resumo de ${todayFmt}</div>
      <div class="today-stats-row">
        <div class="today-stat"><div class="today-stat-n" style="color:#22C87A">${done}</div><div class="today-stat-l">Concluídas</div></div>
        <div class="today-stat"><div class="today-stat-n" style="color:#F0A830">${prog}</div><div class="today-stat-l">Andamento</div></div>
        <div class="today-stat"><div class="today-stat-n" style="color:var(--muted)">${back}</div><div class="today-stat-l">Backlog</div></div>
        <div class="today-stat"><div class="today-stat-n" style="color:var(--accent)">${todayItems.length}</div><div class="today-stat-l">Total</div></div>
      </div>
    </div>
    <div class="today-date">🕐 ${GENERATED_AT.slice(11,16)} · BRT</div>`;
  const c=document.getElementById('timeline-container');c.innerHTML='';
  Object.entries(TIMELINE).forEach(([day,items])=>{
    const isToday=day===TODAY;
    const doneN=items.filter(i=>i.status==='Concluído').length;
    const progN=items.filter(i=>['Em andamento','Revisar'].includes(i.status)).length;
    const sec=document.createElement('div');sec.className='tl-day';
    sec.innerHTML=`<div class="tl-day-hdr">
      <span class="tl-day-label ${isToday?'tl-day-today':''}">${fmtDateLong(day)}</span>
      <span class="tl-cnt">${items.length}</span>
      ${doneN?`<span class="tl-cnt" style="background:rgba(34,200,122,0.1);color:#22C87A">${doneN} ✅</span>`:''}
      ${progN?`<span class="tl-cnt" style="background:rgba(240,168,48,0.1);color:#F0A830">${progN} ⚡</span>`:''}
      <div class="tl-line"></div>
    </div>
    <div class="tl-items">${items.map(i=>`
      <div class="tl-item">
        <a class="tl-key" href="https://turbi-team.atlassian.net/browse/${i.key}" target="_blank">${i.key}</a>
        ${projPill(i.project_key)}
        <div class="tl-title" title="${i.summary}">${i.summary}</div>
        <div class="tl-right">${badge(i.status)}${avatar(i.assignee)}</div>
      </div>`).join('')}
    </div>`;
    c.appendChild(sec);
  });
}

// ── Recent list ──────────────────────────────────────────────
function renderRecent(){
  const todayAll=(TIMELINE[TODAY]||[]).slice(0,8);
  const c=document.getElementById('recent-list');
  c.innerHTML=todayAll.length?todayAll.map(i=>`
    <div class="risk-item">
      <div>${projPill(i.project_key)}</div>
      <div style="flex:1">
        <div style="font-size:11.5px;color:var(--text)">${i.summary.slice(0,55)}${i.summary.length>55?'…':''}</div>
        <div class="risk-meta" style="margin-top:2px"><a class="tl-key" href="https://turbi-team.atlassian.net/browse/${i.key}" target="_blank">${i.key}</a></div>
      </div>
      <div>${badge(i.status)}</div>
    </div>`).join(''):`<div class="empty">Sem movimentações hoje</div>`;
}

// ── Tables ───────────────────────────────────────────────────
function rowHTML(i,showProj=false){
  return`<tr>
    <td class="ikey"><a href="https://turbi-team.atlassian.net/browse/${i.key}" target="_blank">${i.key}</a></td>
    <td style="max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${i.summary}">${i.summary}</td>
    ${showProj?`<td>${projPill(i.project_key)}</td>`:''}
    <td>${badge(i.status)}</td>
    <td style="font-size:10.5px;color:var(--muted)">${i.issuetype}</td>
    <td><div class="av-row">${avatar(i.assignee)}<span style="font-size:11.5px;color:var(--muted)">${shortName(i.assignee)}</span></div></td>
    <td style="font-size:11px;color:var(--muted);font-family:var(--mono)">${fmtDaysAgo(i.updated)}</td>
  </tr>`;
}
function filterTable(view,status,search,btn){
  if(status!==null&&status!==undefined){
    FILTERS[view].status=status;
    if(btn){btn.closest('.filter-row').querySelectorAll('.fbtn').forEach(b=>b.classList.remove('active'));btn.classList.add('active')}
  }
  if(search!==null&&search!==undefined)FILTERS[view].search=search.toLowerCase();
  const pk=view==='cf'?'CF':view==='sf'?'SF':null;
  let list=pk?ISSUES.filter(i=>i.project_key===pk):[...ISSUES];
  if(FILTERS[view].status!=='all')list=list.filter(i=>i.status===FILTERS[view].status);
  if(FILTERS[view].search)list=list.filter(i=>i.summary.toLowerCase().includes(FILTERS[view].search)||i.key.toLowerCase().includes(FILTERS[view].search)||i.assignee.toLowerCase().includes(FILTERS[view].search));
  document.getElementById(view+'-tbody').innerHTML=list.map(i=>rowHTML(i,view==='all')).join('');
}

// ── Charts ───────────────────────────────────────────────────
function buildLegend(id,labels,colors){
  document.getElementById(id).innerHTML=labels.map((l,i)=>`<span style="display:flex;align-items:center;gap:4px"><span class="legend-dot" style="background:${colors[i]}"></span>${l}</span>`).join('');
}
function renderCharts(){
  const SC=STATUS_COLORS;
  function donut(id,legendId,pk){
    const counts={};ISSUES.filter(i=>i.project_key===pk).forEach(i=>{counts[i.status]=(counts[i.status]||0)+1});
    const labels=Object.keys(counts),vals=Object.values(counts),cols=labels.map(s=>SC[s]||'#4E5570');
    buildLegend(legendId,labels.map((l,i)=>`${l} (${vals[i]})`),cols);
    new Chart(document.getElementById(id),{type:'doughnut',data:{labels,datasets:[{data:vals,backgroundColor:cols,borderWidth:2,borderColor:'#13161E'}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}}}});
  }
  donut('cfChart','cf-legend','CF');
  donut('sfChart','sf-legend','SF');

  const wl={};ISSUES.filter(i=>i.project_key==='CF'&&i.assignee!=='Unassigned').forEach(i=>{wl[i.assignee]=(wl[i.assignee]||0)+1});
  const wls=Object.entries(wl).sort((a,b)=>b[1]-a[1]).slice(0,8);
  const names=wls.map(([n])=>shortName(n));
  buildLegend('wl-legend',names,names.map((_,i)=>AV_COLS[i%AV_COLS.length]));
  const wlH=Math.max(180,wls.length*40+40);
  document.querySelector('#wlChart').parentElement.style.height=wlH+'px';
  new Chart(document.getElementById('wlChart'),{type:'bar',data:{labels:names,datasets:[{label:'Issues',data:wls.map(([,v])=>v),backgroundColor:AV_COLS.slice(0,wls.length),borderRadius:4,borderSkipped:false}]},options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{beginAtZero:true,grid:{color:'rgba(255,255,255,0.04)'},ticks:{color:'#7A8299',font:{size:10}}},y:{grid:{display:false},ticks:{color:'#7A8299',font:{size:10}}}}}});

  const days=Object.keys(TIMELINE).slice(0,14).reverse();
  new Chart(document.getElementById('actChart'),{type:'bar',data:{labels:days.map(d=>d.slice(5)),datasets:[{label:'Movimentações',data:days.map(d=>(TIMELINE[d]||[]).length),backgroundColor:days.map(d=>d===TODAY?'#F0A830':'#4F7CFF'),borderRadius:4,borderSkipped:false}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{y:{beginAtZero:true,grid:{color:'rgba(255,255,255,0.04)'},ticks:{color:'#7A8299',font:{size:10}}},x:{grid:{display:false},ticks:{color:'#7A8299',font:{size:10},autoSkip:false,maxRotation:45}}}}});

  // CF vs SF compare
  const statuses=['Concluído','Em andamento','Revisar','Backlog'];
  const cfData=statuses.map(s=>ISSUES.filter(i=>i.project_key==='CF'&&i.status===s).length);
  const sfData=statuses.map(s=>ISSUES.filter(i=>i.project_key==='SF'&&i.status===s).length);
  buildLegend('compare-legend',['Core Financeiro','Tech Salesforce'],['#4F7CFF','#7B5EA7']);
  new Chart(document.getElementById('compareChart'),{type:'bar',data:{labels:statuses,datasets:[{label:'CF',data:cfData,backgroundColor:'#4F7CFF',borderRadius:4,borderSkipped:false},{label:'SF',data:sfData,backgroundColor:'#7B5EA7',borderRadius:4,borderSkipped:false}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{y:{beginAtZero:true,grid:{color:'rgba(255,255,255,0.04)'},ticks:{color:'#7A8299',font:{size:10}}},x:{grid:{display:false},ticks:{color:'#7A8299',font:{size:10}}}}}});

  // Issue types
  const types={};ISSUES.forEach(i=>{types[i.issuetype]=(types[i.issuetype]||0)+1});
  const tKeys=Object.keys(types).sort((a,b)=>types[b]-types[a]);
  buildLegend('type-legend',tKeys.map((t,i)=>`${t} (${types[t]})`),AV_COLS.slice(0,tKeys.length));
  new Chart(document.getElementById('typeChart'),{type:'doughnut',data:{labels:tKeys,datasets:[{data:tKeys.map(t=>types[t]),backgroundColor:AV_COLS.slice(0,tKeys.length),borderWidth:2,borderColor:'#13161E'}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}}}});
}

// ── Auto-Summary (AI) ────────────────────────────────────────
async function renderSquadSummary(pk){
  const bodyEl=document.getElementById(pk.toLowerCase()+'-summary-body');
  if(bodyEl.classList.contains('loaded'))return;
  bodyEl.textContent='Gerando análise com IA…';
  const s=getStats(pk);
  const pct=s.total>0?Math.round(s.done/s.total*100):0;
  const issues=ISSUES.filter(i=>i.project_key===pk);
  const inProg=issues.filter(i=>i.status==='Em andamento').map(i=>`- ${i.key}: ${i.summary.slice(0,60)}`).join('\\n');
  const inRev=issues.filter(i=>i.status==='Revisar').map(i=>`- ${i.key}: ${i.summary.slice(0,60)}`).join('\\n');
  const done=issues.filter(i=>i.status==='Concluído').slice(0,5).map(i=>`- ${i.key}: ${i.summary.slice(0,60)}`).join('\\n');
  const risks=computeRisks().filter(r=>r.meta===pk||r.meta==='CF/SF');
  const prompt=`Você é PM sênior da Turbi (fintech/mobilidade). Analise este snapshot do squad ${pk==='CF'?'Core Financeiro':'Tech Salesforce'} e escreva um resumo executivo CONCISO em português brasileiro.

DADOS:
- Total: ${s.total} issues | Concluídas: ${s.done} (${pct}%) | Em andamento: ${s.prog} | Revisar: ${s.rev} | Backlog: ${s.back}
- Em andamento:\\n${inProg||'nenhuma'}
- Aguardando revisão:\\n${inRev||'nenhuma'}
- Recentemente concluídas:\\n${done||'nenhuma'}
- Riscos: ${risks.length>0?risks.map(r=>r.text).join('; '):'nenhum identificado'}

Escreva em 4-5 linhas: (1) estado geral, (2) o que está fluindo bem, (3) principal preocupação/risco, (4) recomendação imediata. Tom direto, sem bullet points, sem títulos.`;

  try{
    const resp=await fetch('https://api.anthropic.com/v1/messages',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model:'claude-sonnet-4-20250514',max_tokens:400,messages:[{role:'user',content:prompt}]})});
    const data=await resp.json();
    const txt=data.content?.find(b=>b.type==='text')?.text||'Não foi possível gerar análise.';
    bodyEl.textContent=txt;bodyEl.classList.add('loaded');
  }catch(e){bodyEl.textContent='Análise temporariamente indisponível. Verifique as issues abaixo.';}
}

// ── Static Insights ──────────────────────────────────────────
function renderInsights(pk){
  const s=getStats(pk);const issues=ISSUES.filter(i=>i.project_key===pk);
  const insights=[];
  const pct=s.total>0?Math.round(s.done/s.total*100):0;
  if(pct>=60)insights.push({type:'success',title:'BOA VELOCIDADE',text:`${pct}% das issues concluídas. Sprint em bom ritmo.`});
  else if(pct<30)insights.push({type:'danger',title:'PROGRESSO BAIXO',text:`Apenas ${pct}% concluídas. Revise prioridades e dependências.`});
  const stale=issues.filter(i=>i.status==='Em andamento'&&Math.round((Date.now()-new Date(i.updated))/86400000)>7);
  if(stale.length>0)insights.push({type:'warn',title:'ISSUES ESTAGNADAS',text:`${stale.length} issue(s) em andamento sem movimentação há +7 dias.`});
  const unassign=issues.filter(i=>i.status==='Em andamento'&&i.assignee==='Unassigned');
  if(unassign.length>0)insights.push({type:'danger',title:'SEM RESPONSÁVEL',text:`${unassign.length} issue(s) em andamento sem owner. Atribuição necessária.`});
  if(s.rev>2)insights.push({type:'warn',title:'GARGALO EM REVISÃO',text:`${s.rev} issues aguardando revisão. Pode indicar bottleneck no QA/code review.`});
  const spikes=issues.filter(i=>i.issuetype==='Spike'&&i.status!=='Concluído'&&i.status!=='Cancelado');
  if(spikes.length>0)insights.push({type:'info',title:'SPIKES EM ABERTO',text:`${spikes.length} spike(s) em aberto. Verifique se há decisões bloqueadas.`});
  if(s.back>s.prog*3)insights.push({type:'info',title:'BACKLOG EXTENSO',text:`Backlog (${s.back}) muito maior que o ritmo atual. Considere refinamento.`});
  if(insights.length===0)insights.push({type:'success',title:'TUDO EM ORDEM',text:'Nenhum ponto crítico identificado neste momento.'});
  document.getElementById(pk.toLowerCase()+'-insights').innerHTML=insights.map(i=>`
    <div class="insight-item ${i.type}">
      <div class="insight-title ${i.type}">${i.title}</div>
      <div style="font-size:12px;color:var(--muted);line-height:1.5">${i.text}</div>
    </div>`).join('');
}

// ── AI Calls ─────────────────────────────────────────────────
async function callAI(type){
  const btnMap={task:'btn-task',comment:'btn-comment',sprint:'btn-sprint',daily:'btn-daily'};
  const outMap={task:'t-out',comment:'c-out',sprint:'s-out',daily:'d-out'};
  const btn=document.getElementById(btnMap[type]);
  const outEl=document.getElementById(outMap[type]);
  let prompt='';

  if(type==='task'){
    const sq=document.getElementById('t-sq').value,ti=document.getElementById('t-ti').value.trim(),cx=document.getElementById('t-cx').value.trim(),ty=document.getElementById('t-ty').value;
    if(!ti){toast('Preencha o título');return;}
    prompt=`Você é PM da squad "${sq}" da Turbi (fintech/mobilidade). Escreva uma ${ty} completa para o Jira em português:\\n\\nTítulo: ${ti}\\nContexto: ${cx||'não especificado'}\\n\\nFormate com:\\n## Descrição\\n(3-5 linhas diretas)\\n\\n## Critérios de Aceite\\n- (bullet points)\\n\\n## Definition of Done\\n- (checklist técnico)\\n\\n## Story Points sugeridos: X\\n\\nSeja objetivo e específico para o contexto de fintech/mobilidade.`;
  } else if(type==='comment'){
    const is=document.getElementById('c-is').value.trim(),ty=document.getElementById('c-ty').value,cx=document.getElementById('c-cx').value.trim();
    if(!cx){toast('Preencha o contexto');return;}
    prompt=`Você é dev/PM da Turbi. Escreva um comentário Jira do tipo "${ty}" para a issue ${is||'[ISSUE]'}.\\n\\nContexto: ${cx}\\n\\nRegras: máximo 6 linhas, tom direto, português brasileiro, inclua próximos passos. Não use markdown pesado.`;
  } else if(type==='sprint'){
    const sq=document.getElementById('s-sq').value,au=document.getElementById('s-au').value,de=document.getElementById('s-de').value.trim();
    const pk=sq.includes('CF')?'CF':'SF';const s=getStats(pk);const pct=s.total>0?Math.round(s.done/s.total*100):0;
    prompt=`Você é PM da squad "${sq}" da Turbi. Escreva um resumo de sprint para "${au}" em português.\\n\\nMétricas: ${s.total} issues | ${s.done} concluídas (${pct}%) | ${s.prog} em andamento | ${s.rev} em revisão\\nPrincipais entregas: ${de||'a preencher'}\\n\\nAjuste o tom e profundidade para a audiência "${au}". Destaque impacto de negócio, riscos e próximos passos.`;
  } else if(type==='daily'){
    const sq=document.getElementById('d-sq').value,im=document.getElementById('d-im').value.trim();
    const pk=sq.includes('CF')?'CF':sq.includes('SF')?'SF':null;
    const todayList=(TIMELINE[TODAY]||[]).filter(i=>!pk||i.project_key===pk);
    const lines=todayList.map(i=>`- ${i.key} (${i.status}): ${i.summary.slice(0,50)}`).join('\\n');
    prompt=`Você é PM da squad "${sq}" da Turbi. Escreva o daily standup de hoje (${TODAY}) para o Slack.\\n\\nMovimentações (${todayList.length}):\\n${lines||'nenhuma hoje'}\\nDestaques extras: ${im||'nenhum'}\\n\\nFormato: ontem / hoje / impedimentos. 3 parágrafos curtos, tom Slack casual mas profissional, em português.`;
  }

  btn.disabled=true;btn.innerHTML='<span class="spinner"></span> Gerando…';
  outEl.textContent='';outEl.className='ai-out streaming';

  try{
    const resp=await fetch('https://api.anthropic.com/v1/messages',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model:'claude-sonnet-4-20250514',max_tokens:800,stream:true,messages:[{role:'user',content:prompt}]})});
    const reader=resp.body.getReader();const dec=new TextDecoder();let txt='';
    while(true){
      const{done,value}=await reader.read();if(done)break;
      const chunk=dec.decode(value);
      for(const line of chunk.split('\\n')){
        if(line.startsWith('data:')){
          try{const d=JSON.parse(line.slice(5));if(d.type==='content_block_delta'&&d.delta?.text){txt+=d.delta.text;outEl.textContent=txt;}}catch{}
        }
      }
    }
    outEl.classList.remove('streaming');outEl.classList.add('loaded');
    toast('Gerado com IA ✨');
  }catch(e){outEl.textContent='Erro ao chamar IA. Tente novamente.';outEl.className='ai-out';}
  finally{btn.disabled=false;btn.innerHTML='✨ Gerar com IA';}
}

// ── Metrics KPIs ─────────────────────────────────────────────
function renderMetricsKPIs(){
  const s=getStats(null);
  const active=s.prog+s.rev;
  const velocity=Object.values(TIMELINE).slice(0,7).reduce((a,v)=>a+v.filter(i=>i.status==='Concluído').length,0);
  document.getElementById('kpis-metrics').innerHTML=
    kpiHTML('Taxa de Conclusão',Math.round(s.done/s.total*100)+'%','geral','green')+
    kpiHTML('Issues Ativas',active,'prog+rev','warn')+
    kpiHTML('Backlog Total',s.back,'sem iniciar','blue')+
    kpiHTML('Canceladas',s.can,'descartadas','red')+
    kpiHTML('Vel. 7 Dias',velocity,'concluídas','green');
}

// ── INIT ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded',()=>{
  // Date chips
  const d=new Date(GENERATED_AT);
  document.getElementById('topbar-date').textContent='⏱ '+d.toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
  document.getElementById('footer-ts').textContent=d.toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'})+' · atualizado';
  document.getElementById('footer-total').textContent=`${ISSUES.length} issues · CF+SF`;
  document.getElementById('today-badge').textContent=(TIMELINE[TODAY]||[]).length;

  // Overview KPIs
  renderKPIs('kpis-overview',null);
  renderSquadCard('squad-cf-card','CF');
  renderSquadCard('squad-sf-card','SF');
  renderRecent();
  renderRisks();
  renderDaily();
  renderKPIs('kpis-cf','CF');
  renderKPIs('kpis-sf','SF');
  renderMetricsKPIs();

  // Tables
  filterTable('cf','all',null);
  filterTable('sf','all',null);
  filterTable('all','all',null);
  document.querySelectorAll('.fbtn.active').forEach(b=>b.classList.add('active'));
});
</script>
</body>
</html>
"""


# ── Builder ───────────────────────────────────────────────────
def build_html(issues: list[dict], timeline: dict) -> str:
    now    = datetime.now(timezone(timedelta(hours=-3)))
    today  = now.strftime("%Y-%m-%d")
    gen_at = now.strftime("%Y-%m-%dT%H:%M:%S-03:00")

    html = HTML_TEMPLATE
    html = html.replace("__ISSUES_JSON__",   json.dumps(issues,   ensure_ascii=False))
    html = html.replace("__TIMELINE_JSON__", json.dumps(timeline, ensure_ascii=False))
    html = html.replace("__GENERATED_AT__",  gen_at)
    html = html.replace("__TODAY__",         today)
    return html


# ── Main ──────────────────────────────────────────────────────
def main():
    print("🚗 Turbi PM Dashboard v2 — build iniciado")
    now_br = datetime.now(timezone(timedelta(hours=-3)))
    print(f"   Horário: {now_br.strftime('%d/%m/%Y %H:%M')} (Brasília)")

    print("\n📡 Buscando issues do Jira…")
    issues   = fetch_all()
    timeline = build_timeline(issues, days=30)

    total  = len(issues)
    done   = sum(1 for i in issues if i["status"] == "Concluído")
    prog   = sum(1 for i in issues if i["status"] == "Em andamento")
    today  = now_br.strftime("%Y-%m-%d")

    print(f"\n📊 {total} issues | {done} concluídas | {prog} em andamento")
    print(f"   Hoje ({today}): {len(timeline.get(today, []))} movimentações")

    print("\n🔨 Gerando index.html…")
    html = build_html(issues, timeline)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ index.html gerado ({len(html)//1024}KB)")


if __name__ == "__main__":
    main()
