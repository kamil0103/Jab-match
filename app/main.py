import streamlit as st
import os
import json
from app.config import Config
from app.db.database import Database
from app.parsers.transcript import parse_transcript
from app.parsers.syllabus import parse_syllabus
from app.ai.extractor import TranscriptExtractor
from app.auth import login_user, register_user, get_user_paths, get_profile, update_profile
from app.db.education import (
    get_institutions, get_degrees, get_courses, get_courses_grouped,
    add_institution, update_institution, delete_institution,
    add_degree, update_degree, delete_degree,
    add_course, update_course, delete_course, move_course,
    find_matching_institution, find_matching_degree, save_from_review
)
from app.db.experience import (
    get_work_experience, add_work_experience, update_work_experience, delete_work_experience,
    get_projects, add_project, update_project, delete_project
)
from app.resume_editor import (
    build_resume_data, save_resume_version, get_latest_resume_version,
    render_resume_html, render_resume_pdf, ResumeAIHelper, ATSChecker
)

st.set_page_config(
    page_title="Job Matcher",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Ensure required directories exist
Config.ensure_dirs()

# ============================================
# AUTHENTICATION
# ============================================
if "user" not in st.session_state:
    st.session_state.user = None

if "auth_tab" not in st.session_state:
    st.session_state.auth_tab = "Login"

def show_auth_page():
    st.title("Job Matcher")
    st.markdown("Sign in or create an account to manage your job search.")

    tabs = st.tabs(["Login", "Register"])

    with tabs[0]:
        st.subheader("Login")
        with st.form("login_form"):
            login_id = st.text_input("Username or Email")
            login_password = st.text_input("Password", type="password")
            login_submit = st.form_submit_button("Login", type="primary")

        if login_submit:
            if not login_id or not login_password:
                st.error("Please enter both username/email and password.")
            else:
                with st.spinner("Logging in..."):
                    success, user = login_user(login_id, login_password)
                    if success:
                        st.session_state.user = user
                        st.success(f"Welcome back, {user['username']}!")
                        st.rerun()
                    else:
                        st.error("Invalid username/email or password.")

    with tabs[1]:
        st.subheader("Create Account")
        with st.form("register_form"):
            reg_username = st.text_input("Username")
            reg_email = st.text_input("Email")
            reg_password = st.text_input("Password", type="password")
            reg_password2 = st.text_input("Confirm Password", type="password")
            reg_submit = st.form_submit_button("Create Account", type="primary")

        if reg_submit:
            if not reg_username or not reg_email or not reg_password:
                st.error("All fields are required.")
            elif reg_password != reg_password2:
                st.error("Passwords do not match.")
            elif len(reg_password) < 6:
                st.error("Password must be at least 6 characters.")
            else:
                with st.spinner("Creating account..."):
                    success, user_id = register_user(reg_username, reg_email, reg_password)
                    if success:
                        # Auto-login after registration
                        ok, user = login_user(reg_username, reg_password)
                        if ok:
                            st.session_state.user = user
                            st.success(f"Account created! Welcome, {user['username']}!")
                            st.rerun()
                    else:
                        st.error("Username or email already taken.")

# Show auth page if not logged in
if st.session_state.user is None:
    show_auth_page()
    st.stop()

# ============================================
# LOGGED-IN USER SETUP
# ============================================
user = st.session_state.user
user_paths = get_user_paths(user["id"])

# Refresh profile data from users database and merge into session user
profile = get_profile(user["id"])
user.update(profile)
st.session_state.user = user

# Ensure directories exist
os.makedirs(user_paths["uploads_dir"], exist_ok=True)
os.makedirs(user_paths["generated_dir"], exist_ok=True)

# Per-user database
db = Database(user_paths["db_path"])
extractor = TranscriptExtractor()

# Start background scheduler if enabled
from app.scheduler.daily import get_scheduler
scheduler = get_scheduler()
if Config.SCHEDULE_ENABLED and Config.SCRAPER_ENABLED:
    scheduler.start()

# ============================================
# SIDEBAR NAVIGATION + LOGOUT
# ============================================
st.sidebar.title("Job Matcher")
st.sidebar.markdown(f"**Logged in as:** `{user['username']}`")

page = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Profile", "Education", "Experience", "Upload Transcript", "Skills & Certificates", "Resume Editor", "Discover Jobs", "Jobs", "Generate Documents", "Settings"]
)

st.sidebar.markdown("---")
if st.sidebar.button("Logout", use_container_width=True):
    st.session_state.user = None
    st.session_state.keywords_data = None
    st.session_state.discovered_jobs = []
    st.session_state.indeed_jobs = []
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("### Status")
if Config.ai_available():
    st.sidebar.success("AI Ready")
else:
    st.sidebar.error("AI Not Configured")

if Config.SCRAPER_ENABLED:
    st.sidebar.warning("Scraper Enabled")
else:
    st.sidebar.info("Scraper Disabled")

# Helper: refresh counts
def get_counts():
    courses = db.fetchall("SELECT COUNT(*) as c FROM courses")
    jobs = db.fetchall("SELECT COUNT(*) as c FROM jobs")
    docs = db.fetchall("SELECT COUNT(*) as c FROM documents")
    skills = db.fetchall("SELECT COUNT(*) as c FROM skills")
    certs = db.fetchall("SELECT COUNT(*) as c FROM certificates")
    return courses[0]["c"], jobs[0]["c"], docs[0]["c"], skills[0]["c"], certs[0]["c"]

course_count, job_count, doc_count, skill_count, cert_count = get_counts()

# ============================================
# PAGES
# ============================================

if page == "Dashboard":
    st.title("Job Matcher Dashboard")
    st.markdown("Welcome to Job Matcher! Your data is private and tied to your account.")

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Courses", course_count)
    with col2:
        st.metric("Skills", skill_count)
    with col3:
        st.metric("Certificates", cert_count)
    with col4:
        st.metric("Jobs Tracked", job_count)
    with col5:
        st.metric("Documents", doc_count)

    st.markdown("### Quick Start")
    st.markdown("""
    1. Go to **Upload Transcript** and upload your university transcript PDF
    2. Go to **Skills & Certificates** to manage skills and add certifications
    3. Go to **Discover Jobs** to find listings matched to your profile
    4. Go to **Jobs** to analyze fit and generate application materials
    """)

elif page == "Profile":
    st.title("Your Profile")
    st.markdown("Update your personal information. This is used when generating resumes and cover letters.")

    profile = get_profile(user["id"])

    with st.form("profile_form"):
        full_name = st.text_input("Full Name", value=profile.get("full_name", ""), placeholder="John Doe")
        email = st.text_input("Email", value=profile.get("email", user.get("email", "")), placeholder="john@example.com")
        phone = st.text_input("Phone", value=profile.get("phone", ""), placeholder="(555) 123-4567")
        location = st.text_input("Location (City, State)", value=profile.get("location", ""), placeholder="Los Angeles, CA")
        linkedin_url = st.text_input("LinkedIn URL", value=profile.get("linkedin_url", ""), placeholder="https://linkedin.com/in/johndoe")
        github_url = st.text_input("GitHub URL", value=profile.get("github_url", ""), placeholder="https://github.com/johndoe")
        portfolio_url = st.text_input("Portfolio / Website URL", value=profile.get("portfolio_url", ""), placeholder="https://johndoe.dev")
        summary = st.text_area("Professional Summary (2–4 lines)", value=profile.get("summary", ""), height=100)
        target_roles = st.text_input("Target Roles (comma separated)", value=profile.get("target_roles", ""), placeholder="Software Engineer, Backend Developer")

        save_profile = st.form_submit_button("Save Profile", type="primary")

    if save_profile:
        updated = {
            "full_name": full_name,
            "email": email,
            "phone": phone,
            "location": location,
            "linkedin_url": linkedin_url,
            "github_url": github_url,
            "portfolio_url": portfolio_url,
            "summary": summary,
            "target_roles": target_roles,
        }
        if update_profile(user["id"], updated):
            # Refresh session user
            user.update(updated)
            st.session_state.user = user
            st.success("Profile saved!")
            st.rerun()
        else:
            st.error("Could not save profile.")

    st.markdown("---")
    st.subheader("Resume Contact Header Preview")
    contact_parts = []
    if profile.get("location"):
        contact_parts.append(profile.get("location"))
    if profile.get("phone"):
        contact_parts.append(profile.get("phone"))
    if profile.get("email"):
        contact_parts.append(profile.get("email"))
    links = []
    if profile.get("linkedin_url"):
        links.append(f"[LinkedIn]({profile.get('linkedin_url')})")
    if profile.get("github_url"):
        links.append(f"[GitHub]({profile.get('github_url')})")
    if profile.get("portfolio_url"):
        links.append(f"[Portfolio]({profile.get('portfolio_url')})")

    if profile.get("full_name"):
        st.markdown(f"### {profile.get('full_name')}")
    if contact_parts:
        st.markdown(" | ".join(contact_parts))
    if links:
        st.markdown(" | ".join(links))

    st.markdown("---")
    st.subheader("Education Summary")
    grouped = get_courses_grouped(user["id"], db)
    if grouped:
        for inst in grouped:
            st.markdown(f"**{inst['name']}** ({inst['institution_type']})")
            for deg in inst.get("degrees", []):
                st.markdown(f"- {deg['degree_name']} — {deg.get('field', '')} ({len(deg['courses'])} courses)")
    else:
        st.info("No education added yet. Go to the **Education** page to add your degrees and institutions.")

