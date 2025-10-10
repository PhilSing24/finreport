from pathlib import Path
from datetime import date
from core.charts.make_charts import chart_top_movers_png
from core.render.render import render_html, html_to_pdf

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"

def generate_daily_report(d: date):
    # placeholder data (later we’ll fetch from DB/news)
    overview_bullets = [
        "S&P 500 +0.6%, Nasdaq +0.8%, EuroStoxx 50 +0.4%",
        "WTI +0.7%, Gold -0.3%, US 10Y -3bp",
        "USD broadly flat; EURUSD 1.08 (+0.1%)"
    ]
    top_movers = [("AAPL", 2.3), ("NVDA", 1.9), ("TSLA", -1.2), ("MSFT", 0.8)]
    sources = [
        {"title": "Example News Story", "url": "https://example.com/news1"},
        {"title": "Another Source", "url": "https://example.com/news2"},
    ]

    BUILD.mkdir(exist_ok=True, parents=True)
    charts_dir = BUILD / "charts"
    charts_dir.mkdir(exist_ok=True)

    # chart
    movers_png = chart_top_movers_png(charts_dir, top_movers)

    # render HTML
    html_out = BUILD / f"report_{d.isoformat()}.html"
    ctx = {
        "report_date": d.isoformat(),
        "overview_bullets": overview_bullets,
        "charts": {"top_movers": movers_png},
        "sources": sources,
    }
    render_html("template.html", ctx, html_out)

    # export PDF
    pdf_out = BUILD / f"report_{d.isoformat()}.pdf"
    html_to_pdf(html_out, pdf_out)

    return {"html": html_out, "pdf": pdf_out}

if __name__ == "__main__":
    out = generate_daily_report(date.today())
    print("HTML:", out["html"])
    print("PDF :", out["pdf"])