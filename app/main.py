from fastapi import FastAPI
from datetime import date
from scripts.generate_report import generate_daily_report

app = FastAPI(title="FinReport API")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/generate")
def generate():
    out = generate_daily_report(date.today())
    return {"ok": True, "pdf": str(out["pdf"]), "html": str(out["html"])}