elif page == "Education":
    st.title("Education")
    st.markdown("Manage your institutions, degrees, and courses. Add degrees here first, then upload transcripts and match them.")

    # Helper refresh
    institutions = get_institutions(user["id"], db)
    degrees = get_degrees(user["id"], db)
    courses = get_courses(user["id"], db)

    # ============== INSTITUTIONS ==============
    st.markdown("---")
    st.header("Institutions")
    with st.expander("Add Institution"):
        with st.form("add_institution_form"):
            inst_name = st.text_input("Institution Name", placeholder="University of Example")
            inst_type = st.selectbox("Type", ["university", "community_college", "high_school", "certificate_organization", "other"])
            inst_location = st.text_input("Location (City, State)", placeholder="Los Angeles, CA")
            add_inst = st.form_submit_button("Add Institution")
        if add_inst and inst_name:
            add_institution(user["id"], inst_name, inst_type, inst_location, db)
            st.success(f"Added {inst_name}")
            st.rerun()

    if institutions:
        for inst in institutions:
            with st.expander(f"{inst['name']} ({inst['institution_type']})"):
                with st.form(f"edit_inst_{inst['id']}"):
                    edit_inst_name = st.text_input("Name", value=inst["name"], key=f"inst_name_{inst['id']}")
                    edit_inst_type = st.selectbox("Type", ["university", "community_college", "high_school", "certificate_organization", "other"],
                                                   index=["university", "community_college", "high_school", "certificate_organization", "other"].index(inst.get("institution_type", "other")),
                                                   key=f"inst_type_{inst['id']}")
                    edit_inst_location = st.text_input("Location", value=inst.get("location", ""), key=f"inst_loc_{inst['id']}")
                    c1, c2 = st.columns(2)
                    with c1:
                        save_inst = st.form_submit_button("Save")
                    with c2:
                        delete_inst = st.form_submit_button("Delete", type="secondary")
                if save_inst:
                    update_institution(user["id"], inst["id"], edit_inst_name, edit_inst_type, edit_inst_location, db)
                    st.success("Institution updated")
                    st.rerun()
                if delete_inst:
                    delete_institution(user["id"], inst["id"], db)
                    st.success("Institution deleted")
                    st.rerun()
    else:
        st.info("No institutions yet. Add one above.")

    # ============== DEGREES ==============
    st.markdown("---")
    st.header("Degrees")
    with st.expander("Add Degree"):
        with st.form("add_degree_form"):
            deg_inst = st.selectbox("Institution", [i["name"] for i in institutions], disabled=not institutions)
            deg_name = st.text_input("Degree Name", placeholder="Bachelor of Science in Computer Science")
            deg_type = st.selectbox("Degree Type", ["high_school_diploma", "associates", "bachelors", "masters", "doctorate", "certificate", "other"])
            deg_field = st.text_input("Field of Study", placeholder="Computer Science")
            c1, c2 = st.columns(2)
            with c1:
                deg_start = st.text_input("Start Date (YYYY-MM)", placeholder="2020-08")
            with c2:
                deg_end = st.text_input("End Date (YYYY-MM)", placeholder="2024-05")
            deg_gpa = st.text_input("GPA", placeholder="3.8")
            deg_honors = st.text_input("Honors", placeholder="Cum Laude")
            deg_current = st.checkbox("Currently enrolled")
            add_deg = st.form_submit_button("Add Degree")
        if add_deg and deg_name and institutions:
            inst_id = next(i["id"] for i in institutions if i["name"] == deg_inst)
            add_degree(user["id"], inst_id, deg_name, deg_type, deg_field, deg_start, deg_end, deg_gpa, deg_honors, deg_current, db)
            st.success(f"Added {deg_name}")
            st.rerun()

    if degrees:
        for deg in degrees:
            with st.expander(f"{deg['degree_name']} at {deg.get('institution_name', 'Unknown')}"):
                with st.form(f"edit_deg_{deg['id']}"):
                    edit_deg_inst = st.selectbox("Institution", [i["name"] for i in institutions],
                                                  index=[i["name"] for i in institutions].index(deg.get("institution_name", institutions[0]["name"])) if institutions else 0,
                                                  key=f"deg_inst_{deg['id']}")
                    edit_deg_name = st.text_input("Degree Name", value=deg["degree_name"], key=f"deg_name_{deg['id']}")
                    type_options = ["high_school_diploma", "associates", "bachelors", "masters", "doctorate", "certificate", "other"]
                    edit_deg_type = st.selectbox("Degree Type", type_options,
                                                 index=type_options.index(deg.get("degree_type", "other")),
                                                 key=f"deg_type_{deg['id']}")
                    edit_deg_field = st.text_input("Field", value=deg.get("field", ""), key=f"deg_field_{deg['id']}")
                    c1, c2 = st.columns(2)
                    with c1:
                        edit_deg_start = st.text_input("Start Date", value=deg.get("start_date", ""), key=f"deg_start_{deg['id']}")
                    with c2:
                        edit_deg_end = st.text_input("End Date", value=deg.get("end_date", ""), key=f"deg_end_{deg['id']}")
                    edit_deg_gpa = st.text_input("GPA", value=deg.get("gpa", ""), key=f"deg_gpa_{deg['id']}")
                    edit_deg_honors = st.text_input("Honors", value=deg.get("honors", ""), key=f"deg_honors_{deg['id']}")
                    edit_deg_current = st.checkbox("Currently enrolled", value=bool(deg.get("is_current")), key=f"deg_current_{deg['id']}")
                    c1, c2 = st.columns(2)
                    with c1:
                        save_deg = st.form_submit_button("Save")
                    with c2:
                        delete_deg = st.form_submit_button("Delete", type="secondary")
                if save_deg and institutions:
                    inst_id = next(i["id"] for i in institutions if i["name"] == edit_deg_inst)
                    update_degree(user["id"], deg["id"], inst_id, edit_deg_name, edit_deg_type, edit_deg_field,
                                  edit_deg_start, edit_deg_end, edit_deg_gpa, edit_deg_honors, edit_deg_current, db)
                    st.success("Degree updated")
                    st.rerun()
                if delete_deg:
                    delete_degree(user["id"], deg["id"], db)
                    st.success("Degree deleted")
                    st.rerun()
    else:
        st.info("No degrees yet. Add one above.")

    # ============== COURSES ==============
    st.markdown("---")
    st.header("Courses")
    if courses:
        st.markdown("Toggle **Major Related** to control which courses appear on your resume.")
        for c in courses:
            cols = st.columns([2, 2, 1, 1, 1, 1, 1])
            with cols[0]:
                st.markdown(f"**{c['code']}** — {c['name']}")
            with cols[1]:
                st.markdown(f"Grade: {c['grade']}, Credits: {c['credits']}, Term: {c.get('term', '')}")
            with cols[2]:
                is_major = bool(c.get("is_major_related", 1))
                if st.checkbox("Major", value=is_major, key=f"major_{c['id']}") != is_major:
                    from app.db.education import update_course_major_related
                    update_course_major_related(user["id"], c["id"], not is_major, db)
                    st.rerun()
            with cols[3]:
                if st.button("Edit", key=f"edit_course_{c['id']}"):
                    st.session_state[f"edit_course_open_{c['id']}"] = True
                    st.rerun()
            with cols[4]:
                if st.button("Delete", key=f"del_course_{c['id']}"):
                    delete_course(user["id"], c["id"], db)
                    st.rerun()

            if st.session_state.get(f"edit_course_open_{c['id']}", False):
                with st.form(f"edit_course_form_{c['id']}"):
                    ec_code = st.text_input("Code", value=c.get("code", ""), key=f"ec_code_{c['id']}")
                    ec_name = st.text_input("Name", value=c.get("name", ""), key=f"ec_name_{c['id']}")
                    ec_grade = st.text_input("Grade", value=c.get("grade", ""), key=f"ec_grade_{c['id']}")
                    ec_credits = st.number_input("Credits", value=float(c.get("credits") or 0), key=f"ec_credits_{c['id']}")
                    ec_term = st.text_input("Term", value=c.get("term", ""), key=f"ec_term_{c['id']}")
                    ec_desc = st.text_area("Description", value=c.get("description", ""), key=f"ec_desc_{c['id']}")
                    ec_major = st.checkbox("Major related", value=bool(c.get("is_major_related", 1)), key=f"ec_major_{c['id']}")
                    degree_options = [(None, "Unassigned")] + [(d["id"], d["degree_name"]) for d in degrees]
                    current_deg = c.get("degree_id")
                    ec_deg_idx = next((i for i, (did, _) in enumerate(degree_options) if did == current_deg), 0)
                    ec_deg = st.selectbox("Degree", [d[1] for d in degree_options], index=ec_deg_idx, key=f"ec_deg_{c['id']}")
                    save_ec = st.form_submit_button("Save")
                if save_ec:
                    deg_id = degree_options[[d[1] for d in degree_options].index(ec_deg)][0]
                    update_course(user["id"], c["id"], None, deg_id, ec_code, ec_name, ec_grade, ec_credits, ec_term, ec_desc, ec_major, db)
                    st.session_state.pop(f"edit_course_open_{c['id']}", None)
                    st.success("Course updated")
                    st.rerun()
    else:
        st.info("No courses yet. Upload a transcript to add courses.")

