import streamlit as st
import os
import json
from app.config import Config
from app.db.database import Database
from app.parsers.transcript import parse_transcript
from app.parsers.syllabus import parse_syllabus
from app.ai.extractor import TranscriptExtractor
from app.auth import login_user, register_user, get_user_paths, get_profile, update_profile
from app.db.education import save_extracted_transcript, get_courses_grouped

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
    ["Dashboard", "Profile", "Upload Transcript", "Skills & Certificates", "Discover Jobs", "Jobs", "Generate Documents", "Settings"]
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

elif page == "Upload Transcript":
    st.title("Upload Transcript")
    st.markdown("Upload your academic transcript (and optionally syllabi) to extract your skills using AI. Courses will be organized by institution and degree.")

    transcript_file = st.file_uploader("Upload Transcript PDF", type=["pdf"])
    syllabus_files = st.file_uploader("Upload Syllabus PDFs (Optional)", type=["pdf"], accept_multiple_files=True)

    if transcript_file:
        save_path = os.path.join(user_paths["uploads_dir"], transcript_file.name)
        with open(save_path, "wb") as f:
            f.write(transcript_file.getbuffer())
        st.success(f"Saved {transcript_file.name}")

        if st.button("Extract Courses & Skills"):
            if not Config.ai_available():
                st.error("AI not configured. Add GEMINI_API_KEY to .env")
            else:
                with st.spinner("Parsing transcript with AI..."):
                    try:
                        result = parse_transcript(save_path)
                        extracted = extractor.extract_courses(result["raw_text"])

                        # Save institutions, degrees, courses, and transfer credits
                        save_extracted_transcript(user["id"], extracted, db)

                        courses = extracted.get("courses", [])

                        # Parse syllabi if any
                        syllabi_texts = []
                        if syllabus_files:
                            for syl in syllabus_files:
                                syl_path = os.path.join(user_paths["uploads_dir"], syl.name)
                                with open(syl_path, "wb") as f:
                                    f.write(syl.getbuffer())
                                syl_data = parse_syllabus(syl_path)
                                syllabi_texts.append(syl_data["raw_text"])
                            if syllabi_texts:
                                courses = extractor.enhance_with_syllabi(courses, syllabi_texts)
                                # Update descriptions in DB for enhanced courses
                                for c in courses:
                                    db.execute(
                                        "UPDATE courses SET description = ? WHERE user_id = ? AND code = ? AND name = ? AND term = ?",
                                        (c.get("description"), user["id"], c.get("code"), c.get("name"), c.get("term"))
                                    )

                        # Extract skills
                        skills = extractor.extract_skills(courses)
                        for s in skills:
                            try:
                                db.execute(
                                    "INSERT OR IGNORE INTO skills (user_id, name, category, proficiency, source) VALUES (?, ?, ?, ?, ?)",
                                    (user["id"], s.get("name"), s.get("category"), s.get("proficiency"), s.get("source"))
                                )
                            except Exception:
                                pass

                        st.success(f"Extracted {len(courses)} courses and {len(skills)} skills!")
                        st.session_state.last_extracted = extracted
                        st.rerun()
                    except Exception as e:
                        st.error(f"Extraction failed: {e}")

    # Show extraction results if available
    if st.session_state.get("last_extracted"):
        extracted = st.session_state.last_extracted
        st.markdown("---")
        st.subheader("Extracted Institutions & Degrees")
        for inst in extracted.get("institutions", []):
            st.write(f"**{inst.get('name')}** — {inst.get('institution_type')} ({inst.get('location') or 'no location'})")
        for deg in extracted.get("degrees", []):
            st.write(f"- {deg.get('degree_name')} ({deg.get('degree_type')}) at {deg.get('institution_name')}")

    # Show existing courses grouped by institution and degree
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
                            st.write(f"- **{c['code']}** — {c['name']} (Grade: {c['grade']}, Credits: {c['credits']}, Term: {c.get('term', 'N/A')})")
                    else:
                        st.caption("No courses assigned to this degree yet.")

                if inst.get("unassigned_courses"):
                    st.markdown("#### 📄 Unassigned Courses")
                    for c in inst["unassigned_courses"]:
                        st.write(f"- **{c['code']}** — {c['name']} (Grade: {c['grade']}, Credits: {c['credits']}, Term: {c.get('term', 'N/A')})")

    # Show transfer credits
    transfers = db.fetchall("SELECT * FROM transfer_credits WHERE user_id = ? ORDER BY id DESC", (user["id"],))
    if transfers:
        st.markdown("---")
        st.subheader("Transfer Credits")
        for t in transfers:
            st.write(f"**Institution:** {t.get('institution', 'N/A')}")
            st.write(f"Attempted: {t.get('attempted', 'N/A')} | Earned: {t.get('earned', 'N/A')} | GPA Units: {t.get('gpa_units', 'N/A')}")
            st.write(f"Transfer GPA: {t.get('transfer_gpa', 'N/A')}")
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

        if not courses:
            st.error("Upload your transcript first to generate documents.")
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
                                data, filepath, html = gen.generate_resume(courses, skills, certificates, job, profile)
                                # Ensure generated file goes to user's directory
                                filename = os.path.basename(filepath)
                                user_filepath = os.path.join(user_paths["generated_dir"], filename)
                                if filepath != user_filepath and os.path.exists(filepath):
                                    import shutil
                                    shutil.move(filepath, user_filepath)
                                    filepath = user_filepath
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
                                data, filepath, html = gen.generate_cover_letter(courses, skills, certificates, job, profile)
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
                                qna = gen.generate_qna(courses, skills, certificates, job, profile)
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
