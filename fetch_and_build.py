#!/usr/bin/env python3
"""
Turbi PM Dashboard v2 — Generator
Run: JIRA_EMAIL=x JIRA_API_TOKEN=y python fetch_and_build_v2.py
"""

import os, json, base64, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
from collections import defaultdict

JIRA_BASE  = "https://turbi-team.atlassian.net"
JIRA_EMAIL = os.environ["JIRA_EMAIL"]
JIRA_TOKEN = os.environ["JIRA_API_TOKEN"]

_creds  = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_TOKEN}".encode()).decode()
HEADERS = {"Authorization": f"Basic {_creds}", "Accept": "application/json", "Content-Type": "application/json"}

PROJECTS = {
    "CF": {"id": "10775"},
    "SF": {"id": "11209"},
}
FIELDS = "summary,status,assignee,priority,issuetype,project,created,updated"

def jira_search(jql, max_results=100):
    url = f"{JIRA_BASE}/rest/api/3/search/jql"
    payload = json.dumps({"jql": jql, "maxResults": max_results, "fields": FIELDS.split(",")}).encode()
    req = urllib.request.Request(url, data=payload, headers=HEADERS, method="POST")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read()).get("issues", [])

def compact(issue):
    f = issue.get("fields", {}); proj = f.get("project", {}); a = f.get("assignee")
    return {"key": issue["key"], "summary": f.get("summary", ""), "status": f.get("status", {}).get("name", ""),
            "project_key": proj.get("key", ""), "project_name": proj.get("name", ""),
            "assignee": a.get("displayName", "Unassigned") if a else "Unassigned",
            "issuetype": f.get("issuetype", {}).get("name", ""), "priority": (f.get("priority") or {}).get("name", "Medium"),
            "created": f.get("created", ""), "updated": f.get("updated", "")}

def fetch_all():
    issues = []
    for key, info in PROJECTS.items():
        raw = jira_search(f"project = {info['id']} ORDER BY updated DESC", max_results=100)
        issues.extend([compact(i) for i in raw])
    return issues

def build_timeline(issues, days=30):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    by_day = defaultdict(list)
    for i in issues:
        day = i["updated"][:10]
        if day >= cutoff:
            by_day[day].append({"key": i["key"], "summary": i["summary"], "status": i["status"],
                                  "assignee": i["assignee"], "project_key": i["project_key"], "issuetype": i["issuetype"]})
    return dict(sorted(by_day.items(), reverse=True))

def build_html(issues, timeline):
    now = datetime.now(timezone(timedelta(hours=-3)))
    today = now.strftime("%Y-%m-%d")
    gen_at = now.strftime("%Y-%m-%dT%H:%M:%S-03:00")
    with open("turbi_pm_v2.html", "r", encoding="utf-8") as f:
        html = f.read()
    html = html.replace("__ISSUES_JSON__", json.dumps(issues, ensure_ascii=False))
    html = html.replace("__TIMELINE_JSON__", json.dumps(timeline, ensure_ascii=False))
    html = html.replace("__GENERATED_AT__", gen_at)
    html = html.replace("__TODAY__", today)
    return html

def main():
    issues = fetch_all()
    timeline = build_timeline(issues, days=30)
    html = build_html(issues, timeline)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Done: {len(html)//1024}KB")

if __name__ == "__main__":
    main()