elif page == "Experience":
    st.title("Experience & Projects")
    st.markdown("Add your real work experience and projects. The AI will use these on your resume and will NOT invent fake ones.")

    # ============== WORK EXPERIENCE ==============
    st.markdown("---")
    st.header("Work Experience")
    with st.expander("Add Work Experience"):
        with st.form("add_exp_form"):
            exp_company = st.text_input("Company", placeholder="Tech Corp")
            exp_title = st.text_input("Job Title", placeholder="Software Engineering Intern")
            exp_location = st.text_input("Location", placeholder="Remote")
            c1, c2 = st.columns(2)
            with c1:
                exp_start = st.text_input("Start Date (YYYY-MM)", placeholder="2023-06")
            with c2:
                exp_end = st.text_input("End Date (YYYY-MM)", placeholder="2023-08")
            exp_current = st.checkbox("I currently work here")
            exp_bullets = st.text_area("Bullet points (one per line)", height=100,
                                       placeholder="- Built a Python API serving 10k requests/day\n- Reduced database query time by 40%")
            add_exp = st.form_submit_button("Add Experience")
        if add_exp and exp_company and exp_title:
            add_work_experience(user["id"], exp_company, exp_title, exp_location,
                                exp_start, exp_end, exp_current, exp_bullets, db)
            st.success(f"Added experience at {exp_company}")
            st.rerun()

    experiences = get_work_experience(user["id"], db)
    if experiences:
        for exp in experiences:
            with st.expander(f"{exp['title']} at {exp['company']}"):
                with st.form(f"edit_exp_{exp['id']}"):
                    ee_company = st.text_input("Company", value=exp["company"], key=f"ee_company_{exp['id']}")
                    ee_title = st.text_input("Job Title", value=exp["title"], key=f"ee_title_{exp['id']}")
                    ee_location = st.text_input("Location", value=exp.get("location", ""), key=f"ee_location_{exp['id']}")
                    c1, c2 = st.columns(2)
                    with c1:
                        ee_start = st.text_input("Start Date", value=exp.get("start_date", ""), key=f"ee_start_{exp['id']}")
                    with c2:
                        ee_end = st.text_input("End Date", value=exp.get("end_date", ""), key=f"ee_end_{exp['id']}")
                    ee_current = st.checkbox("I currently work here", value=bool(exp.get("is_current")), key=f"ee_current_{exp['id']}")
                    ee_bullets = st.text_area("Bullet points", value=exp.get("bullets", ""), height=100, key=f"ee_bullets_{exp['id']}")
                    c1, c2 = st.columns(2)
                    with c1:
                        save_exp = st.form_submit_button("Save")
                    with c2:
                        del_exp = st.form_submit_button("Delete", type="secondary")
                if save_exp:
                    update_work_experience(user["id"], exp["id"], ee_company, ee_title, ee_location,
                                           ee_start, ee_end, ee_current, ee_bullets, db)
                    st.success("Experience updated")
                    st.rerun()
                if del_exp:
                    delete_work_experience(user["id"], exp["id"], db)
                    st.success("Experience deleted")
                    st.rerun()
    else:
        st.info("No work experience yet. Add one above.")

    # ============== PROJECTS ==============
    st.markdown("---")
    st.header("Projects")
    with st.expander("Add Project"):
        with st.form("add_project_form"):
            proj_name = st.text_input("Project Name", placeholder="Job Matching App")
            proj_desc = st.text_area("Description", placeholder="A web app that uses AI to match resumes to jobs")
            proj_tech = st.text_input("Technologies (comma separated)", placeholder="Python, Streamlit, SQLite")
            proj_link = st.text_input("Project Link", placeholder="https://github.com/username/project")
            c1, c2 = st.columns(2)
            with c1:
                proj_start = st.text_input("Start Date (YYYY-MM)", placeholder="2024-01")
            with c2:
                proj_end = st.text_input("End Date (YYYY-MM)", placeholder="2024-06")
            proj_current = st.checkbox("This project is ongoing")
            add_proj = st.form_submit_button("Add Project")
        if add_proj and proj_name:
            add_project(user["id"], proj_name, proj_desc, proj_tech, proj_link,
                        proj_start, proj_end, proj_current, db)
            st.success(f"Added project: {proj_name}")
            st.rerun()

    projects = get_projects(user["id"], db)
    if projects:
        for proj in projects:
            with st.expander(f"{proj['name']}"):
                with st.form(f"edit_proj_{proj['id']}"):
                    ep_name = st.text_input("Name", value=proj["name"], key=f"ep_name_{proj['id']}")
                    ep_desc = st.text_area("Description", value=proj.get("description", ""), key=f"ep_desc_{proj['id']}")
                    ep_tech = st.text_input("Technologies", value=proj.get("technologies", ""), key=f"ep_tech_{proj['id']}")
                    ep_link = st.text_input("Link", value=proj.get("link", ""), key=f"ep_link_{proj['id']}")
                    c1, c2 = st.columns(2)
                    with c1:
                        ep_start = st.text_input("Start Date", value=proj.get("start_date", ""), key=f"ep_start_{proj['id']}")
                    with c2:
                        ep_end = st.text_input("End Date", value=proj.get("end_date", ""), key=f"ep_end_{proj['id']}")
                    ep_current = st.checkbox("Ongoing", value=bool(proj.get("is_current")), key=f"ep_current_{proj['id']}")
                    c1, c2 = st.columns(2)
                    with c1:
                        save_proj = st.form_submit_button("Save")
                    with c2:
                        del_proj = st.form_submit_button("Delete", type="secondary")
                if save_proj:
                    update_project(user["id"], proj["id"], ep_name, ep_desc, ep_tech, ep_link,
                                   ep_start, ep_end, ep_current, db)
                    st.success("Project updated")
                    st.rerun()
                if del_proj:
                    delete_project(user["id"], proj["id"], db)
                    st.success("Project deleted")
                    st.rerun()
                if proj.get("link"):
                    st.link_button("View Project", proj["link"])
    else:
        st.info("No projects yet. Add one above.")

