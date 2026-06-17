from typing import List, Dict, Any, Optional


# ============== INSTITUTIONS ==============

def get_institutions(user_id: int, db) -> List[Dict[str, Any]]:
    return db.fetchall("SELECT * FROM institutions WHERE user_id = ? ORDER BY name", (user_id,))


def get_institution(user_id: int, institution_id: int, db) -> Optional[Dict[str, Any]]:
    return db.fetchone(
        "SELECT * FROM institutions WHERE user_id = ? AND id = ?",
        (user_id, institution_id)
    )


def add_institution(user_id: int, name: str, institution_type: str, location: str, db) -> int:
    return db.insert(
        "INSERT INTO institutions (user_id, name, institution_type, location) VALUES (?, ?, ?, ?)",
        (user_id, name, institution_type, location)
    )


def update_institution(user_id: int, institution_id: int, name: str, institution_type: str, location: str, db):
    db.execute(
        "UPDATE institutions SET name = ?, institution_type = ?, location = ? WHERE id = ? AND user_id = ?",
        (name, institution_type, location, institution_id, user_id)
    )


def delete_institution(user_id: int, institution_id: int, db):
    # Orphan courses/degrees instead of cascading
    db.execute("UPDATE courses SET institution_id = NULL WHERE institution_id = ? AND user_id = ?", (institution_id, user_id))
    db.execute("UPDATE degrees SET institution_id = NULL WHERE institution_id = ? AND user_id = ?", (institution_id, user_id))
    db.execute("DELETE FROM institutions WHERE id = ? AND user_id = ?", (institution_id, user_id))


# ============== DEGREES ==============

def get_degrees(user_id: int, db) -> List[Dict[str, Any]]:
    return db.fetchall(
        """SELECT d.*, i.name as institution_name, i.institution_type
           FROM degrees d
           LEFT JOIN institutions i ON d.institution_id = i.id
           WHERE d.user_id = ?
           ORDER BY d.end_date DESC, d.start_date DESC""",
        (user_id,)
    )


def get_degree(user_id: int, degree_id: int, db) -> Optional[Dict[str, Any]]:
    return db.fetchone(
        "SELECT * FROM degrees WHERE user_id = ? AND id = ?",
        (user_id, degree_id)
    )


def add_degree(user_id: int, institution_id: int, degree_name: str, degree_type: str,
               field: str, start_date: str, end_date: str, gpa: str, honors: str,
               is_current: bool, db) -> int:
    return db.insert(
        """INSERT INTO degrees
           (user_id, institution_id, degree_name, degree_type, field, start_date, end_date, gpa, honors, is_current)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, institution_id, degree_name, degree_type, field, start_date, end_date, gpa, honors, 1 if is_current else 0)
    )


def update_degree(user_id: int, degree_id: int, institution_id: int, degree_name: str,
                  degree_type: str, field: str, start_date: str, end_date: str, gpa: str,
                  honors: str, is_current: bool, db):
    db.execute(
        """UPDATE degrees
           SET institution_id = ?, degree_name = ?, degree_type = ?, field = ?, start_date = ?,
               end_date = ?, gpa = ?, honors = ?, is_current = ?
           WHERE id = ? AND user_id = ?""",
        (institution_id, degree_name, degree_type, field, start_date, end_date,
         gpa, honors, 1 if is_current else 0, degree_id, user_id)
    )


def delete_degree(user_id: int, degree_id: int, db):
    db.execute("UPDATE courses SET degree_id = NULL WHERE degree_id = ? AND user_id = ?", (degree_id, user_id))
    db.execute("DELETE FROM degrees WHERE id = ? AND user_id = ?", (degree_id, user_id))


# ============== COURSES ==============

def get_courses(user_id: int, db) -> List[Dict[str, Any]]:
    return db.fetchall("SELECT * FROM courses WHERE user_id = ? ORDER BY term, code", (user_id,))


def get_course(user_id: int, course_id: int, db) -> Optional[Dict[str, Any]]:
    return db.fetchone("SELECT * FROM courses WHERE user_id = ? AND id = ?", (user_id, course_id))


def add_course(user_id: int, institution_id: Optional[int], degree_id: Optional[int],
               code: str, name: str, grade: str, credits: float, term: str,
               description: str, is_major_related: bool, db) -> int:
    return db.insert(
        """INSERT INTO courses
           (user_id, institution_id, degree_id, code, name, grade, credits, term, description, is_major_related)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, institution_id, degree_id, code, name, grade, credits, term, description, 1 if is_major_related else 0)
    )


def update_course(user_id: int, course_id: int, institution_id: Optional[int], degree_id: Optional[int],
                  code: str, name: str, grade: str, credits: float, term: str,
                  description: str, is_major_related: bool, db):
    db.execute(
        """UPDATE courses
           SET institution_id = ?, degree_id = ?, code = ?, name = ?, grade = ?,
               credits = ?, term = ?, description = ?, is_major_related = ?
           WHERE id = ? AND user_id = ?""",
        (institution_id, degree_id, code, name, grade, credits, term, description,
         1 if is_major_related else 0, course_id, user_id)
    )


def update_course_major_related(user_id: int, course_id: int, is_major_related: bool, db):
    db.execute(
        "UPDATE courses SET is_major_related = ? WHERE id = ? AND user_id = ?",
        (1 if is_major_related else 0, course_id, user_id)
    )


