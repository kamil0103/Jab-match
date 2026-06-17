from typing import List, Dict, Any, Optional


# ============== WORK EXPERIENCE ==============

def get_work_experience(user_id: int, db) -> List[Dict[str, Any]]:
    return db.fetchall(
        "SELECT * FROM work_experience WHERE user_id = ? ORDER BY end_date DESC, start_date DESC",
        (user_id,)
    )


def get_work_experience_item(user_id: int, exp_id: int, db) -> Optional[Dict[str, Any]]:
    return db.fetchone(
        "SELECT * FROM work_experience WHERE user_id = ? AND id = ?",
        (user_id, exp_id)
    )


def add_work_experience(user_id: int, company: str, title: str, location: str,
                        start_date: str, end_date: str, is_current: bool,
                        bullets: str, db) -> int:
    return db.insert(
        """INSERT INTO work_experience
           (user_id, company, title, location, start_date, end_date, is_current, bullets)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, company, title, location, start_date, end_date,
         1 if is_current else 0, bullets)
    )


def update_work_experience(user_id: int, exp_id: int, company: str, title: str,
                           location: str, start_date: str, end_date: str,
                           is_current: bool, bullets: str, db):
    db.execute(
        """UPDATE work_experience
           SET company = ?, title = ?, location = ?, start_date = ?, end_date = ?,
               is_current = ?, bullets = ?
           WHERE id = ? AND user_id = ?""",
        (company, title, location, start_date, end_date,
         1 if is_current else 0, bullets, exp_id, user_id)
    )


def delete_work_experience(user_id: int, exp_id: int, db):
    db.execute(
        "DELETE FROM work_experience WHERE id = ? AND user_id = ?",
        (exp_id, user_id)
    )


# ============== PROJECTS ==============

def get_projects(user_id: int, db) -> List[Dict[str, Any]]:
    return db.fetchall(
        "SELECT * FROM projects WHERE user_id = ? ORDER BY end_date DESC, start_date DESC",
        (user_id,)
    )


def get_project(user_id: int, project_id: int, db) -> Optional[Dict[str, Any]]:
    return db.fetchone(
        "SELECT * FROM projects WHERE user_id = ? AND id = ?",
        (user_id, project_id)
    )


def add_project(user_id: int, name: str, description: str, technologies: str,
                link: str, start_date: str, end_date: str, is_current: bool,
                db) -> int:
    return db.insert(
        """INSERT INTO projects
           (user_id, name, description, technologies, link, start_date, end_date, is_current)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, name, description, technologies, link, start_date, end_date,
         1 if is_current else 0)
    )


def update_project(user_id: int, project_id: int, name: str, description: str,
                   technologies: str, link: str, start_date: str, end_date: str,
                   is_current: bool, db):
    db.execute(
        """UPDATE projects
           SET name = ?, description = ?, technologies = ?, link = ?, start_date = ?,
               end_date = ?, is_current = ?
           WHERE id = ? AND user_id = ?""",
        (name, description, technologies, link, start_date, end_date,
         1 if is_current else 0, project_id, user_id)
    )


def delete_project(user_id: int, project_id: int, db):
    db.execute(
        "DELETE FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id)
    )


# ============== HELPERS ==============

def format_bullets(bullets_text: str) -> List[str]:
    """Split bullet text by newlines and strip."""
    if not bullets_text:
        return []
    return [b.strip("-• ").strip() for b in bullets_text.splitlines() if b.strip()]


def render_bullets(bullets_text: str) -> str:
    """Render bullets as an HTML unordered list."""
    bullets = format_bullets(bullets_text)
    if not bullets:
        return ""
    return "<ul>" + "".join(f"<li>{b}</li>" for b in bullets) + "</ul>"