elif page == "Upload Transcript":
    st.title("Upload Transcript")
    st.markdown("Upload an academic transcript. The AI will extract the institution, degree, and courses, then you review and confirm before saving.")

    # Initialize review state
    if "transcript_review" not in st.session_state:
        st.session_state.transcript_review = None

    transcript_file = st.file_uploader("Upload Transcript PDF", type=["pdf"])
    syllabus_files = st.file_uploader("Upload Syllabus PDFs (Optional)", type=["pdf"], accept_multiple_files=True)

    if transcript_file and not st.session_state.transcript_review:
        save_path = os.path.join(user_paths["uploads_dir"], transcript_file.name)
        with open(save_path, "wb") as f:
            f.write(transcript_file.getbuffer())
        st.success(f"Saved {save_path}")

        if st.button("Extract Courses"):
            if not Config.ai_available():
                st.error("AI not configured. Add GEMINI_API_KEY to .env")
            else:
                with st.spinner("Parsing transcript with AI..."):
                    try:
                        result = parse_transcript(save_path)
                        raw_text = result["raw_text"]
                        extracted = extractor.extract_courses(raw_text)

                        # Optional syllabus enhancement
                        syllabi_texts = []
                        if syllabus_files:
                            for syl in syllabus_files:
                                syl_path = os.path.join(user_paths["uploads_dir"], syl.name)
                                with open(syl_path, "wb") as f:
                                    f.write(syl.getbuffer())
                                syl_data = parse_syllabus(syl_path)
                                syllabi_texts.append(syl_data["raw_text"])
                            if syllabi_texts:
                                enhanced = extractor.enhance_with_syllabi(extracted.get("courses", []), syllabi_texts)
                                for c, e in zip(extracted.get("courses", []), enhanced):
                                    c["description"] = e.get("description", c.get("description", ""))

                        st.session_state.transcript_review = {
                            "extracted": extracted,
                            "raw_text": raw_text,
                            "save_path": save_path
                        }
                        st.rerun()
                    except Exception as e:
                        st.error(f"Extraction failed: {e}")

    # ============== REVIEW & CONFIRM ==============
    review = st.session_state.transcript_review
    if review:
        extracted = review["extracted"]
        institutions = get_institutions(user["id"], db)
        degrees = get_degrees(user["id"], db)

        ext_insts = extracted.get("institutions", [])
        ext_degs = extracted.get("degrees", [])
        ext_courses = extracted.get("courses", [])

        if len(ext_insts) > 1 or len(ext_degs) > 1:
            st.warning("This transcript seems to contain multiple institutions or degrees. Only the first one will be matched in this review; manage the rest on the Education page.")

        ext_inst = ext_insts[0] if ext_insts else {}
        ext_deg = ext_degs[0] if ext_degs else {}

        st.markdown("---")
        st.subheader("Review Extracted Data")

        # Match to existing (outside form so they update immediately)
        col_match_inst, col_match_deg = st.columns(2)
        with col_match_inst:
            inst_options = [(None, "Create new institution")] + [(i["id"], i["name"]) for i in institutions]
            matched_inst = find_matching_institution(user["id"], ext_inst.get("name", ""), db)
            default_inst_idx = next((idx for idx, (iid, _) in enumerate(inst_options) if iid == (matched_inst["id"] if matched_inst else None)), 0)
            selected_inst_label = st.selectbox("Match institution to", [name for _, name in inst_options], index=default_inst_idx, key="review_inst")
            selected_inst_id = inst_options[[name for _, name in inst_options].index(selected_inst_label)][0]
            selected_inst = next((i for i in institutions if i["id"] == selected_inst_id), None)

        with col_match_deg:
            degree_options = [(None, "Create new degree")] + [(d["id"], d["degree_name"]) for d in degrees]
            matched_degree = None
            if selected_inst_id:
                matched_degree = find_matching_degree(user["id"], selected_inst_id, ext_deg.get("degree_name", ""), db)
            default_deg_idx = next((idx for idx, (did, _) in enumerate(degree_options) if did == (matched_degree["id"] if matched_degree else None)), 0)
            selected_deg_label = st.selectbox("Match degree to", [name for _, name in degree_options], index=default_deg_idx, key="review_deg")
            selected_deg_id = degree_options[[name for _, name in degree_options].index(selected_deg_label)][0]
            selected_deg = next((d for d in degrees if d["id"] == selected_deg_id), None)

        # Pre-fill values from existing selection or extracted data
        inst_name_default = selected_inst["name"] if selected_inst else ext_inst.get("name", "")
        inst_type_default = selected_inst["institution_type"] if selected_inst else ext_inst.get("institution_type", "other")
        inst_location_default = selected_inst.get("location", "") if selected_inst else ext_inst.get("location", "")

        deg_name_default = selected_deg["degree_name"] if selected_deg else ext_deg.get("degree_name", "")
        deg_type_default = selected_deg["degree_type"] if selected_deg else ext_deg.get("degree_type", "other")
        deg_field_default = selected_deg.get("field", "") if selected_deg else ext_deg.get("field", "")
        deg_start_default = selected_deg.get("start_date", "") if selected_deg else ext_deg.get("start_date", "")
        deg_end_default = selected_deg.get("end_date", "") if selected_deg else ext_deg.get("end_date", "")
        deg_gpa_default = selected_deg.get("gpa", "") if selected_deg else ext_deg.get("gpa", "")
        deg_honors_default = selected_deg.get("honors", "") if selected_deg else ext_deg.get("honors", "")
        deg_current_default = bool(selected_deg.get("is_current")) if selected_deg else bool(ext_deg.get("is_current", False))

        with st.form("review_form"):
            st.markdown("#### Institution Details")
            ri_name = st.text_input("Institution Name", value=inst_name_default, key="ri_name")
            ri_type = st.selectbox("Type", ["university", "community_college", "high_school", "certificate_organization", "other"],
                                   index=["university", "community_college", "high_school", "certificate_organization", "other"].index(inst_type_default),
                                   key="ri_type")
            ri_location = st.text_input("Location", value=inst_location_default, key="ri_location")

            st.markdown("#### Degree Details")
            rd_name = st.text_input("Degree Name", value=deg_name_default, key="rd_name")
            rd_type = st.selectbox("Degree Type", ["high_school_diploma", "associates", "bachelors", "masters", "doctorate", "certificate", "other"],
                                   index=["high_school_diploma", "associates", "bachelors", "masters", "doctorate", "certificate", "other"].index(deg_type_default),
                                   key="rd_type")
            rd_field = st.text_input("Field", value=deg_field_default, key="rd_field")
            c1, c2 = st.columns(2)
            with c1:
                rd_start = st.text_input("Start Date", value=deg_start_default, key="rd_start")
            with c2:
                rd_end = st.text_input("End Date", value=deg_end_default, key="rd_end")
            rd_gpa = st.text_input("GPA", value=deg_gpa_default, key="rd_gpa")
            rd_honors = st.text_input("Honors", value=deg_honors_default, key="rd_honors")
            rd_current = st.checkbox("Currently enrolled", value=deg_current_default, key="rd_current")

            st.markdown(f"#### Courses ({len(ext_courses)})")
            st.markdown("Toggle **Major Related** for each course. Only major-related courses will appear on your resume by default.")
            for idx, c in enumerate(ext_courses):
                cols = st.columns([3, 2, 1])
                with cols[0]:
                    st.markdown(f"**{c.get('code', '')}** — {c.get('name', '')}")
                with cols[1]:
                    st.markdown(f"Grade: {c.get('grade', '')}, Credits: {c.get('credits', '')}, Term: {c.get('term', '')}")
                with cols[2]:
                    st.checkbox("Major related", value=True, key=f"review_major_{idx}")

            save_review = st.form_submit_button("✅ Save to My Education", type="primary")

        if save_review:
            review_data = {
                "institution": {
                    "id": selected_inst_id,
                    "name": ri_name,
                    "institution_type": ri_type,
                    "location": ri_location
                },
                "degree": {
                    "id": selected_deg_id,
                    "degree_name": rd_name,
                    "degree_type": rd_type,
                    "field": rd_field,
                    "start_date": rd_start,
                    "end_date": rd_end,
                    "gpa": rd_gpa,
                    "honors": rd_honors,
                    "is_current": rd_current
                },
                "courses": [
                    {
                        **c,
                        "is_major_related": st.session_state.get(f"review_major_{idx}", True)
                    }
                    for idx, c in enumerate(ext_courses)
                ]
            }

            with st.spinner("Saving..."):
                try:
                    save_from_review(user["id"], review_data, db)

                    # Extract skills from the saved courses
                    skills = extractor.extract_skills(review_data["courses"])
                    for s in skills:
                        try:
                            db.execute(
                                "INSERT OR IGNORE INTO skills (user_id, name, category, proficiency, source) VALUES (?, ?, ?, ?, ?)",
                                (user["id"], s.get("name"), s.get("category"), s.get("proficiency"), s.get("source"))
                            )
                        except Exception:
                            pass

                    st.success(f"Saved {len(ext_courses)} courses!")
                    st.session_state.transcript_review = None
                    for idx in range(len(ext_courses)):
                        st.session_state.pop(f"review_major_{idx}", None)
                    st.rerun()
                except Exception as e:
                    st.error(f"Save failed: {e}")

        if st.button("Cancel Review"):
            st.session_state.transcript_review = None
            for idx in range(len(ext_courses)):
                st.session_state.pop(f"review_major_{idx}", None)
            st.rerun()

    # ============== EXISTING EDUCATION ==============
    grouped = get_courses_grouped(user["id"], db)
    if grouped:
        st.markdown("---")
        st.subheader("Your Education")
        for inst in grouped:
            with st.expander(f"🏫 {inst['name']} ({inst['institution_type']})" if inst['id'] else f"📁 {inst['name']}"):
                if inst.get("location"):
                    st.write(f"Location: {inst['location']}")

                for deg in inst.get("degrees", []):
                    st.markdown(f"#### 🎓 {deg['degree_name']}")
                    if deg.get("field"):
                        st.write(f"Field: {deg['field']}")
                    if deg.get("gpa"):
                        st.write(f"GPA: {deg['gpa']}")
                    if deg.get("start_date") or deg.get("end_date"):
                        st.write(f"{deg.get('start_date', '')} — {deg.get('end_date', 'Present') if deg.get('is_current') else deg.get('end_date', '')}")
                    if deg.get("courses"):
                        for c in deg["courses"]:
                            major_flag = "✅" if c.get("is_major_related") else "⬜"
                            st.write(f"- {major_flag} **{c['code']}** — {c['name']} (Grade: {c['grade']}, Credits: {c['credits']}, Term: {c.get('term', 'N/A')})")
                    else:
                        st.caption("No courses assigned to this degree yet.")

                if inst.get("unassigned_courses"):
                    st.markdown("#### 📄 Unassigned Courses")
                    for c in inst["unassigned_courses"]:
                        major_flag = "✅" if c.get("is_major_related") else "⬜"
                        st.write(f"- {major_flag} **{c['code']}** — {c['name']} (Grade: {c['grade']}, Credits: {c['credits']}, Term: {c.get('term', 'N/A')})")
            st.markdown("---")

