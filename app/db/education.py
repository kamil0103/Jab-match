from typing import List, Dict, Any, Optional


def save_institution(user_id: int, institution: Dict[str, Any], db) -> int:
    """Save or update an institution and return its id."""
    name = institution.get("name", "Unknown Institution")
    location = institution.get("location")
    institution_type = institution.get("institution_type", "other")

    existing = db.fetchone(
        "SELECT id FROM institutions WHERE user_id = ? AND name = ?",
        (user_id, name)
    )
    if existing:
        db.execute(
            "UPDATE institutions SET location = ?, institution_type = ? WHERE id = ?",
            (location, institution_type, existing["id"])
        )
        return existing["id"]

    result = db.execute(
        "INSERT INTO institutions (user_id, name, location, institution_type) VALUES (?, ?, ?, ?)",
        (user_id, name, location, institution_type)
    )
    return result[0]["id"] if result else db.fetchone(
        "SELECT id FROM institutions WHERE user_id = ? AND name = ?",
        (user_id, name)
    )["id"]


def save_degree(user_id: int, institution_id: int, degree: Dict[str, Any], db) -> int:
    """Save or update a degree and return its id."""
    degree_name = degree.get("degree_name", "Unknown Degree")
    degree_type = degree.get("degree_type", "other")
    field = degree.get("field")
    start_date = degree.get("start_date")
    end_date = degree.get("end_date")
    gpa = degree.get("gpa")
    honors = degree.get("honors")
    is_current = 1 if degree.get("is_current") else 0

    existing = db.fetchone(
        "SELECT id FROM degrees WHERE user_id = ? AND institution_id = ? AND degree_name = ?",
        (user_id, institution_id, degree_name)
    )
    if existing:
        db.execute(
            "UPDATE degrees SET degree_type = ?, field = ?, start_date = ?, end_date = ?, gpa = ?, honors = ?, is_current = ? WHERE id = ?",
            (degree_type, field, start_date, end_date, gpa, honors, is_current, existing["id"])
        )
        return existing["id"]

    result = db.execute(
        "INSERT INTO degrees (user_id, institution_id, degree_name, degree_type, field, start_date, end_date, gpa, honors, is_current) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, institution_id, degree_name, degree_type, field, start_date, end_date, gpa, honors, is_current)
    )
    return result[0]["id"] if result else db.fetchone(
        "SELECT id FROM degrees WHERE user_id = ? AND institution_id = ? AND degree_name = ?",
        (user_id, institution_id, degree_name)
    )["id"]


def save_course(user_id: int, institution_id: Optional[int], degree_id: Optional[int], course: Dict[str, Any], db) -> int:
    """Save a course if it does not already exist for the user/degree/term."""
    code = course.get("code")
    name = course.get("name", "Unknown Course")
    grade = course.get("grade")
    credits = course.get("credits")
    term = course.get("term")
    description = course.get("description")
    skills = course.get("skills")

    # Avoid duplicates within the same degree/institution and term
    existing = db.fetchone(
        "SELECT id FROM courses WHERE user_id = ? AND code = ? AND name = ? AND term = ? AND COALESCE(degree_id, -1) = COALESCE(?, -1)",
        (user_id, code, name, term, degree_id if degree_id else -1)
    )
    if existing:
        db.execute(
            "UPDATE courses SET institution_id = ?, degree_id = ?, grade = ?, credits = ?, description = ?, skills = ? WHERE id = ?",
            (institution_id, degree_id, grade, credits, description, skills, existing["id"])
        )
        return existing["id"]

    result = db.execute(
        "INSERT INTO courses (user_id, institution_id, degree_id, code, name, grade, credits, term, description, skills) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, institution_id, degree_id, code, name, grade, credits, term, description, skills)
    )
    return result[0]["id"] if result else db.fetchone(
        "SELECT id FROM courses WHERE user_id = ? AND code = ? AND name = ? AND term = ?",
        (user_id, code, name, term)
    )["id"]


def save_transfer_credit(user_id: int, institution_id: Optional[int], transfer: Dict[str, Any], db) -> int:
    """Save a transfer credit summary."""
    institution_name = transfer.get("institution_name") or transfer.get("institution")
    attempted = transfer.get("attempted")
    earned = transfer.get("earned")
    gpa_units = transfer.get("gpa_units")
    points = transfer.get("points")
    transfer_gpa = transfer.get("transfer_gpa")

    existing = db.fetchone(
        "SELECT id FROM transfer_credits WHERE user_id = ? AND institution = ?",
        (user_id, institution_name)
    )
    if existing:
        db.execute(
            "UPDATE transfer_credits SET institution_id = ?, attempted = ?, earned = ?, gpa_units = ?, points = ?, transfer_gpa = ? WHERE id = ?",
            (institution_id, attempted, earned, gpa_units, points, transfer_gpa, existing["id"])
        )
        return existing["id"]

    result = db.execute(
        "INSERT INTO transfer_credits (user_id, institution_id, institution, attempted, earned, gpa_units, points, transfer_gpa) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, institution_id, institution_name, attempted, earned, gpa_units, points, transfer_gpa)
    )
    return result[0]["id"] if result else db.fetchone(
        "SELECT id FROM transfer_credits WHERE user_id = ? AND institution = ?",
        (user_id, institution_name)
    )["id"]


def save_extracted_transcript(user_id: int, extracted: Dict[str, Any], db) -> Dict[str, Any]:
    """Save institutions, degrees, courses, and transfer credits from extracted transcript data."""
    institutions = extracted.get("institutions", [])
    degrees = extracted.get("degrees", [])
    courses = extracted.get("courses", [])
    transfer_credits = extracted.get("transfer_credits", [])

    institution_ids = {}
    degree_ids = {}

    # Save institutions first
    for inst in institutions:
        inst_id = save_institution(user_id, inst, db)
        institution_ids[inst.get("name", "Unknown Institution")] = inst_id

    # Save transfer credit institutions if not already saved
    for tc in transfer_credits:
        inst_name = tc.get("institution_name") or tc.get("institution")
        if inst_name and inst_name not in institution_ids:
            inst_id = save_institution(user_id, {
                "name": inst_name,
                "location": None,
                "institution_type": "community_college"
            }, db)
            institution_ids[inst_name] = inst_id

    # Save degrees
    for deg in degrees:
        inst_name = deg.get("institution_name")
        inst_id = institution_ids.get(inst_name)
        if inst_id:
            deg_id = save_degree(user_id, inst_id, deg, db)
            degree_ids[(inst_id, deg.get("degree_name", "Unknown Degree"))] = deg_id

    # Save courses
    saved_courses = []
    for course in courses:
        inst_name = course.get("institution_name")
        deg_name = course.get("degree_name")
        inst_id = institution_ids.get(inst_name)
        deg_id = None
        if inst_id and deg_name:
            deg_id = degree_ids.get((inst_id, deg_name))
        course_id = save_course(user_id, inst_id, deg_id, course, db)
        saved_courses.append(course_id)

    # Save transfer credits
    saved_transfers = []
    for tc in transfer_credits:
        inst_name = tc.get("institution_name") or tc.get("institution")
        inst_id = institution_ids.get(inst_name)
        tc_id = save_transfer_credit(user_id, inst_id, tc, db)
        saved_transfers.append(tc_id)

    return {
        "institution_ids": institution_ids,
        "degree_ids": degree_ids,
        "saved_courses": saved_courses,
        "saved_transfers": saved_transfers
    }


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
