import os
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML
from app.config import Config

env = Environment(
    loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), "../templates/resume_editor")),
    autoescape=select_autoescape(["html", "xml"])
)


def _format_bullets(bullets_text: str):
    if not bullets_text:
        return []
    return [b.strip("-• ").strip() for b in bullets_text.splitlines() if b.strip()]


def _prepare_resume_data(resume_data: dict) -> dict:
    data = dict(resume_data)
    for exp in data.get("experience", []):
        exp["bullet_list"] = _format_bullets(exp.get("bullets", ""))
    return data


def render_resume_html(resume_data: dict, template_name: str = "classic") -> str:
    data = _prepare_resume_data(resume_data)
    template = env.get_template(f"{template_name}.html")
    return template.render(**data)


def render_resume_pdf(resume_data: dict, template_name: str = "classic", output_path: str = None) -> str:
    html = render_resume_html(resume_data, template_name)
    if output_path is None:
        from datetime import datetime
        safe_name = "".join(c if c.isalnum() else "_" for c in resume_data.get("profile", {}).get("full_name", "resume")).strip("_") or "resume"
        output_path = os.path.join(Config.GENERATED_DIR, f"{safe_name}_{template_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    HTML(string=html).write_pdf(output_path)
    return output_path