elif page == "Skills & Certificates":
    st.title("Skills & Certificates")

    # ============================================
    # SKILLS SECTION
    # ============================================
    st.markdown("---")
    st.header("Skills")
    st.markdown("View, organize, add, and delete your skills.")

    skills = db.fetchall("SELECT * FROM skills ORDER BY category, name")

    # Add new skill
    with st.expander("Add New Skill", expanded=False):
        with st.form("add_skill_form"):
            new_name = st.text_input("Skill Name")
            new_category = st.selectbox(
                "Category",
                ["Programming Language", "Framework", "Tool", "Concept", "Database", "Cloud",
                 "DevOps", "Data Science", "Machine Learning", "Web Development",
                 "Mobile Development", "Security", "Algorithm", "Theory", "Soft Skill", "Other"]
            )
            new_proficiency = st.selectbox("Proficiency", ["Beginner", "Intermediate", "Advanced", "Expert"])
            new_source = st.text_input("Source (e.g., Course or Project)", value="Manual entry")
            submitted = st.form_submit_button("Add Skill")

        if submitted and new_name:
            try:
                db.execute(
                    "INSERT INTO skills (user_id, name, category, proficiency, source) VALUES (?, ?, ?, ?, ?)",
                    (user["id"], new_name, new_category, new_proficiency, new_source)
                )
                st.success(f"Added skill: {new_name}")
                st.rerun()
            except Exception as e:
                st.error(f"Could not add skill: {e}")

    # Show skills grouped by category with management actions
    if skills:
        st.markdown(f"**Your Skills ({len(skills)} total)**")
        skill_cats = {}
        for s in skills:
            cat = s.get("category", "Other")
            skill_cats.setdefault(cat, []).append(s)

        for cat, cat_skills in skill_cats.items():
            with st.expander(f"{cat} ({len(cat_skills)} skills)", expanded=False):
                for s in cat_skills:
                    cols = st.columns([3, 2, 2, 2, 1])
                    with cols[0]:
                        st.markdown(f"**{s['name']}**")
                    with cols[1]:
                        st.markdown(f"*{s.get('proficiency', 'N/A')}*")
                    with cols[2]:
                        st.markdown(f"_{s.get('source', '')}_")
                    with cols[3]:
                        if st.button("Edit", key=f"edit_skill_{s['id']}"):
                            st.session_state[f"edit_skill_{s['id']}"] = True
                            st.rerun()
                    with cols[4]:
                        if st.button("Delete", key=f"del_skill_{s['id']}"):
                            db.execute("DELETE FROM skills WHERE id = ?", (s['id'],))
                            st.success(f"Deleted {s['name']}")
                            st.rerun()

                    if st.session_state.get(f"edit_skill_{s['id']}", False):
                        with st.form(f"edit_form_{s['id']}"):
                            edit_name = st.text_input("Name", value=s['name'], key=f"edit_name_{s['id']}")
                            cat_options = ["Programming Language", "Framework", "Tool", "Concept", "Database", "Cloud",
                                         "DevOps", "Data Science", "Machine Learning", "Web Development",
                                         "Mobile Development", "Security", "Algorithm", "Theory", "Soft Skill", "Other"]
                            try:
                                cat_idx = cat_options.index(s.get("category", "Other"))
                            except ValueError:
                                cat_idx = 15
                            edit_category = st.selectbox("Category", cat_options, index=cat_idx, key=f"edit_cat_{s['id']}")
                            prof_options = ["Beginner", "Intermediate", "Advanced", "Expert"]
                            try:
                                prof_idx = prof_options.index(s.get("proficiency", "Beginner"))
                            except ValueError:
                                prof_idx = 0
                            edit_prof = st.selectbox("Proficiency", prof_options, index=prof_idx, key=f"edit_prof_{s['id']}")
                            edit_source = st.text_input("Source", value=s.get("source", ""), key=f"edit_src_{s['id']}")
                            save_edit = st.form_submit_button("Save")

                        if save_edit:
                            db.execute(
                                "UPDATE skills SET name = ?, category = ?, proficiency = ?, source = ? WHERE id = ?",
                                (edit_name, edit_category, edit_prof, edit_source, s['id'])
                            )
                            st.session_state.pop(f"edit_skill_{s['id']}", None)
                            st.success(f"Updated {edit_name}")
                            st.rerun()
    else:
        st.info("No skills yet. Upload your transcript to auto-extract, or add skills manually above.")

    # ============================================
    # CERTIFICATES SECTION
    # ============================================
    st.markdown("---")
    st.header("Certificates & Certifications")
    st.markdown("Add professional certifications, licenses, and credentials. These boost your job matching and appear on generated resumes.")

    certificates = db.fetchall("SELECT * FROM certificates ORDER BY date_obtained DESC")

    # Add new certificate
    with st.expander("Add New Certificate", expanded=False):
        with st.form("add_cert_form"):
            cert_name = st.text_input("Certificate Name", placeholder="e.g., AWS Certified Solutions Architect")
            cert_issuer = st.text_input("Issuing Organization", placeholder="e.g., Amazon Web Services")
            cert_date = st.text_input("Date Obtained (YYYY-MM)", placeholder="2024-06")
            cert_expiry = st.text_input("Expiry Date (YYYY-MM, optional)", placeholder="2027-06")
            cert_id = st.text_input("Credential ID (optional)")
            cert_url = st.text_input("Verification URL (optional)")
            cert_desc = st.text_area("Description / Notes", placeholder="Briefly describe what this cert covers...")
            cert_submitted = st.form_submit_button("Add Certificate")

        if cert_submitted and cert_name:
            try:
                db.execute(
                    "INSERT INTO certificates (user_id, name, issuer, date_obtained, expiry, credential_id, url, description) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (user["id"], cert_name, cert_issuer, cert_date or None, cert_expiry or None, cert_id or None, cert_url or None, cert_desc or None)
                )
                st.success(f"Added certificate: {cert_name}")
                st.rerun()
            except Exception as e:
                st.error(f"Could not add certificate: {e}")

    # Show certificates
    if certificates:
        st.markdown(f"**Your Certificates ({len(certificates)} total)**")
        for cert in certificates:
            with st.expander(f"{cert['name']} — {cert.get('issuer', 'Unknown')}", expanded=False):
                cols = st.columns([2, 2, 2, 1])
                with cols[0]:
                    st.markdown(f"**Issued:** {cert.get('date_obtained', 'N/A')}")
                    if cert.get('expiry'):
                        st.markdown(f"**Expires:** {cert['expiry']}")
                with cols[1]:
                    if cert.get('credential_id'):
                        st.markdown(f"**Credential ID:** `{cert['credential_id']}`")
                with cols[2]:
                    if cert.get('url'):
                        st.link_button("Verify Certificate", cert['url'])
                with cols[3]:
                    if st.button("Delete", key=f"del_cert_{cert['id']}"):
                        db.execute("DELETE FROM certificates WHERE id = ?", (cert['id'],))
                        st.success(f"Deleted {cert['name']}")
                        st.rerun()
                if cert.get('description'):
                    st.markdown(f"_{cert['description']}_")
    else:
        st.info("No certificates added yet. Add them above to include in job matching and resumes.")

