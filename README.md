# ResumeIQ — AI Resume Ranking Platform

A two-role platform where HR teams post jobs and get AI-ranked applicants,
and candidates browse jobs, apply, and get resume feedback — all powered by
sentence-embedding based semantic matching.

## Features

**HR side**
- Sign up / log in as an HR user
- Post job openings, and close/reopen them once filled
- View applicants per job, automatically ranked by match score
- See matched/missing skills per applicant for explainability
- Add private notes per applicant (e.g. interview impressions)
- Shortlist or reject applicants (candidates see the status update)
- Export the ranked applicant list as a CSV file
- Analytics dashboard: score distribution + most common missing skills across all applicants

**Candidate side**
- Sign up / log in as a candidate
- Upload a resume once (PDF/DOCX/TXT)
- Browse all open jobs with an instant match % against your resume
- Apply to jobs with one click
- Track application status (In review / Shortlisted / Rejected)
- Get personalized feedback: which in-demand skills are missing from your resume,
  each paired with curated free YouTube videos and documentation to learn them
- **Career Assistant chatbot**: paste any job description and ask what skills it
  requires, or have an open conversation about your resume and job search —
  powered by Google's free Gemini API

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python) |
| Auth | JWT (PyJWT) + bcrypt password hashing (passlib) |
| NLP / Matching | sentence-transformers (all-MiniLM-L6-v2) + cosine similarity |
| Resume parsing | pdfplumber, python-docx |
| Database | SQLite |
| Frontend | HTML/CSS/vanilla JS (no build step) |
| Charts | Chart.js |
| Deployment | Render |

## Project structure

```
resume-ranker-v2/
├── backend/
│   ├── main.py         # FastAPI app + all API routes
│   ├── auth.py          # password hashing + JWT
│   ├── database.py      # SQLite schema + queries
│   ├── parser.py         # resume text extraction
│   ├── ranker.py          # embeddings + scoring
│   ├── resources.py        # curated free learning resources per skill
│   ├── chatbot.py           # Gemini API integration for the career assistant
│   ├── .env.example          # template for your GEMINI_API_KEY
│   └── requirements.txt
├── frontend/
│   └── index.html         # full single-page app (auth + both dashboards)
├── uploads/                 # temp storage during resume processing
├── requirements.txt          # root copy for Render's build
├── render.yaml
└── README.md
```

## Setting up the Career Assistant chatbot (Gemini API)

The chatbot needs a free Gemini API key:

1. Get one from [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) (free, no credit card — see setup guide if needed)
2. In the `backend/` folder, copy `.env.example` to a new file named `.env`
3. Open `.env` and replace `your_gemini_api_key_here` with your real key
4. Save — the server reads it automatically on startup (via python-dotenv)

**Never commit your `.env` file** — it's already in `.gitignore` so it won't
accidentally get pushed to GitHub. If you skip this setup, every other
feature still works fine — only the Career Assistant chat will show an error.

## Running locally

```bash
cd resume-ranker-v2
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

cd backend
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000`. You'll land on the login screen.

**To test the full flow:**
1. Click "Create an account" → choose "I'm hiring (HR)" → sign up
2. Post a job (e.g. title "Backend Engineer", description mentioning Python/FastAPI/SQL)
3. Log out, sign up again as "I'm job hunting" (candidate) — use a different email
4. Upload a resume (any PDF/DOCX/TXT with some skills mentioned)
5. Go to "Browse Jobs" → you'll see your match % → click "Apply now"
6. Log back in as the HR account → "Job Postings" → "View applicants" → see the ranked applicant, shortlist them
7. Log back in as the candidate → "My Applications" → see the status changed to "Shortlisted"

> First request will be slow (~20-30s) while the embedding model loads. After that it's fast.

## Deploying to Render

1. Push this project to a GitHub repo (see commands below)
2. Go to [render.com](https://render.com) → New + → Web Service → connect your repo
3. Render auto-detects `render.yaml`. If not, set manually:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
4. **Add your Gemini API key**: in Render, go to your service → Environment →
   add an environment variable named `GEMINI_API_KEY` with your key as the value.
   (Don't put it in `render.yaml` or any committed file — the dashboard is the
   safe place for secrets.)
5. Click "Create Web Service" and wait for the build
6. Your live URL (e.g. `https://resumeiq.onrender.com`) is your submission link

> Free tier note: the service sleeps after 15 minutes of inactivity and takes
> ~30-60 seconds to wake up on the next request — open the link a minute
> before your demo.

## Pushing to GitHub

```bash
cd resume-ranker-v2
git init
git add .
git commit -m "ResumeIQ: full two-role platform with auth, ranking, and analytics"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

## Notes for your report / viva

- The `SECRET_KEY` in `auth.py` is hardcoded for demo simplicity — mention
  that in production it would live in an environment variable
- The ranking core (embeddings + cosine similarity) is unchanged from the
  single-user version — it's just now called once per application instead
  of once per batch upload, and results are persisted per job/candidate pair
- SQLite is used for simplicity; a production version would use PostgreSQL