def move_course(user_id: int, course_id: int, institution_id: Optional[int], degree_id: Optional[int], db):
    db.execute(
        "UPDATE courses SET institution_id = ?, degree_id = ? WHERE id = ? AND user_id = ?",
        (institution_id, degree_id, course_id, user_id)
    )


def delete_course(user_id: int, course_id: int, db):
    db.execute("DELETE FROM courses WHERE id = ? AND user_id = ?", (course_id, user_id))


# ============== GROUPED VIEW ==============

def get_courses_grouped(user_id: int, db) -> List[Dict[str, Any]]:
    """Return institutions with nested degrees and courses for the user."""
    institutions = db.fetchall(
        "SELECT * FROM institutions WHERE user_id = ? ORDER BY name",
        (user_id,)
    )
    degrees = db.fetchall(
        "SELECT * FROM degrees WHERE user_id = ? ORDER BY end_date DESC, start_date DESC",
        (user_id,)
    )
    courses = db.fetchall(
        "SELECT * FROM courses WHERE user_id = ? ORDER BY term, code",
        (user_id,)
    )

    # Also include unassigned courses (no institution)
    unassigned_courses = [c for c in courses if not c.get("institution_id")]

    result = []
    for inst in institutions:
        inst_degrees = []
        for deg in degrees:
            if deg["institution_id"] == inst["id"]:
                deg_courses = [c for c in courses if c.get("degree_id") == deg["id"]]
                inst_degrees.append({**deg, "courses": deg_courses})
        # Courses at this institution but not assigned to a degree
        inst_unassigned = [c for c in courses if c.get("institution_id") == inst["id"] and not c.get("degree_id")]
        result.append({
            **inst,
            "degrees": inst_degrees,
            "unassigned_courses": inst_unassigned
        })

    if unassigned_courses:
        result.append({
            "id": None,
            "name": "Unassigned",
            "location": None,
            "institution_type": "other",
            "degrees": [],
            "unassigned_courses": unassigned_courses
        })

    return result


# ============== EXTRACTION / REVIEW ==============

def find_matching_institution(user_id: int, name: str, db) -> Optional[Dict[str, Any]]:
    """Find an existing institution by name (case-insensitive)."""
    if not name:
        return None
    return db.fetchone(
        "SELECT * FROM institutions WHERE user_id = ? AND LOWER(name) = LOWER(?)",
        (user_id, name.strip())
    )


def find_matching_degree(user_id: int, institution_id: int, degree_name: str, db) -> Optional[Dict[str, Any]]:
    """Find an existing degree by institution and name (case-insensitive)."""
    if not degree_name:
        return None
    return db.fetchone(
        """SELECT d.* FROM degrees d
           WHERE d.user_id = ? AND d.institution_id = ? AND LOWER(d.degree_name) = LOWER(?)""",
        (user_id, institution_id, degree_name.strip())
    )


def save_from_review(user_id: int, review_data: Dict[str, Any], db) -> Dict[str, Any]:
    """Save education data from the transcript review screen.

    review_data format:
    {
        "institution": {"id": existing_id_or_none, "name": ..., "institution_type": ..., "location": ...},
        "degree": {"id": existing_id_or_none, "degree_name": ..., "degree_type": ..., "field": ..., ...},
        "courses": [{"code": ..., "name": ..., "grade": ..., "credits": ..., "term": ..., "description": ..., "is_major_related": ...}]
    }
    """
    inst_data = review_data.get("institution", {})
    deg_data = review_data.get("degree", {})
    courses = review_data.get("courses", [])

    # Institution
    inst_id = inst_data.get("id")
    if inst_id:
        update_institution(user_id, inst_id, inst_data["name"], inst_data["institution_type"], inst_data.get("location", ""), db)
    else:
        inst_id = add_institution(user_id, inst_data["name"], inst_data["institution_type"], inst_data.get("location", ""), db)

    # Degree
    deg_id = deg_data.get("id")
    if deg_id:
        update_degree(user_id, deg_id, inst_id, deg_data["degree_name"], deg_data["degree_type"],
                      deg_data.get("field", ""), deg_data.get("start_date", ""), deg_data.get("end_date", ""),
                      deg_data.get("gpa", ""), deg_data.get("honors", ""), bool(deg_data.get("is_current", False)), db)
    else:
        deg_id = add_degree(user_id, inst_id, deg_data["degree_name"], deg_data["degree_type"],
                            deg_data.get("field", ""), deg_data.get("start_date", ""), deg_data.get("end_date", ""),
                            deg_data.get("gpa", ""), deg_data.get("honors", ""), bool(deg_data.get("is_current", False)), db)

    # Courses
    saved = []
    for course in courses:
        code = course.get("code", "")
        name = course.get("name", "")
        term = course.get("term", "")
        # Check for duplicate
        existing = db.fetchone(
            """SELECT id FROM courses
               WHERE user_id = ? AND code = ? AND name = ? AND term = ? AND degree_id = ?""",
            (user_id, code, name, term, deg_id)
        )
        is_major = bool(course.get("is_major_related", True))
        if existing:
            update_course(user_id, existing["id"], inst_id, deg_id, code, name,
                          course.get("grade", ""), course.get("credits"), term,
                          course.get("description", ""), is_major, db)
            saved.append(existing["id"])
        else:
            cid = add_course(user_id, inst_id, deg_id, code, name,
                             course.get("grade", ""), course.get("credits"), term,
                             course.get("description", ""), is_major, db)
            saved.append(cid)

    return {"institution_id": inst_id, "degree_id": deg_id, "course_ids": saved}