elif page == "Resume Editor":
    st.title("Resume Editor")
    st.markdown("Build and customize your resume section by section. AI can help improve wording, and the ATS checker gives quick feedback.")

    # Load or initialize resume data
    if "resume_data" not in st.session_state:
        latest = get_latest_resume_version(user["id"], db)
        if latest:
            st.session_state.resume_data = latest
        else:
            st.session_state.resume_data = build_resume_data(user["id"], db)

    resume_data = st.session_state.resume_data
    ai_helper = ResumeAIHelper()

    # Sidebar controls
    st.sidebar.markdown("### Resume Controls")
    template = st.sidebar.selectbox("Template", ["classic", "modern", "minimal"], index=["classic", "modern", "minimal"].index(resume_data.get("template", "classic")))
    resume_data["template"] = template
    resume_title = st.sidebar.text_input("Resume Title", value=resume_data.get("title", "My Resume"))
    resume_data["title"] = resume_title

    if st.sidebar.button("Reset from Profile Data", use_container_width=True):
        st.session_state.resume_data = build_resume_data(user["id"], db, title=resume_title, template=template)
        st.success("Resume reset from profile.")
        st.rerun()

    if st.sidebar.button("Save Version", use_container_width=True, type="primary"):
        save_resume_version(user["id"], None, resume_data, db)
        st.success("Resume version saved!")

    # Editor layout
    editor_tab, preview_tab, ats_tab = st.tabs(["Edit", "Preview", "ATS Check"])

    with editor_tab:
        # Profile section
        with st.expander("Profile / Contact", expanded=True):
            profile_sec = resume_data.get("profile", {})
            c1, c2 = st.columns(2)
            with c1:
                profile_sec["full_name"] = st.text_input("Full Name", value=profile_sec.get("full_name", ""), key="re_full_name")
                profile_sec["email"] = st.text_input("Email", value=profile_sec.get("email", ""), key="re_email")
                profile_sec["phone"] = st.text_input("Phone", value=profile_sec.get("phone", ""), key="re_phone")
                profile_sec["location"] = st.text_input("Location", value=profile_sec.get("location", ""), key="re_location")
            with c2:
                profile_sec["linkedin"] = st.text_input("LinkedIn", value=profile_sec.get("linkedin", ""), key="re_linkedin")
                profile_sec["portfolio"] = st.text_input("Portfolio", value=profile_sec.get("portfolio", ""), key="re_portfolio")
                profile_sec["github"] = st.text_input("GitHub", value=profile_sec.get("github", ""), key="re_github")
            summary_col, ai_col = st.columns([3, 1])
            with summary_col:
                profile_sec["summary"] = st.text_area("Professional Summary", value=profile_sec.get("summary", ""), height=120, key="re_summary")
            with ai_col:
                st.markdown("&nbsp;")
                if st.button("✨ Improve Summary", use_container_width=True):
                    profile = get_profile(user["id"]) or {}
                    improved = ai_helper.improve_summary(profile_sec.get("summary", ""), profile.get("target_roles", ""), profile)
                    profile_sec["summary"] = improved
                    st.session_state.resume_data = resume_data
                    st.success("Summary updated")
                    st.rerun()
            resume_data["profile"] = profile_sec

        # Section order
        with st.expander("Section Order"):
            current_order = resume_data.get("section_order", ["summary", "experience", "education", "skills", "projects", "certifications"])
            for i, sec in enumerate(current_order):
                cols = st.columns([4, 1, 1])
                with cols[0]:
                    st.markdown(f"**{i+1}. {sec.capitalize()}**")
                with cols[1]:
                    if st.button("⬆️", key=f"sec_up_{sec}"):
                        if i > 0:
                            current_order[i-1], current_order[i] = current_order[i], current_order[i-1]
                            st.session_state.resume_data["section_order"] = current_order
                            st.rerun()
                with cols[2]:
                    if st.button("⬇️", key=f"sec_down_{sec}"):
                        if i < len(current_order) - 1:
                            current_order[i], current_order[i+1] = current_order[i+1], current_order[i]
                            st.session_state.resume_data["section_order"] = current_order
                            st.rerun()

        # Experience section
        with st.expander("Experience"):
            for idx, exp in enumerate(resume_data.get("experience", [])):
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        exp["title"] = st.text_input("Title", value=exp.get("title", ""), key=f"re_exp_title_{idx}")
                        exp["company"] = st.text_input("Company", value=exp.get("company", ""), key=f"re_exp_company_{idx}")
                        exp["location"] = st.text_input("Location", value=exp.get("location", ""), key=f"re_exp_loc_{idx}")
                    with c2:
                        exp["start_date"] = st.text_input("Start", value=exp.get("start_date", ""), key=f"re_exp_start_{idx}")
                        exp["end_date"] = st.text_input("End", value=exp.get("end_date", ""), key=f"re_exp_end_{idx}")
                        exp["is_current"] = st.checkbox("Current", value=bool(exp.get("is_current", False)), key=f"re_exp_current_{idx}")
                    bullets_col, ai_col = st.columns([3, 1])
                    with bullets_col:
                        exp["bullets"] = st.text_area("Bullet points (one per line)", value=exp.get("bullets", ""), height=120, key=f"re_exp_bullets_{idx}")
                    with ai_col:
                        st.markdown("&nbsp;")
                        if st.button("✨ Improve Bullets", key=f"re_exp_ai_{idx}", use_container_width=True):
                            improved = ai_helper.improve_bullets(exp.get("bullets", ""), exp.get("title", ""), exp.get("company", ""))
                            exp["bullets"] = improved
                            st.session_state.resume_data = resume_data
                            st.success("Bullets updated")
                            st.rerun()
                    if st.button("Delete Experience", key=f"re_exp_del_{idx}", type="secondary"):
                        resume_data["experience"].pop(idx)
                        st.session_state.resume_data = resume_data
                        st.rerun()
            if st.button("+ Add Experience"):
                resume_data.setdefault("experience", []).append({
                    "title": "", "company": "", "location": "", "start_date": "", "end_date": "",
                    "is_current": False, "bullets": ""
                })
                st.session_state.resume_data = resume_data
                st.rerun()

        # Education section
        with st.expander("Education"):
            for idx, edu in enumerate(resume_data.get("education", [])):
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        edu["school"] = st.text_input("School", value=edu.get("school", ""), key=f"re_edu_school_{idx}")
                        edu["degree"] = st.text_input("Degree", value=edu.get("degree", ""), key=f"re_edu_degree_{idx}")
                        edu["field"] = st.text_input("Field", value=edu.get("field", ""), key=f"re_edu_field_{idx}")
                    with c2:
                        edu["graduation_date"] = st.text_input("Graduation Date", value=edu.get("graduation_date", ""), key=f"re_edu_grad_{idx}")
                        edu["gpa"] = st.text_input("GPA", value=edu.get("gpa", ""), key=f"re_edu_gpa_{idx}")
                        edu["honors"] = st.text_input("Honors", value=edu.get("honors", ""), key=f"re_edu_honors_{idx}")
                        edu["is_current"] = st.checkbox("Current", value=bool(edu.get("is_current", False)), key=f"re_edu_current_{idx}")
                    if st.button("Delete Education", key=f"re_edu_del_{idx}", type="secondary"):
                        resume_data["education"].pop(idx)
                        st.session_state.resume_data = resume_data
                        st.rerun()
            if st.button("+ Add Education"):
                resume_data.setdefault("education", []).append({
                    "school": "", "degree": "", "field": "", "graduation_date": "", "gpa": "", "honors": "", "is_current": False
                })
                st.session_state.resume_data = resume_data
                st.rerun()

        # Skills section
        with st.expander("Skills"):
            for idx, skill_group in enumerate(resume_data.get("skills", [])):
                cols = st.columns([2, 3, 1])
                with cols[0]:
                    skill_group["category"] = st.text_input("Category", value=skill_group.get("category", ""), key=f"re_skill_cat_{idx}")
                with cols[1]:
                    skill_group["skills"] = st.text_input("Skills (comma separated)", value=", ".join(skill_group.get("skills", [])), key=f"re_skills_{idx}").split(",")
                    skill_group["skills"] = [s.strip() for s in skill_group["skills"] if s.strip()]
                with cols[2]:
                    if st.button("Delete", key=f"re_skill_del_{idx}", type="secondary"):
                        resume_data["skills"].pop(idx)
                        st.session_state.resume_data = resume_data
                        st.rerun()
            if st.button("+ Add Skill Group"):
                resume_data.setdefault("skills", []).append({"category": "", "skills": []})
                st.session_state.resume_data = resume_data
                st.rerun()
            st.markdown("#### AI Skill Suggestions")
            job_desc = st.text_area("Paste a job description for skill suggestions", height=80, key="re_job_desc_skills")
            if st.button("Suggest Skills"):
                all_skills = []
                for g in resume_data.get("skills", []):
                    all_skills.extend(g.get("skills", []))
                suggestions = ai_helper.suggest_skills(job_desc, all_skills, profile_sec.get("summary", ""))
                if suggestions:
                    resume_data.setdefault("skills", []).append({"category": "Suggested", "skills": suggestions})
                    st.session_state.resume_data = resume_data
                    st.success(f"Added suggestions: {', '.join(suggestions)}")
                    st.rerun()
                else:
                    st.info("No suggestions returned. Make sure AI is configured.")

        # Projects section
        with st.expander("Projects"):
            for idx, proj in enumerate(resume_data.get("projects", [])):
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        proj["name"] = st.text_input("Name", value=proj.get("name", ""), key=f"re_proj_name_{idx}")
                        proj["technologies"] = st.text_input("Technologies", value=proj.get("technologies", ""), key=f"re_proj_tech_{idx}")
                        proj["link"] = st.text_input("Link", value=proj.get("link", ""), key=f"re_proj_link_{idx}")
                    with c2:
                        proj["start_date"] = st.text_input("Start", value=proj.get("start_date", ""), key=f"re_proj_start_{idx}")
                        proj["end_date"] = st.text_input("End", value=proj.get("end_date", ""), key=f"re_proj_end_{idx}")
                        proj["is_current"] = st.checkbox("Current", value=bool(proj.get("is_current", False)), key=f"re_proj_current_{idx}")
                    proj["description"] = st.text_area("Description", value=proj.get("description", ""), key=f"re_proj_desc_{idx}")
                    if st.button("Delete Project", key=f"re_proj_del_{idx}", type="secondary"):
                        resume_data["projects"].pop(idx)
                        st.session_state.resume_data = resume_data
                        st.rerun()
            if st.button("+ Add Project"):
                resume_data.setdefault("projects", []).append({
                    "name": "", "description": "", "technologies": "", "link": "", "start_date": "", "end_date": "", "is_current": False
                })
                st.session_state.resume_data = resume_data
                st.rerun()

        # Certifications section
        with st.expander("Certifications"):
            for idx, cert in enumerate(resume_data.get("certifications", [])):
                cols = st.columns([3, 2, 2, 1])
                with cols[0]:
                    cert["name"] = st.text_input("Name", value=cert.get("name", ""), key=f"re_cert_name_{idx}")
                with cols[1]:
                    cert["organization"] = st.text_input("Organization", value=cert.get("organization", ""), key=f"re_cert_org_{idx}")
                with cols[2]:
                    cert["date"] = st.text_input("Date", value=cert.get("date", ""), key=f"re_cert_date_{idx}")
                with cols[3]:
                    if st.button("Delete", key=f"re_cert_del_{idx}", type="secondary"):
                        resume_data["certifications"].pop(idx)
                        st.session_state.resume_data = resume_data
                        st.rerun()
            if st.button("+ Add Certification"):
                resume_data.setdefault("certifications", []).append({"name": "", "organization": "", "date": ""})
                st.session_state.resume_data = resume_data
                st.rerun()

    with preview_tab:
        try:
            html = render_resume_html(resume_data, template)
            st.components.v1.html(html, height=800, scrolling=True)
            if st.button("Export PDF", type="primary"):
                pdf_path = render_resume_pdf(resume_data, template)
                with open(pdf_path, "rb") as f:
                    st.download_button("Download PDF", f, file_name=os.path.basename(pdf_path), mime="application/pdf")
        except Exception as e:
            st.error(f"Preview failed: {e}")

    with ats_tab:
        job_desc_ats = st.text_area("Paste job description (optional)", height=120, key="re_ats_job")
        checker = ATSChecker(resume_data, job_desc_ats)
        result = checker.check()
        st.metric("ATS Score", f"{result['score']}/100")
        st.progress(result["score"] / 100.0)
        if result["issues"]:
            st.markdown("#### Suggestions")
            for issue in result["issues"]:
                st.markdown(f"- {issue}")
        else:
            st.success("No major issues detected.")
        if result["missing_keywords"]:
            st.markdown("#### Missing Keywords")
            st.markdown(", ".join(result["missing_keywords"]))

    st.session_state.resume_data = resume_data

