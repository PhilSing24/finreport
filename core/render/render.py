from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

_env = Environment(
    loader=FileSystemLoader(str(Path(__file__).parent)),
    autoescape=select_autoescape(["html"])
)

def render_html(template_name: str, ctx: dict, out_html: Path):
    tpl = _env.get_template(template_name)
    html = tpl.render(**ctx)
    out_html.write_text(html, encoding="utf-8")
    return out_html

def html_to_pdf(html_path: Path, out_pdf: Path):
    HTML(filename=str(html_path)).write_pdf(str(out_pdf))
    return out_pdf
