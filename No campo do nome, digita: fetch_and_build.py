"""
Turbi PM Dashboard — Gerador automático
Busca dados do Jira (CF + SF) e gera o index.html atualizado.
Roda via GitHub Actions todo dia de manhã.
"""

import os
import json
import base64
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from collections import defaultdict

# ── Config ──────────────────────────────────────────────────────────────
JIRA_BASE    = "https://turbi-team.atlassian.net"
JIRA_EMAIL   = os.environ["JIRA_EMAIL"]
JIRA_TOKEN   = os.environ["JIRA_API_TOKEN"]
CLOUD_ID     = "80f3914d-7797-4e17-9f6a-649cd76c789b"

# Credenciais Basic Auth
_creds = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_TOKEN}".encode()).decode()
HEADERS = {
    "Authorization": f"Basic {_creds}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

PROJECTS = {
    "CF": {"name": "Core Financeiro",  "id": "10775", "color": "#0EA5E9", "bg": "#E0F2FE", "emoji": "💰",
           "board": f"{JIRA_BASE}/jira/software/c/projects/CF/boards/1034"},
    "SF": {"name": "Tech Salesforce",  "id": "11209", "color": "#8B5CF6", "bg": "#F5F3FF", "emoji": "🔗",
           "board": f"{JIRA_BASE}/jira/software/c/projects/SF/boards/1599"},
}

FIELDS = "summary,status,assignee,priority,issuetype,project,created,updated"


# ── Jira fetcher ─────────────────────────────────────────────────────────
def jira_search(jql: str, max_results: int = 100) -> list[dict]:
    params = urllib.parse.urlencode({
        "jql": jql,
        "maxResults": max_results,
        "fields": FIELDS,
    })
    url = f"{JIRA_BASE}/rest/api/3/search?{params}"
    req = urllib.request.Request(url, headers=HEADERS)
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


# ── Timeline builder ─────────────────────────────────────────────────────
def build_timeline(issues: list[dict], days: int = 30) -> dict:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    by_day: dict[str, list] = defaultdict(list)
    for i in issues:
        day = i["updated"][:10]
        if day >= cutoff:
            by_day[day].append({
                "key":        i["key"],
                "summary":    i["summary"],
                "status":     i["status"],
                "assignee":   i["assignee"],
                "project_key": i["project_key"],
                "issuetype":  i["issuetype"],
            })
    return dict(sorted(by_day.items(), reverse=True))


# ── Stats ────────────────────────────────────────────────────────────────
def stats(issues: list[dict], project_key: str | None = None) -> dict:
    lst = [i for i in issues if not project_key or i["project_key"] == project_key]
    return {
        "total": len(lst),
        "done":  sum(1 for i in lst if i["status"] == "Concluído"),
        "prog":  sum(1 for i in lst if i["status"] == "Em andamento"),
        "rev":   sum(1 for i in lst if i["status"] == "Revisar"),
        "back":  sum(1 for i in lst if i["status"] in ("Backlog", "Ready To Develop")),
        "can":   sum(1 for i in lst if i["status"] == "Cancelado"),
    }


# ── HTML template ────────────────────────────────────────────────────────
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Turbi PM Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root{--blue:#1A56DB;--dark:#0F172A;--border:#E2E8F0;--done:#10B981;--prog:#F59E0B;--rev:#8B5CF6;--todo:#6B7280}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#F1F5F9;color:var(--dark)}
.app{display:flex;height:100vh;overflow:hidden}
.sidebar{width:216px;background:var(--dark);color:#fff;display:flex;flex-direction:column;flex-shrink:0}
.logo{padding:18px 16px;border-bottom:1px solid rgba(255,255,255,.1)}
.logo-title{font-size:18px;font-weight:700}
.logo-sub{font-size:11px;color:rgba(255,255,255,.35);margin-top:2px}
.nav{padding:10px 8px;flex:1}
.nav-section{font-size:10px;font-weight:600;color:rgba(255,255,255,.3);text-transform:uppercase;letter-spacing:1px;padding:12px 8px 5px}
.nav-item{display:flex;align-items:center;gap:9px;padding:8px 12px;border-radius:8px;cursor:pointer;font-size:13px;color:rgba(255,255,255,.6);transition:all .15s;margin-bottom:1px}
.nav-item:hover{background:rgba(255,255,255,.08);color:#fff}
.nav-item.active{background:var(--blue);color:#fff}
.nav-icon{font-size:15px;width:18px;text-align:center}
.nav-badge{margin-left:auto;background:var(--prog);color:#fff;font-size:10px;font-weight:700;padding:1px 6px;border-radius:10px}
.sidebar-footer{padding:12px 16px;border-top:1px solid rgba(255,255,255,.08);font-size:11px;color:rgba(255,255,255,.3)}
.main{flex:1;overflow-y:auto;display:flex;flex-direction:column}
.topbar{background:#fff;border-bottom:1px solid var(--border);padding:0 24px;height:54px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0}
.topbar-title{font-size:15px;font-weight:600}
.chip{font-size:11px;padding:4px 10px;border-radius:6px;font-weight:500}
.chip-blue{background:#EBF2FF;color:#0052CC}
.chip-gray{background:#F1F5F9;color:#64748B}
.chips{display:flex;gap:8px}
.view{display:none;padding:22px 24px}
.view.active{display:block}
.kpi-row{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:22px}
.kpi{background:#fff;border-radius:12px;padding:16px 18px;border:1px solid var(--border)}
.kpi-label{font-size:11px;font-weight:600;color:#64748B;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px}
.kpi-val{font-size:26px;font-weight:700;line-height:1}
.kpi-sub{font-size:11px;color:#94A3B8;margin-top:3px}
.kpi.g .kpi-val{color:var(--done)}.kpi.b .kpi-val{color:var(--blue)}.kpi.y .kpi-val{color:var(--prog)}
.section-title{font-size:14px;font-weight:600;margin-bottom:14px}
.squad-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px}
.squad-card{background:#fff;border-radius:12px;padding:20px;border:1px solid var(--border);cursor:pointer;transition:all .15s}
.squad-card:hover{box-shadow:0 4px 16px rgba(0,0,0,.08);transform:translateY(-1px)}
.squad-hdr{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px}
.squad-name{font-size:14px;font-weight:600}.squad-key{font-size:11px;color:#94A3B8;margin-top:2px}
.health{width:10px;height:10px;border-radius:50%}
.h-green{background:var(--done)}.h-yellow{background:var(--prog)}.h-red{background:#EF4444}
.prog-bar{height:6px;background:#F1F5F9;border-radius:3px;overflow:hidden;margin-top:6px}
.prog-fill{height:100%;border-radius:3px}
.prog-lbl{display:flex;justify-content:space-between;font-size:11px;color:#64748B}
.squad-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:12px}
.stat{background:#F8FAFC;border-radius:8px;padding:6px 0;text-align:center}
.stat-n{font-size:15px;font-weight:700}.stat-l{font-size:10px;color:#94A3B8;margin-top:1px}
.stat-n.g{color:var(--done)}.stat-n.y{color:var(--prog)}.stat-n.b{color:var(--blue)}
.card{background:#fff;border-radius:12px;border:1px solid var(--border);overflow:hidden;margin-bottom:20px}
.card-hdr{padding:14px 18px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;gap:10px}
.card-title{font-size:13px;font-weight:600;white-space:nowrap}
.filter-row{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.search{padding:5px 10px;border:1px solid var(--border);border-radius:6px;font-size:12px;width:180px;outline:none}
.search:focus{border-color:var(--blue)}
.fbtn{font-size:11px;padding:4px 10px;border-radius:6px;border:1px solid var(--border);background:#fff;cursor:pointer;color:#64748B}
.fbtn.active,.fbtn:hover{background:var(--blue);color:#fff;border-color:var(--blue)}
table{width:100%;border-collapse:collapse}
th{text-align:left;padding:9px 14px;font-size:10px;font-weight:600;color:#64748B;text-transform:uppercase;letter-spacing:.5px;background:#FAFAFA;border-bottom:1px solid var(--border)}
td{padding:10px 14px;font-size:12.5px;border-bottom:1px solid #F1F5F9;vertical-align:middle}
tr:last-child td{border-bottom:none}
tr:hover td{background:#F8FAFC}
.ikey a{font-family:monospace;font-size:12px;color:var(--blue);font-weight:600;text-decoration:none}
.ikey a:hover{text-decoration:underline}
.badge{display:inline-flex;align-items:center;padding:3px 8px;border-radius:20px;font-size:11px;font-weight:600;white-space:nowrap}
.s-done{background:#ECFDF5;color:#059669}.s-prog{background:#FFFBEB;color:#D97706}
.s-rev{background:#F5F3FF;color:#7C3AED}.s-todo{background:#F1F5F9;color:#475569}
.s-can{background:#F9FAFB;color:#9CA3AF}
.avatar{width:22px;height:22px;border-radius:50%;color:#fff;font-size:9px;font-weight:700;display:inline-flex;align-items:center;justify-content:center;flex-shrink:0}
.av-cell{display:inline-flex;align-items:center;gap:5px}
.proj-tag{font-size:11px;padding:2px 8px;border-radius:10px;font-weight:600}
.timeline-day{margin-bottom:20px}
.day-hdr{display:flex;align-items:center;gap:10px;margin-bottom:10px}
.day-date{font-size:13px;font-weight:700}
.day-cnt{font-size:11px;color:#64748B;background:#F1F5F9;padding:2px 8px;border-radius:10px}
.day-today-badge{background:var(--blue);color:#fff}
.day-line{flex:1;height:1px;background:var(--border)}
.day-items{display:flex;flex-direction:column;gap:6px}
.day-item{display:flex;align-items:center;gap:10px;background:#fff;border:1px solid var(--border);border-radius:8px;padding:10px 14px}
.day-item:hover{border-color:#CBD5E1}
.day-item-key a{font-family:monospace;font-size:11px;color:var(--blue);font-weight:600;text-decoration:none}
.day-item-key a:hover{text-decoration:underline}
.day-item-title{flex:1;font-size:12.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.day-item-right{display:flex;align-items:center;gap:8px;flex-shrink:0}
.today-box{background:#FFF7ED;border:1px solid #FED7AA;border-radius:12px;padding:14px 18px;margin-bottom:18px}
.today-box-title{font-size:13px;font-weight:600;color:#9A3412;margin-bottom:10px}
.today-stats{display:flex;gap:20px}
.today-stat-n{font-size:20px;font-weight:700}.today-stat-l{font-size:11px;color:#64748B}
.metrics-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:20px}
.chart-card{background:#fff;border-radius:12px;border:1px solid var(--border);padding:18px}
.chart-title{font-size:13px;font-weight:600;margin-bottom:14px}
.chart-wrap{position:relative;height:210px}
.ai-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.ai-card{background:#fff;border-radius:12px;border:1px solid var(--border);overflow:hidden}
.ai-card-hdr{padding:14px 18px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px;background:linear-gradient(135deg,#EFF6FF,#F5F3FF)}
.ai-card-icon{font-size:18px}.ai-card-title{font-size:13px;font-weight:600}.ai-card-sub{font-size:11px;color:#64748B}
.ai-card-body{padding:18px}
.flabel{font-size:12px;font-weight:600;color:#374151;margin-bottom:4px;display:block}
.fgroup{margin-bottom:12px}
.finput,.fselect,.ftextarea{width:100%;padding:7px 10px;border:1px solid var(--border);border-radius:7px;font-size:12.5px;outline:none;font-family:inherit}
.finput:focus,.fselect:focus,.ftextarea:focus{border-color:var(--blue)}
.ftextarea{resize:vertical;min-height:70px}
.ai-out{background:#F8FAFC;border:1px solid var(--border);border-radius:8px;padding:10px 12px;font-size:12px;min-height:70px;white-space:pre-wrap;line-height:1.6;color:#94A3B8}
.ai-out.filled{color:#374151}
.btn{padding:7px 16px;border-radius:7px;font-size:12.5px;font-weight:600;cursor:pointer;border:none;display:inline-flex;align-items:center;gap:5px}
.btn-p{background:var(--blue);color:#fff}.btn-p:hover{background:#1D4ED8}
.btn-s{background:#F1F5F9;color:#374151;border:1px solid var(--border)}.btn-s:hover{background:#E2E8F0}
.btn-row{display:flex;gap:7px;margin-top:10px}
.toast{position:fixed;bottom:20px;right:20px;background:#0F172A;color:#fff;padding:10px 16px;border-radius:9px;font-size:13px;z-index:9999;opacity:0;transform:translateY(8px);transition:all .25s;pointer-events:none}
.toast.show{opacity:1;transform:translateY(0)}
</style>
</head>
<body>
<div class="app">
  <div class="sidebar">
    <div class="logo">
      <div class="logo-title">🚗 Turbi</div>
      <div class="logo-sub">PM Dashboard · CF & SF</div>
    </div>
    <nav class="nav">
      <div class="nav-section">Visão</div>
      <div class="nav-item active" onclick="show('overview',this)"><span class="nav-icon">📊</span>Overview</div>
      <div class="nav-item" onclick="show('daily',this)"><span class="nav-icon">📅</span>Resumo Diário<span class="nav-badge" id="today-badge">0</span></div>
      <div class="nav-section">Projetos</div>
      <div class="nav-item" onclick="show('cf',this)"><span class="nav-icon">💰</span>Core Financeiro</div>
      <div class="nav-item" onclick="show('sf',this)"><span class="nav-icon">🔗</span>Tech Salesforce</div>
      <div class="nav-section">Ferramentas</div>
      <div class="nav-item" onclick="show('issues',this)"><span class="nav-icon">📋</span>Todas as Issues</div>
      <div class="nav-item" onclick="show('metrics',this)"><span class="nav-icon">📈</span>Métricas</div>
      <div class="nav-item" onclick="show('ai',this)"><span class="nav-icon">✨</span>IA Assistente</div>
    </nav>
    <div class="sidebar-footer" id="footer-info">Carregando…</div>
  </div>
  <div class="main">
    <div class="topbar">
      <div class="topbar-title" id="page-title">Visão Geral</div>
      <div class="chips">
        <span class="chip chip-blue">🔗 turbi-team.atlassian.net</span>
        <span class="chip chip-gray" id="topbar-date">…</span>
      </div>
    </div>

    <!-- OVERVIEW -->
    <div id="view-overview" class="view active">
      <div class="kpi-row" id="overview-kpis"></div>
      <div class="section-title">Squads</div>
      <div class="squad-grid" id="squad-cards"></div>
    </div>

    <!-- DAILY -->
    <div id="view-daily" class="view">
      <div class="today-box" id="today-box"></div>
      <div id="timeline-container"></div>
    </div>

    <!-- CF -->
    <div id="view-cf" class="view">
      <div class="kpi-row" id="cf-kpis"></div>
      <div class="card">
        <div class="card-hdr">
          <div class="card-title">💰 Core Financeiro</div>
          <div class="filter-row">
            <input class="search" placeholder="🔍 Buscar…" oninput="filter('cf','',this.value)"/>
            <button class="fbtn active" onclick="filter('cf','all',null,this)">Todas</button>
            <button class="fbtn" onclick="filter('cf','Em andamento',null,this)">Em andamento</button>
            <button class="fbtn" onclick="filter('cf','Revisar',null,this)">Revisar</button>
            <button class="fbtn" onclick="filter('cf','Concluído',null,this)">Concluído</button>
          </div>
        </div>
        <table><thead><tr><th>Chave</th><th>Título</th><th>Status</th><th>Tipo</th><th>Responsável</th><th>Atualizado</th></tr></thead>
        <tbody id="cf-tbody"></tbody></table>
      </div>
    </div>

    <!-- SF -->
    <div id="view-sf" class="view">
      <div class="kpi-row" id="sf-kpis"></div>
      <div class="card">
        <div class="card-hdr">
          <div class="card-title">🔗 Tech Salesforce</div>
          <div class="filter-row">
            <input class="search" placeholder="🔍 Buscar…" oninput="filter('sf','',this.value)"/>
            <button class="fbtn active" onclick="filter('sf','all',null,this)">Todas</button>
            <button class="fbtn" onclick="filter('sf','Em andamento',null,this)">Em andamento</button>
            <button class="fbtn" onclick="filter('sf','Concluído',null,this)">Concluído</button>
          </div>
        </div>
        <table><thead><tr><th>Chave</th><th>Título</th><th>Status</th><th>Tipo</th><th>Responsável</th><th>Atualizado</th></tr></thead>
        <tbody id="sf-tbody"></tbody></table>
      </div>
    </div>

    <!-- ALL ISSUES -->
    <div id="view-issues" class="view">
      <div class="card">
        <div class="card-hdr">
          <div class="card-title">Todas as Issues</div>
          <div class="filter-row">
            <input class="search" placeholder="🔍 Buscar…" oninput="filter('all','',this.value)"/>
            <button class="fbtn active" onclick="filter('all','all',null,this)">Todas</button>
            <button class="fbtn" onclick="filter('all','Em andamento',null,this)">⚡ Andamento</button>
            <button class="fbtn" onclick="filter('all','Revisar',null,this)">👀 Revisar</button>
            <button class="fbtn" onclick="filter('all','Concluído',null,this)">✅ Concluído</button>
            <button class="fbtn" onclick="filter('all','Backlog',null,this)">📥 Backlog</button>
          </div>
        </div>
        <table><thead><tr><th>Chave</th><th>Título</th><th>Squad</th><th>Status</th><th>Tipo</th><th>Responsável</th><th>Atualizado</th></tr></thead>
        <tbody id="all-tbody"></tbody></table>
      </div>
    </div>

    <!-- METRICS -->
    <div id="view-metrics" class="view">
      <div class="metrics-grid">
        <div class="chart-card"><div class="chart-title">Status — Core Financeiro</div><div class="chart-wrap"><canvas id="cfChart"></canvas></div></div>
        <div class="chart-card"><div class="chart-title">Status — Tech Salesforce</div><div class="chart-wrap"><canvas id="sfChart"></canvas></div></div>
      </div>
      <div class="metrics-grid">
        <div class="chart-card"><div class="chart-title">Workload por Responsável (CF)</div><div class="chart-wrap"><canvas id="wlChart"></canvas></div></div>
        <div class="chart-card"><div class="chart-title">Atividade por Dia (últimas 2 semanas)</div><div class="chart-wrap"><canvas id="actChart"></canvas></div></div>
      </div>
    </div>

    <!-- AI -->
    <div id="view-ai" class="view">
      <div style="font-size:12.5px;color:#64748B;margin-bottom:18px;">Gere prompts prontos para usar no Claude. Preencha → copie → cole no Claude.</div>
      <div class="ai-grid">
        <div class="ai-card">
          <div class="ai-card-hdr"><div class="ai-card-icon">📝</div><div><div class="ai-card-title">Escrever Task</div><div class="ai-card-sub">Descrição, critérios de aceite e DoD</div></div></div>
          <div class="ai-card-body">
            <div class="fgroup"><label class="flabel">Squad</label><select class="fselect" id="t-sq"><option>Core Financeiro (CF)</option><option>Tech Salesforce (SF)</option></select></div>
            <div class="fgroup"><label class="flabel">Título</label><input class="finput" id="t-ti" placeholder="Ex: Implementar conciliação automática Adyen"/></div>
            <div class="fgroup"><label class="flabel">Contexto</label><textarea class="ftextarea" id="t-cx" placeholder="O que precisa ser feito e por quê…"></textarea></div>
            <div class="fgroup"><label class="flabel">Tipo</label><select class="fselect" id="t-ty"><option>História</option><option>Tarefa Técnica</option><option>Bug</option><option>Spike</option></select></div>
            <button class="btn btn-p" onclick="genTask()">✨ Gerar Prompt</button>
            <div style="margin-top:12px"><label class="flabel">Prompt:</label><div class="ai-out" id="t-out" style="margin-top:5px">Preencha os campos acima.</div><div class="btn-row"><button class="btn btn-s" onclick="cp('t-out')">📋 Copiar</button></div></div>
          </div>
        </div>
        <div class="ai-card">
          <div class="ai-card-hdr"><div class="ai-card-icon">💬</div><div><div class="ai-card-title">Comentário Jira</div><div class="ai-card-sub">Atualização, bloqueio ou handoff</div></div></div>
          <div class="ai-card-body">
            <div class="fgroup"><label class="flabel">Issue (ex: CF-320)</label><input class="finput" id="c-is" placeholder="CF-320"/></div>
            <div class="fgroup"><label class="flabel">Tipo</label><select class="fselect" id="c-ty"><option>Atualização de progresso</option><option>Reportar bloqueio</option><option>Handoff para QA</option><option>Resolução de bloqueio</option><option>Pedido de revisão</option></select></div>
            <div class="fgroup"><label class="flabel">Contexto</label><textarea class="ftextarea" id="c-cx" placeholder="O que aconteceu…"></textarea></div>
            <button class="btn btn-p" onclick="genComment()">✨ Gerar Prompt</button>
            <div style="margin-top:12px"><label class="flabel">Prompt:</label><div class="ai-out" id="c-out" style="margin-top:5px">Preencha os campos acima.</div><div class="btn-row"><button class="btn btn-s" onclick="cp('c-out')">📋 Copiar</button></div></div>
          </div>
        </div>
        <div class="ai-card">
          <div class="ai-card-hdr"><div class="ai-card-icon">📊</div><div><div class="ai-card-title">Resumo de Sprint</div><div class="ai-card-sub">Relatório para stakeholders</div></div></div>
          <div class="ai-card-body">
            <div class="fgroup"><label class="flabel">Squad</label><select class="fselect" id="s-sq"><option>Core Financeiro (CF)</option><option>Tech Salesforce (SF)</option></select></div>
            <div class="fgroup"><label class="flabel">Audiência</label><select class="fselect" id="s-au"><option>C-Level</option><option>Stakeholders de produto</option><option>Time técnico</option><option>Slack do time</option></select></div>
            <div class="fgroup"><label class="flabel">Principais entregas</label><textarea class="ftextarea" id="s-de" placeholder="Features ou fixes entregues…"></textarea></div>
            <button class="btn btn-p" onclick="genSprint()">✨ Gerar Prompt</button>
            <div style="margin-top:12px"><label class="flabel">Prompt:</label><div class="ai-out" id="s-out" style="margin-top:5px">Preencha os campos acima.</div><div class="btn-row"><button class="btn btn-s" onclick="cp('s-out')">📋 Copiar</button></div></div>
          </div>
        </div>
        <div class="ai-card">
          <div class="ai-card-hdr"><div class="ai-card-icon">☀️</div><div><div class="ai-card-title">Daily Standup</div><div class="ai-card-sub">Resumo do dia para o time</div></div></div>
          <div class="ai-card-body">
            <div class="fgroup"><label class="flabel">Squad</label><select class="fselect" id="d-sq"><option>Core Financeiro (CF)</option><option>Tech Salesforce (SF)</option><option>CF + SF</option></select></div>
            <div class="fgroup"><label class="flabel">Impedimentos / destaques</label><textarea class="ftextarea" id="d-im" placeholder="Algo além das issues do Jira?"></textarea></div>
            <button class="btn btn-p" onclick="genDaily()">✨ Gerar Prompt</button>
            <div style="margin-top:12px"><label class="flabel">Prompt:</label><div class="ai-out" id="d-out" style="margin-top:5px">Preencha os campos acima.</div><div class="btn-row"><button class="btn btn-s" onclick="cp('d-out')">📋 Copiar</button></div></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
<div class="toast" id="toast"></div>

<script>
const ISSUES = __ISSUES_JSON__;
const TIMELINE = __TIMELINE_JSON__;
const GENERATED_AT = "__GENERATED_AT__";
const TODAY = "__TODAY__";

const PROJ = {
  CF:{color:'#0EA5E9',bg:'#E0F2FE',board:'https://turbi-team.atlassian.net/jira/software/c/projects/CF/boards/1034'},
  SF:{color:'#8B5CF6',bg:'#F5F3FF',board:'https://turbi-team.atlassian.net/jira/software/c/projects/SF/boards/1599'}
};
const STATUS_CLS = {'Concluído':'s-done','Em andamento':'s-prog','Revisar':'s-rev','Backlog':'s-todo','Ready To Develop':'s-todo','Cancelado':'s-can'};
const STATUS_ICON = {'Concluído':'✅','Em andamento':'⚡','Revisar':'👀','Backlog':'📥','Ready To Develop':'📋','Cancelado':'❌'};
const AV_COLS = ['#0EA5E9','#8B5CF6','#F59E0B','#10B981','#EF4444','#06B6D4','#EC4899'];
const TITLES = {overview:'Visão Geral',daily:'Resumo Diário',cf:'Core Financeiro',sf:'Tech Salesforce',issues:'Todas as Issues',metrics:'Métricas',ai:'IA Assistente'};
const FILTERS = {cf:{status:'all',search:''},sf:{status:'all',search:''},all:{status:'all',search:''}};

function badge(s){const c=STATUS_CLS[s]||'s-todo';const i=STATUS_ICON[s]||'•';return `<span class="badge ${c}">${i} ${s}</span>`}
function avatar(n){
  if(!n||n==='Unassigned')return`<div class="avatar" style="background:#CBD5E1;color:#64748B">?</div>`;
  const p=n.trim().split(/[\s.]+/);
  const init=p.length>=2?p[0][0]+p[p.length-1][0]:n.substring(0,2);
  const c=AV_COLS[n.charCodeAt(0)%AV_COLS.length];
  return`<div class="avatar" style="background:${c}">${init.toUpperCase()}</div>`;
}
function fmtDate(iso){if(!iso)return'—';const d=new Date(iso);return d.toLocaleDateString('pt-BR',{day:'2-digit',month:'2-digit'})}
function fmtDateLong(s){
  const d=new Date(s+'T12:00:00');
  const t=new Date(TODAY+'T12:00:00');
  const diff=Math.round((t-d)/86400000);
  if(diff===0)return'Hoje';if(diff===1)return'Ontem';
  return d.toLocaleDateString('pt-BR',{weekday:'long',day:'2-digit',month:'long'});
}
function projTag(k){const p=PROJ[k]||{color:'#64748B',bg:'#F1F5F9'};return`<span class="proj-tag" style="background:${p.bg};color:${p.color}">${k}</span>`}
function shortName(n){if(!n||n==='Unassigned')return'<i style="color:#94A3B8">—</i>';const p=n.trim().split(/[\s.]+/);return p.length>=2?p[0]+' '+p[p.length-1]:p[0]}
function getStats(pk){
  const l=ISSUES.filter(i=>!pk||i.project_key===pk);
  return{total:l.length,done:l.filter(i=>i.status==='Concluído').length,prog:l.filter(i=>i.status==='Em andamento').length,
    rev:l.filter(i=>i.status==='Revisar').length,back:l.filter(i=>['Backlog','Ready To Develop'].includes(i.status)).length};
}

function show(name,el){
  document.querySelectorAll('.view').forEach(v=>v.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));
  document.getElementById('view-'+name).classList.add('active');
  el.classList.add('active');
  document.getElementById('page-title').textContent=TITLES[name]||name;
  if(name==='metrics')setTimeout(renderCharts,60);
}

function renderOverviewKPIs(){
  const s=getStats(null);
  const pct=s.total>0?Math.round(s.done/s.total*100):0;
  document.getElementById('overview-kpis').innerHTML=`
    <div class="kpi b"><div class="kpi-label">Total Issues</div><div class="kpi-val">${s.total}</div><div class="kpi-sub">CF + SF</div></div>
    <div class="kpi g"><div class="kpi-label">Concluídas</div><div class="kpi-val">${s.done}</div><div class="kpi-sub">${pct}%</div></div>
    <div class="kpi y"><div class="kpi-label">Em Andamento</div><div class="kpi-val">${s.prog}</div><div class="kpi-sub"></div></div>
    <div class="kpi"><div class="kpi-label">Backlog</div><div class="kpi-val">${s.back}</div><div class="kpi-sub"></div></div>
    <div class="kpi"><div class="kpi-label">Hoje</div><div class="kpi-val">${(TIMELINE[TODAY]||[]).length}</div><div class="kpi-sub">movimentações</div></div>`;
}

function renderProjectKPIs(containerId,pk){
  const s=getStats(pk);const pct=s.total>0?Math.round(s.done/s.total*100):0;
  document.getElementById(containerId).innerHTML=`
    <div class="kpi b"><div class="kpi-label">Total</div><div class="kpi-val">${s.total}</div><div class="kpi-sub">issues</div></div>
    <div class="kpi g"><div class="kpi-label">Concluídas</div><div class="kpi-val">${s.done}</div><div class="kpi-sub">${pct}%</div></div>
    <div class="kpi y"><div class="kpi-label">Em andamento</div><div class="kpi-val">${s.prog}</div><div class="kpi-sub"></div></div>
    <div class="kpi"><div class="kpi-label">Revisar</div><div class="kpi-val">${s.rev}</div><div class="kpi-sub"></div></div>
    <div class="kpi"><div class="kpi-label">Backlog</div><div class="kpi-val">${s.back}</div><div class="kpi-sub"></div></div>`;
}

function renderSquadCards(){
  const c=document.getElementById('squad-cards');
  ['CF','SF'].forEach(k=>{
    const p=PROJ[k];const s=getStats(k);
    const pct=s.total>0?Math.round(s.done/s.total*100):0;
    const h=pct>=60?'h-green':pct>=30?'h-yellow':'h-red';
    const names={CF:'💰 Core Financeiro',SF:'🔗 Tech Salesforce'};
    const div=document.createElement('div');
    div.className='squad-card';
    div.innerHTML=`<div class="squad-hdr"><div><div class="squad-name" style="color:${p.color}">${names[k]}</div><div class="squad-key">${k}</div></div><div class="health ${h}"></div></div>
      <div><div class="prog-lbl"><span>Progresso</span><span style="font-weight:700">${pct}%</span></div><div class="prog-bar"><div class="prog-fill" style="width:${pct}%;background:${p.color}"></div></div></div>
      <div class="squad-stats">
        <div class="stat"><div class="stat-n g">${s.done}</div><div class="stat-l">Feito</div></div>
        <div class="stat"><div class="stat-n y">${s.prog}</div><div class="stat-l">Andamento</div></div>
        <div class="stat"><div class="stat-n b">${s.rev}</div><div class="stat-l">Revisar</div></div>
        <div class="stat"><div class="stat-n">${s.back}</div><div class="stat-l">Backlog</div></div>
      </div>`;
    div.onclick=()=>window.open(p.board,'_blank');
    c.appendChild(div);
  });
}

function renderDaily(){
  const todayItems=TIMELINE[TODAY]||[];
  const done=todayItems.filter(i=>i.status==='Concluído').length;
  const prog=todayItems.filter(i=>['Em andamento','Revisar'].includes(i.status)).length;
  const back=todayItems.filter(i=>['Backlog','Ready To Develop'].includes(i.status)).length;
  const todayFmt=new Date(TODAY+'T12:00:00').toLocaleDateString('pt-BR',{day:'2-digit',month:'long',year:'numeric'});
  document.getElementById('today-box').innerHTML=`
    <div class="today-box-title">☀️ Hoje — ${todayFmt} · ${todayItems.length} movimentações</div>
    <div class="today-stats">
      <div class="today-stat"><div class="today-stat-n" style="color:var(--done)">${done}</div><div class="today-stat-l">Concluídas</div></div>
      <div class="today-stat"><div class="today-stat-n" style="color:var(--prog)">${prog}</div><div class="today-stat-l">Em andamento</div></div>
      <div class="today-stat"><div class="today-stat-n" style="color:#64748B">${back}</div><div class="today-stat-l">Backlog</div></div>
    </div>`;
  const container=document.getElementById('timeline-container');
  container.innerHTML='';
  Object.entries(TIMELINE).forEach(([day,items])=>{
    const isToday=day===TODAY;
    const doneN=items.filter(i=>i.status==='Concluído').length;
    const progN=items.filter(i=>['Em andamento','Revisar'].includes(i.status)).length;
    const sec=document.createElement('div');sec.className='timeline-day';
    sec.innerHTML=`<div class="day-hdr">
      <div class="day-date">${fmtDateLong(day)}</div>
      <div class="day-cnt ${isToday?'day-today-badge':''}">${items.length}</div>
      ${doneN?`<div class="day-cnt" style="background:#ECFDF5;color:#059669">${doneN} ✅</div>`:''}
      ${progN?`<div class="day-cnt" style="background:#FFFBEB;color:#D97706">${progN} ⚡</div>`:''}
      <div class="day-line"></div></div>
      <div class="day-items">${items.map(i=>`
        <div class="day-item">
          <div class="day-item-key"><a href="https://turbi-team.atlassian.net/browse/${i.key}" target="_blank">${i.key}</a></div>
          ${projTag(i.project_key)}
          <div class="day-item-title" title="${i.summary}">${i.summary}</div>
          <div class="day-item-right">${badge(i.status)}<div class="av-cell">${avatar(i.assignee)}</div></div>
        </div>`).join('')}
      </div>`;
    container.appendChild(sec);
  });
}

function rowHTML(i,showProj=false){
  return`<tr>
    <td class="ikey"><a href="https://turbi-team.atlassian.net/browse/${i.key}" target="_blank">${i.key}</a></td>
    <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${i.summary}">${i.summary}</td>
    ${showProj?`<td>${projTag(i.project_key)}</td>`:''}
    <td>${badge(i.status)}</td>
    <td style="font-size:11px;color:#94A3B8">${i.issuetype}</td>
    <td><div class="av-cell">${avatar(i.assignee)}<span style="font-size:12px">${shortName(i.assignee)}</span></div></td>
    <td style="font-size:11.5px;color:#64748B">${fmtDate(i.updated)}</td>
  </tr>`;
}

function renderTable(tbodyId,list,showProj=false){
  document.getElementById(tbodyId).innerHTML=list.map(i=>rowHTML(i,showProj)).join('');
}

function filter(view,status,search,btn){
  if(status!==null&&status!==undefined){
    FILTERS[view].status=status;
    if(btn){btn.closest('.filter-row').querySelectorAll('.fbtn').forEach(b=>b.classList.remove('active'));btn.classList.add('active')}
  }
  if(search!==null&&search!==undefined) FILTERS[view].search=search.toLowerCase();
  const pk=view==='cf'?'CF':view==='sf'?'SF':null;
  const showProj=view==='all';
  let list=ISSUES.filter(i=>!pk||i.project_key===pk);
  if(FILTERS[view].status!=='all') list=list.filter(i=>i.status===FILTERS[view].status);
  if(FILTERS[view].search) list=list.filter(i=>i.summary.toLowerCase().includes(FILTERS[view].search)||i.key.toLowerCase().includes(FILTERS[view].search)||i.assignee.toLowerCase().includes(FILTERS[view].search));
  renderTable(view+'-tbody',list,showProj);
}

let chartsOk=false;
function renderCharts(){
  if(chartsOk)return;chartsOk=true;
  const SC={'Concluído':'#10B981','Em andamento':'#F59E0B','Revisar':'#8B5CF6','Backlog':'#CBD5E1','Ready To Develop':'#93C5FD','Cancelado':'#E5E7EB'};
  function donut(id,pk){
    const counts={};ISSUES.filter(i=>i.project_key===pk).forEach(i=>{counts[i.status]=(counts[i.status]||0)+1});
    new Chart(document.getElementById(id),{type:'doughnut',data:{labels:Object.keys(counts),datasets:[{data:Object.values(counts),backgroundColor:Object.keys(counts).map(s=>SC[s]||'#CBD5E1'),borderWidth:2,borderColor:'#fff'}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'right',labels:{font:{size:11},boxWidth:11}}}}});
  }
  donut('cfChart','CF');donut('sfChart','SF');
  const wl={};ISSUES.filter(i=>i.project_key==='CF'&&i.assignee!=='Unassigned').forEach(i=>{wl[i.assignee]=(wl[i.assignee]||0)+1});
  const wls=Object.entries(wl).sort((a,b)=>b[1]-a[1]).slice(0,8);
  new Chart(document.getElementById('wlChart'),{type:'bar',data:{labels:wls.map(([n])=>n.split(/[\s.]+/).slice(0,2).join(' ')),datasets:[{label:'Issues',data:wls.map(([,v])=>v),backgroundColor:'#0EA5E9',borderRadius:5,borderSkipped:false}]},options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{beginAtZero:true,grid:{color:'#F1F5F9'}},y:{grid:{display:false},ticks:{font:{size:10}}}}}});
  const days=Object.keys(TIMELINE).slice(0,10).reverse();
  new Chart(document.getElementById('actChart'),{type:'bar',data:{labels:days.map(d=>d.slice(5)),datasets:[{label:'Issues',data:days.map(d=>(TIMELINE[d]||[]).length),backgroundColor:days.map(d=>d===TODAY?'#F59E0B':'#0EA5E9'),borderRadius:5,borderSkipped:false}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{y:{beginAtZero:true,grid:{color:'#F1F5F9'}},x:{grid:{display:false}}}}});
}

function genTask(){
  const sq=document.getElementById('t-sq').value,ti=document.getElementById('t-ti').value.trim(),cx=document.getElementById('t-cx').value.trim(),ty=document.getElementById('t-ty').value;
  if(!ti){toast('Preencha o título');return}
  setOut('t-out',`Você é PM da squad "${sq}" da Turbi. Escreva uma ${ty} completa para o Jira:\n\nTítulo: ${ti}\nContexto: ${cx||'Não especificado'}\n\nGere:\n1. Descrição (3-5 linhas)\n2. Critérios de Aceite (bullet points)\n3. DoD (checklist técnico)\n4. Story Points sugeridos\n\nPortuguês, objetivo.`);
}
function genComment(){
  const is=document.getElementById('c-is').value.trim(),ty=document.getElementById('c-ty').value,cx=document.getElementById('c-cx').value.trim();
  if(!cx){toast('Preencha o contexto');return}
  setOut('c-out',`Você é dev/PM da Turbi. Comentário do tipo "${ty}" para issue ${is||'[ISSUE]'}.\n\nContexto: ${cx}\n\nComentário claro e objetivo (máx. 6 linhas), com próximos passos. Português.`);
}
function genSprint(){
  const sq=document.getElementById('s-sq').value,au=document.getElementById('s-au').value,de=document.getElementById('s-de').value.trim();
  const pk=sq.includes('CF')?'CF':'SF';const s=getStats(pk);const pct=Math.round(s.done/s.total*100)||0;
  setOut('s-out',`PM da squad "${sq}" da Turbi. Resumo de sprint para "${au}".\n\nMétricas: ${s.total} issues, ${s.done} concluídas (${pct}%), ${s.prog} em andamento.\nEntregas: ${de||'A preencher'}\n\nDestaque valor, mencione riscos, próximos passos. Tom para ${au}.`);
}
function genDaily(){
  const sq=document.getElementById('d-sq').value,im=document.getElementById('d-im').value.trim();
  const pk=sq.includes('CF')?'CF':sq.includes('SF')?'SF':null;
  const todayList=(TIMELINE[TODAY]||[]).filter(i=>!pk||i.project_key===pk);
  const lines=todayList.map(i=>`- ${i.key} | ${i.status} | ${i.summary}`).join('\n');
  setOut('d-out',`PM da squad "${sq}" da Turbi. Daily standup de ${TODAY}.\n\nMovimentações de hoje (${todayList.length}):\n${lines||'Nenhuma'}\n\nDestaques: ${im||'Nenhum'}\n\nFormato: 3 parágrafos (ontem/hoje/impedimentos). Tom Slack.`);
}
function setOut(id,t){const e=document.getElementById(id);e.textContent=t;e.classList.add('filled');toast('Prompt gerado! Cole no Claude ✨')}
function cp(id){const t=document.getElementById(id).textContent;if(t.includes('Preencha')){toast('Gere um prompt primeiro');return}navigator.clipboard.writeText(t).then(()=>toast('Copiado! ✅'))}
function toast(msg){const e=document.getElementById('toast');e.textContent=msg;e.classList.add('show');setTimeout(()=>e.classList.remove('show'),2400)}

document.addEventListener('DOMContentLoaded',()=>{
  const d=new Date(GENERATED_AT);
  document.getElementById('topbar-date').textContent='📅 Atualizado: '+d.toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
  document.getElementById('footer-info').textContent=`${GENERATED_AT.slice(0,10)} · ${ISSUES.length} issues`;
  document.getElementById('today-badge').textContent=(TIMELINE[TODAY]||[]).length;
  renderOverviewKPIs();
  renderSquadCards();
  renderDaily();
  renderProjectKPIs('cf-kpis','CF');
  renderProjectKPIs('sf-kpis','SF');
  renderTable('cf-tbody',ISSUES.filter(i=>i.project_key==='CF'));
  renderTable('sf-tbody',ISSUES.filter(i=>i.project_key==='SF'));
  renderTable('all-tbody',ISSUES,true);
});
</script>
</body>
</html>"""


# ── Builder ──────────────────────────────────────────────────────────────
def build_html(issues: list[dict], timeline: dict) -> str:
    now    = datetime.now(timezone(timedelta(hours=-3)))  # horário de Brasília
    today  = now.strftime("%Y-%m-%d")
    gen_at = now.strftime("%Y-%m-%dT%H:%M:%S-03:00")

    html = HTML_TEMPLATE
    html = html.replace("__ISSUES_JSON__",   json.dumps(issues,   ensure_ascii=False))
    html = html.replace("__TIMELINE_JSON__", json.dumps(timeline, ensure_ascii=False))
    html = html.replace("__GENERATED_AT__",  gen_at)
    html = html.replace("__TODAY__",         today)
    return html


# ── Main ─────────────────────────────────────────────────────────────────
def main():
    print("🚗 Turbi PM Dashboard — build iniciado")
    print(f"   Horário: {datetime.now(timezone(timedelta(hours=-3))).strftime('%d/%m/%Y %H:%M')} (Brasília)")

    print("\n📡 Buscando issues do Jira…")
    issues   = fetch_all()
    timeline = build_timeline(issues, days=30)

    s = stats(issues)
    print(f"\n📊 Resumo: {s['total']} issues | {s['done']} concluídas | {s['prog']} em andamento | {s['back']} backlog")

    today = datetime.now(timezone(timedelta(hours=-3))).strftime("%Y-%m-%d")
    print(f"   Hoje ({today}): {len(timeline.get(today, []))} movimentações")

    print("\n🔨 Gerando index.html…")
    html = build_html(issues, timeline)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ index.html gerado ({len(html)//1024}KB)")


if __name__ == "__main__":
    main()