elif page == "Discover Jobs":
    st.title("Discover Jobs")
    st.markdown("AI will analyze your skills and find matching job listings.")

    skills = db.fetchall("SELECT * FROM skills")
    courses = db.fetchall("SELECT * FROM courses")
    certificates = db.fetchall("SELECT * FROM certificates")

    if not courses:
        st.warning("Upload your transcript first on the 'Upload Transcript' page.")
    elif not skills:
        st.warning("No skills extracted yet. Upload your transcript and extract skills.")
    else:
        # AI Keyword Generation
        st.markdown("---")
        st.subheader("AI-Generated Search Keywords")

        if st.button("Generate Keywords from My Skills", type="primary"):
            if not Config.ai_available():
                st.error("AI not configured")
            else:
                from app.ai.keywords import KeywordGenerator
                gen = KeywordGenerator()
                with st.spinner("Analyzing your skills for best search keywords..."):
                    try:
                        keywords_data = gen.generate(skills, courses, certificates)
                        st.session_state.keywords_data = keywords_data
                        st.rerun()
                    except Exception as e:
                        st.error(f"Keyword generation failed: {e}")

        keywords_data = st.session_state.get("keywords_data")

        if keywords_data:
            st.success("Keywords generated!")
            st.markdown("**Suggested Keywords:**")
            for kw in keywords_data.get("keywords", []):
                st.markdown(f"- `{kw}`")

            st.markdown("**Target Job Titles:**")
            for title in keywords_data.get("job_titles", []):
                st.markdown(f"- {title}")

        # Unified Search + Links Section
        st.markdown("---")
        st.subheader("Search Jobs")
        st.markdown("Enter keywords, location, and search all job sources at once.")

        search_cols = st.columns([3, 2, 1])
        with search_cols[0]:
            # Use ALL suggested keywords from AI if available
            if keywords_data:
                default_kw = " ".join(keywords_data.get("keywords", ["software engineer"]))
            else:
                default_kw = "software engineer"
            search_keywords = st.text_input(
                "Search Keywords",
                value=default_kw,
                key="search_keywords"
            )
        with search_cols[1]:
            search_location = st.text_input("Location (e.g., Los Angeles, Remote)", value="", key="search_location")
        with search_cols[2]:
            search_button = st.button("Search All Sources", key="search_jobs", type="primary")

        # Pre-compute LinkedIn and Indeed URLs based on current inputs
        from app.ai.keywords import KeywordGenerator
        kw_gen = KeywordGenerator()
        linkedin_url = kw_gen.build_linkedin_url(search_keywords, search_location)
        indeed_url = kw_gen.build_indeed_url(search_keywords, search_location)

        st.markdown("**Quick Search Links:**")
        link_cols = st.columns(3)
        with link_cols[0]:
            st.link_button("Browse LinkedIn Jobs", linkedin_url)
        with link_cols[1]:
            st.link_button("Browse Indeed Jobs", indeed_url)
        with link_cols[2]:
            st.caption("The Muse results appear below")

        if search_button:
            from app.scraper.muse import MuseAPI
            with st.spinner("Searching The Muse job board..."):
                try:
                    api = MuseAPI(user_paths["db_path"])
                    jobs_found = api.search(search_keywords, search_location, max_results=20)
                    added = api.save_jobs(jobs_found)
                    st.session_state.discovered_jobs = jobs_found
                    st.session_state.discovered_added = added
                    st.success(f"The Muse: Found {len(jobs_found)} jobs, added {added} new to your list!")
                except Exception as e:
                    st.error(f"The Muse search failed: {e}")

        # Show discovered Muse jobs
        discovered = st.session_state.get("discovered_jobs", [])
        if discovered:
            st.markdown(f"### The Muse Results ({len(discovered)})")
            for job in discovered:
                with st.expander(f"{job['title']} at {job['company']} — {job.get('location', 'N/A')}"):
                    st.write(job.get("description", "")[:500])
                    if job.get("url"):
                        st.link_button("View & Apply", job["url"])
                    if job.get("published"):
                        st.caption(f"Posted: {job['published'][:10]}")

        # Indeed Stealth Scraper
        st.markdown("---")
        st.subheader("Indeed Direct Scan (Stealth)")
        st.markdown("Optional slower scan using Playwright stealth browser.")

        indeed_cols = st.columns([3, 1])
        with indeed_cols[0]:
            indeed_keywords = st.text_input("Indeed Keywords", value=search_keywords if search_keywords else "software engineer", key="indeed_kw")
        with indeed_cols[1]:
            if st.button("Scan Indeed", key="indeed_search"):
                from app.scraper.indeed import IndeedScraper
                with st.spinner("Scanning Indeed (30-60 seconds)..."):
                    try:
                        scraper = IndeedScraper(db_path=user_paths["db_path"])
                        jobs_found = scraper.search(indeed_keywords, max_results=5)
                        added = scraper.save_jobs(jobs_found)
                        st.success(f"Indeed: found {len(jobs_found)} jobs, added {added} new!")
                        st.session_state.indeed_jobs = jobs_found
                    except Exception as e:
                        st.error(f"Indeed scraper failed: {e}")

        indeed_jobs = st.session_state.get("indeed_jobs", [])
        if indeed_jobs:
            st.markdown(f"### Indeed Results ({len(indeed_jobs)})")
            for job in indeed_jobs:
                with st.expander(f"{job['title']} at {job['company']} — {job.get('location', '')}"):
                    st.write(job.get("description", "")[:300])
                    if job.get("url"):
                        st.link_button("View on Indeed", job["url"])

        st.markdown("---")
        st.info("""
        **Next Steps:** After discovering jobs, go to the **Jobs** page to:
        - See AI match scores
        - Generate tailored resumes and cover letters
        - Get Q&A answers for applications
        """)

elif page == "Jobs":
    st.title("Jobs")
    st.markdown("Manage all tracked jobs. The AI will analyze fit against your courses and skills.")

    # Add job form
    with st.expander("Add Job Manually"):
        with st.form("add_job_form"):
            job_title = st.text_input("Job Title")
            company = st.text_input("Company")
            job_url = st.text_input("Job URL (LinkedIn/Indeed)")
            job_description = st.text_area("Job Description / Requirements", height=150)
            submitted = st.form_submit_button("Add Job")

        if submitted:
            if not job_title:
                st.error("Job title is required")
            else:
                final_desc = job_description
                if not final_desc and job_url:
                    from app.scraper.fetcher import fetch_job_page
                    with st.spinner("Fetching job page content..."):
                        fetched = fetch_job_page(job_url)
                        if fetched and not fetched.startswith("Error"):
                            final_desc = fetched
                            st.success("Fetched job description from URL!")
                        else:
                            st.warning(f"Could not fetch URL: {fetched}")

                db.execute(
                    "INSERT INTO jobs (user_id, title, company, url, description) VALUES (?, ?, ?, ?, ?)",
                    (user["id"], job_title, company, job_url, final_desc)
                )
                st.success("Job added!")
                st.rerun()

    # Job matching
    st.markdown("---")
    st.markdown("### Your Tracked Jobs")
    jobs = db.fetchall("SELECT * FROM jobs ORDER BY match_score DESC, created_at DESC")
    skills = db.fetchall("SELECT * FROM skills")
    courses = db.fetchall("SELECT * FROM courses")
    certificates = db.fetchall("SELECT * FROM certificates")

    if not jobs:
        st.info("No jobs tracked yet. Go to **Discover Jobs** to find listings!")
    elif not courses:
        st.warning("Upload your transcript first to enable matching.")
    else:
        for job in jobs:
            header = f"{job['title']} at {job['company']}"
            if job.get("match_score"):
                header += f" — Match: {job['match_score']:.0f}%"
            with st.expander(header):
                desc = job['description'] or ""
                st.write(desc[:800] + "..." if len(desc) > 800 else desc)
                if job['url']:
                    st.link_button("View Job Posting", job['url'])

                cols = st.columns([1, 1, 1])
                with cols[0]:
                    if st.button(f"Analyze Fit", key=f"match_{job['id']}"):
                        if not Config.ai_available():
                            st.error("AI not configured")
                        else:
                            from app.ai.matcher import JobMatcher
                            matcher = JobMatcher()
                            user_profile = get_profile(user["id"])
                            with st.spinner("Analyzing fit with AI..."):
                                try:
                                    result = matcher.match(skills, courses, certificates, job['description'] or "", user_profile)
                                    db.execute(
                                        "UPDATE jobs SET match_score = ?, missing_skills = ?, requirements = ? WHERE id = ?",
                                        (result.get("match_score"), json.dumps(result.get("missing_skills", [])), json.dumps(result), job['id'])
                                    )
                                    st.success(f"Match Score: {result['match_score']}%")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Matching failed: {e}")
                with cols[1]:
                    if st.button(f"Delete", key=f"del_{job['id']}"):
                        db.execute("DELETE FROM jobs WHERE id = ?", (job['id'],))
                        st.rerun()

                # Display stored fit analysis
                if job.get("requirements"):
                    try:
                        fit_data = json.loads(job["requirements"])
                        score = fit_data.get("match_score", 0)
                        score_color = "🟢" if score >= 70 else "🟡" if score >= 40 else "🔴"
                        st.markdown("---")
                        st.markdown(f"## {score_color} AI Fit Analysis: {score}%")
                        st.progress(score / 100.0)

                        if fit_data.get("summary"):
                            st.markdown(f"**Summary:** {fit_data['summary']}")

                        c1, c2 = st.columns(2)
                        with c1:
                            matching = fit_data.get("matching_skills", [])
                            if matching:
                                st.markdown("#### ✅ Matching Skills")
                                for skill in matching:
                                    st.markdown(f"<span style='background:#d4edda;padding:4px 10px;border-radius:12px;color:#155724;font-size:13px;margin:2px;display:inline-block;'>{skill}</span>", unsafe_allow_html=True)

                            rel_courses = fit_data.get("relevant_courses", [])
                            if rel_courses:
                                st.markdown("#### 📚 Relevant Courses")
                                for course in rel_courses:
                                    if isinstance(course, dict):
                                        st.markdown(f"- **{course.get('code', '')}** — {course.get('name', '')}")
                                    else:
                                        st.markdown(f"- {course}")

                            rel_certs = fit_data.get("relevant_certs", [])
                            if rel_certs:
                                st.markdown("#### 🏆 Relevant Certificates")
                                for cert in rel_certs:
                                    st.markdown(f"- {cert}")

                        with c2:
                            missing = fit_data.get("missing_skills", [])
                            if missing:
                                st.markdown("#### ⚠️ Missing Skills")
                                for skill in missing:
                                    st.markdown(f"<span style='background:#fff3cd;padding:4px 10px;border-radius:12px;color:#856404;font-size:13px;margin:2px;display:inline-block;'>{skill}</span>", unsafe_allow_html=True)

                            if fit_data.get("suggested_improvements"):
                                st.markdown("#### 💡 Suggested Improvements")
                                st.info(fit_data["suggested_improvements"])
                    except Exception:
                        pass

    # Show skill inventory
    if skills:
        st.markdown("---")
        st.subheader("Your Skills Inventory")
        skill_cats = {}
        for s in skills:
            cat = s.get("category", "Other")
            skill_cats.setdefault(cat, []).append(s["name"])
        for cat, names in skill_cats.items():
            st.markdown(f"**{cat}:** {', '.join(names)}")

