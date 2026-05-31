# Job Matcher

An AI-powered job matching and application assistant for Computer Science graduates. Upload your university transcript, add job postings, and let AI generate tailored resumes, cover letters, and interview Q&A.

## Features

- **Transcript Parsing**: Extracts courses, grades, and skills from your PDF transcript using AI (Google Gemini or OpenAI)
- **Syllabus Enhancement**: Optionally upload course syllabi for deeper skill extraction
- **Job Matching**: AI analyzes job descriptions against your skills and gives a match score
- **Document Generation**: One-click generation of tailored PDF resumes, cover letters, and Q&A answers
- **Stealth Scraper**: Optional ultra-slow Indeed scraper with Playwright stealth mode (toggleable)
- **Daily Scheduling**: Background scheduler for automated daily job scans

## Quick Start (Local / Omarchy)

1. Clone or copy this project to your machine
2. Edit `.env` and set your `GEMINI_API_KEY`
3. Run:
   ```bash
   docker compose up --build -d
   ```
4. Open http://localhost:8501 in your browser

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Google Gemini API key | (required) |
| `OPENAI_API_KEY` | OpenAI API key (fallback) | (empty) |
| `SCHEDULE_ENABLED` | Enable daily background scans | `false` |
| `SCHEDULE_TIME` | Daily scan time (24h format) | `09:00` |
| `SCRAPER_ENABLED` | Enable stealth Indeed scraper | `false` |
| `SCRAPER_DELAY` | Seconds between scraper requests | `20` |

## Usage

1. **Upload Transcript**: Go to "Upload Transcript" and upload your university transcript PDF. Click "Extract Courses & Skills"
2. **Add Jobs**: Go to "Jobs" and paste job URLs or descriptions manually. You can also run the stealth scraper if enabled.
3. **Analyze Fit**: Click "Analyze Fit" on any job to get an AI-powered match score.
4. **Generate Documents**: Go to "Generate Documents", select a job, and generate Resume, Cover Letter, or Q&A.

## Stealth Scraper Warning

The Indeed scraper is intentionally **extremely slow** (1 request every 15-30 seconds) to avoid detection and bans. It is disabled by default. Enable at your own risk.

**LinkedIn**: The app does NOT auto-scrape LinkedIn. You must manually paste LinkedIn job URLs or descriptions. Auto-scraping LinkedIn will result in an immediate account ban.

## Unraid Deployment

1. Copy the project folder to your Unraid server
2. Install the **Docker Compose Manager** plugin (or use the CA plugin)
3. Set up a new stack with the provided `docker-compose.yml`
4. Set environment variables in the Unraid container config
5. Map a persistent volume for `./data` to keep your database and generated documents

### Unraid Template (Community Applications)

If you want to add this to Community Applications, create an XML template:

```xml
<?xml version="1.0"?>
<Container version="2">
  <Name>job-matcher</Name>
  <Repository>job-matcher:latest</Repository>
  <Registry/>
  <Network>bridge</Network>
  <Shell>sh</Shell>
  <Privileged>false</Privileged>
  <Support/>
  <Project/>
  <Overview>AI-powered job matching and application assistant</Overview>
  <Category>Productivity:</Category>
  <WebUI>http://[IP]:[PORT:8501]/</WebUI>
  <TemplateURL/>
  <Icon/>
  <ExtraParams/>
  <PostArgs/>
  <CPUset/>
  <DateInstalled/>
  <DonateText/>
  <DonateLink/>
  <Requires/>
  <Config Name="Web UI" Target="8501" Default="8501" Mode="tcp" Description="Streamlit port" Type="Port" Display="always" Required="true" Mask="false">8501</Config>
  <Config Name="Data" Target="/app/data" Default="" Mode="rw" Description="Persistent data volume" Type="Path" Display="always" Required="true" Mask="false">/mnt/user/appdata/job-matcher/data</Config>
  <Config Name="GEMINI_API_KEY" Target="GEMINI_API_KEY" Default="" Mode="" Description="Google Gemini API Key" Type="Variable" Display="always" Required="true" Mask="true"></Config>
  <Config Name="SCRAPER_ENABLED" Target="SCRAPER_ENABLED" Default="false" Mode="" Description="Enable stealth scraper" Type="Variable" Display="always" Required="false" Mask="false">false</Config>
  <Config Name="SCHEDULE_ENABLED" Target="SCHEDULE_ENABLED" Default="false" Mode="" Description="Enable daily scheduler" Type="Variable" Display="always" Required="false" Mask="false">false</Config>
</Container>
```

## Tech Stack

- **UI**: Streamlit (Python)
- **PDF Parsing**: PyMuPDF
- **AI**: Google Gemini (primary), OpenAI (fallback)
- **Scraper**: Playwright with stealth mode
- **PDF Generation**: WeasyPrint (HTML to PDF)
- **Database**: SQLite
- **Scheduler**: APScheduler
- **Deployment**: Docker + Docker Compose

## File Structure

```
job-matcher/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env
├── app/
│   ├── main.py
│   ├── config.py
│   ├── db/
│   ├── parsers/
│   ├── ai/
│   ├── scraper/
│   ├── scheduler/
│   └── templates/
└── data/
```
