# core/render/report_md.py
from __future__ import annotations
from typing import List
from datetime import datetime

from core.analysis.weekly_pipeline import TickerReport, Topic

def _fmt_topic(t: Topic) -> str:
    print('hello1')
    lines = [f"### {t.name}"]
    for b in t.bullets:
        lines.append(f"- {b}")
    if t.refs:
        lines.append("")
        lines.append("_Refs:_")
        for r in t.refs:
            title = r.get("title","").strip() or "(untitled)"
            url = r.get("url","").strip()
            src = r.get("source","").strip()
            ts  = r.get("published_utc","")
            lines.append(f"- [{title}]({url}) · {src} · {ts}")
    lines.append("")
    return "\n".join(lines)

def render_markdown(nvda: TickerReport, tsla: TickerReport) -> str:
     print('hello2')
    hdr = f"# Weekly News Brief: NVDA & TSLA ({nvda.period_start} → {nvda.period_end_excl})\n"
    hdr += f"_Generated: {datetime.utcnow().isoformat(timespec='seconds')}Z_\n\n"

    # very light executive summary: just list topic names
    exec_lines = ["## Executive Summary", ""]
    for tr in [nvda, tsla]:
        exec_lines.append(f"**{tr.ticker}** topics: " + "; ".join([t.name for t in tr.topics]))
    exec_lines.append("")
    exec_sec = "\n".join(exec_lines)

    def section(tr: TickerReport) -> str:
        out = [f"## {tr.ticker}"]
        for t in tr.topics:
            out.append(_fmt_topic(t))
        return "\n".join(out)

    md = "\n\n".join([hdr, exec_sec, section(nvda), section(tsla)])
    return md