elif page == "Generate Documents":
    st.title("Generate Documents")
    st.markdown("Select a job to generate a tailored resume, cover letter, and Q&A answers.")

    # Load profile for document generation
    profile = get_profile(user["id"])
    if not profile.get("full_name"):
        st.warning("Your profile is missing a full name. Go to **Profile** and fill it out first.")

    jobs = db.fetchall("SELECT * FROM jobs ORDER BY match_score DESC, created_at DESC")
    if not jobs:
        st.warning("No jobs added yet. Go to Jobs page first.")
    else:
        job_options = {f"{j['title']} at {j['company']}": j for j in jobs}
        selected = st.selectbox("Select Job", list(job_options.keys()))
        job = job_options[selected]

        skills = db.fetchall("SELECT * FROM skills")
        courses = db.fetchall("SELECT * FROM courses")
        certificates = db.fetchall("SELECT * FROM certificates")
        degrees = get_degrees(user["id"], db)
        work_experience = get_work_experience(user["id"], db)
        projects = get_projects(user["id"], db)

        if not courses:
            st.error("Upload your transcript first to generate documents.")
        elif not degrees:
            st.error("Add your degrees on the **Education** page first.")
        else:
            st.markdown("---")
            col1, col2, col3 = st.columns(3)

            with col1:
                if st.button("Generate Resume"):
                    if not Config.ai_available():
                        st.error("AI not configured")
                    else:
                        from app.ai.generator import DocumentGenerator
                        gen = DocumentGenerator()
                        with st.spinner("Generating resume with AI..."):
                            try:
                                data, filepath, html = gen.generate_resume(
                                    courses, skills, certificates, job, profile, degrees, work_experience, projects
                                )
                                # Ensure generated file goes to user's directory
                                filename = os.path.basename(filepath)
                                user_filepath = os.path.join(user_paths["generated_dir"], filename)
                                if filepath != user_filepath and os.path.exists(filepath):
                                    import shutil
                                    shutil.move(filepath, user_filepath)
                                    filepath = user_filepath

                                # Build full resume JSON for future editor
                                resume_data = {
                                    "profile": {
                                        "full_name": profile.get("full_name", ""),
                                        "email": profile.get("email", ""),
                                        "phone": profile.get("phone", ""),
                                        "location": profile.get("location", ""),
                                        "linkedin_url": profile.get("linkedin_url", ""),
                                        "github_url": profile.get("github_url", ""),
                                        "portfolio_url": profile.get("portfolio_url", ""),
                                        "summary": data.get("summary", profile.get("summary", ""))
                                    },
                                    "degrees": degrees,
                                    "work_experience": work_experience,
                                    "projects": projects,
                                    "skills": [s["name"] for s in skills],
                                    "certificates": [c["name"] for c in certificates],
                                    "courses": data.get("highlighted_courses", [c for c in courses if c.get("is_major_related", 1)][:10])
                                }
                                db.insert(
                                    "INSERT INTO resume_versions (user_id, job_id, resume_data) VALUES (?, ?, ?)",
                                    (user["id"], job['id'], json.dumps(resume_data))
                                )
                                db.execute(
                                    "INSERT INTO documents (user_id, job_id, doc_type, content, file_path) VALUES (?, ?, ?, ?, ?)",
                                    (user["id"], job['id'], "resume", json.dumps(data), filepath)
                                )
                                st.success(f"Resume generated!")
                                with open(filepath, "rb") as f:
                                    st.download_button("Download Resume PDF", f, file_name=os.path.basename(filepath), mime="application/pdf")
                                st.markdown("### Preview")
                                st.components.v1.html(html, height=600, scrolling=True)
                            except Exception as e:
                                st.error(f"Generation failed: {e}")

            with col2:
                if st.button("Generate Cover Letter"):
                    if not Config.ai_available():
                        st.error("AI not configured")
                    else:
                        from app.ai.generator import DocumentGenerator
                        gen = DocumentGenerator()
                        with st.spinner("Generating cover letter with AI..."):
                            try:
                                data, filepath, html = gen.generate_cover_letter(
                                    courses, skills, certificates, job, profile, degrees, work_experience, projects
                                )
                                filename = os.path.basename(filepath)
                                user_filepath = os.path.join(user_paths["generated_dir"], filename)
                                if filepath != user_filepath and os.path.exists(filepath):
                                    import shutil
                                    shutil.move(filepath, user_filepath)
                                    filepath = user_filepath
                                db.execute(
                                    "INSERT INTO documents (user_id, job_id, doc_type, content, file_path) VALUES (?, ?, ?, ?, ?)",
                                    (user["id"], job['id'], "cover_letter", json.dumps(data), filepath)
                                )
                                st.success(f"Cover letter generated!")
                                with open(filepath, "rb") as f:
                                    st.download_button("Download Cover Letter PDF", f, file_name=os.path.basename(filepath), mime="application/pdf")
                                st.markdown("### Preview")
                                st.components.v1.html(html, height=600, scrolling=True)
                            except Exception as e:
                                st.error(f"Generation failed: {e}")

            with col3:
                if st.button("Generate Q&A"):
                    if not Config.ai_available():
                        st.error("AI not configured")
                    else:
                        from app.ai.generator import DocumentGenerator
                        gen = DocumentGenerator()
                        with st.spinner("Generating Q&A with AI..."):
                            try:
                                qna = gen.generate_qna(
                                    courses, skills, certificates, job, profile, degrees, work_experience, projects
                                )
                                db.execute(
                                    "INSERT INTO documents (user_id, job_id, doc_type, content) VALUES (?, ?, ?, ?)",
                                    (user["id"], job['id'], "qna", json.dumps(qna))
                                )
                                st.success("Q&A generated!")
                                for item in qna:
                                    st.markdown(f"**Q: {item['question']}**")
                                    st.markdown(f"A: {item['answer']}")
                                    st.markdown("---")
                            except Exception as e:
                                st.error(f"Generation failed: {e}")

    # Show generated documents
    docs = db.fetchall("SELECT * FROM documents ORDER BY created_at DESC LIMIT 20")
    if docs:
        st.markdown("---")
        st.subheader("Recently Generated Documents")
        for d in docs:
            job_info = db.fetchone("SELECT title, company FROM jobs WHERE id = ?", (d['job_id'],))
            label = f"{d['doc_type'].upper()} for {job_info['title']} at {job_info['company']}"
            st.write(label)
            if d['file_path'] and os.path.exists(d['file_path']):
                with open(d['file_path'], "rb") as f:
                    st.download_button(f"Download {d['doc_type']}", f, file_name=os.path.basename(d['file_path']), mime="application/pdf", key=f"dl_{d['id']}")

elif page == "Settings":
    st.title("Settings")

    st.markdown("### Environment")
    st.json({
        "SCHEDULE_ENABLED": Config.SCHEDULE_ENABLED,
        "SCHEDULE_TIME": Config.SCHEDULE_TIME,
        "SCRAPER_ENABLED": Config.SCRAPER_ENABLED,
        "SCRAPER_DELAY": Config.SCRAPER_DELAY,
        "AI_AVAILABLE": Config.ai_available(),
        "USER": user["username"],
        "USER_ID": user["id"]
    })

    st.markdown("---")
    st.subheader("Data Management")
    st.markdown("Reset or clear your data. These actions are **irreversible**.")

    reset_cols = st.columns(6)
    with reset_cols[0]:
        if st.button("Clear Courses", key="reset_courses"):
            db.execute("DELETE FROM courses")
            st.success("All courses deleted.")
            st.rerun()
    with reset_cols[1]:
        if st.button("Clear Skills", key="reset_skills"):
            db.execute("DELETE FROM skills")
            st.success("All skills deleted.")
            st.rerun()
    with reset_cols[2]:
        if st.button("Clear Certificates", key="reset_certs"):
            db.execute("DELETE FROM certificates")
            st.success("All certificates deleted.")
            st.rerun()
    with reset_cols[3]:
        if st.button("Clear Jobs", key="reset_jobs"):
            db.execute("DELETE FROM jobs")
            db.execute("DELETE FROM documents")
            st.success("All jobs and documents deleted.")
            st.rerun()
    with reset_cols[4]:
        if st.button("Clear Transfer Credits", key="reset_transfer"):
            db.execute("DELETE FROM transfer_credits")
            st.success("Transfer credits deleted.")
            st.rerun()
    with reset_cols[5]:
        if st.button("Reset ALL Data", type="primary", key="reset_all"):
            st.session_state.confirm_reset_all = True
            st.rerun()

    if st.session_state.get("confirm_reset_all", False):
        st.warning("Are you sure? This will delete ALL courses, skills, certificates, jobs, and documents!")
        confirm_cols = st.columns(2)
        with confirm_cols[0]:
            if st.button("Yes, Delete Everything", key="confirm_reset_yes"):
                db.execute("DELETE FROM courses")
                db.execute("DELETE FROM skills")
                db.execute("DELETE FROM certificates")
                db.execute("DELETE FROM jobs")
                db.execute("DELETE FROM documents")
                db.execute("DELETE FROM transfer_credits")
                # Clear uploads and generated dirs
                for d in [user_paths["uploads_dir"], user_paths["generated_dir"]]:
                    if os.path.exists(d):
                        for f in os.listdir(d):
                            fp = os.path.join(d, f)
                            if os.path.isfile(fp):
                                os.remove(fp)
                st.session_state.confirm_reset_all = False
                st.success("All data has been reset.")
                st.rerun()
        with confirm_cols[1]:
            if st.button("Cancel", key="confirm_reset_no"):
                st.session_state.confirm_reset_all = False
                st.rerun()

    st.markdown("---")
    st.subheader("Delete Account")
    st.markdown("**Warning:** This permanently deletes your account and all associated data. This cannot be undone.")

    if st.button("Delete My Account", type="primary", key="delete_account"):
        st.session_state.confirm_delete_account = True
        st.rerun()

    if st.session_state.get("confirm_delete_account", False):
        st.error("This will permanently delete your account and all data. Are you absolutely sure?")
        del_cols = st.columns(2)
        with del_cols[0]:
            if st.button("Yes, Delete My Account Forever", key="confirm_delete_yes"):
                from app.auth import delete_user
                success = delete_user(user["id"])
                if success:
                    st.session_state.user = None
                    st.session_state.confirm_delete_account = False
                    st.success("Account deleted. You have been logged out.")
                    st.rerun()
                else:
                    st.error("Failed to delete account. Please try again.")
        with del_cols[1]:
            if st.button("Cancel", key="confirm_delete_no"):
                st.session_state.confirm_delete_account = False
                st.rerun()

    st.markdown("---")
    st.markdown("### Data Location")
    st.code(user_paths["user_dir"], language="bash")

    st.markdown("### Edit .env")
    st.info("To change settings, edit the `.env` file and restart the container.")
    st.code("docker compose down && docker compose up --build -d", language="bash")
