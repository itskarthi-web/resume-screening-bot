# 🤖 AI Resume Screener

An AI-powered resume screening chatbot that helps recruiters analyze multiple candidates against job requirements through a Telegram interface.

The system accepts Job Descriptions and resumes in multiple formats, uses AI to understand their content, identifies skill matches and gaps, generates candidate insights, and ranks candidates based on their relevance to the job requirements.

---

## 🚀 Features

### 📋 Job Description Processing

The chatbot can accept Job Descriptions as:

* Text
* PDF
* DOCX
* JPG/JPEG
* PNG
* Photos

The system extracts the Job Description and uses Gemini AI to identify:

* Job title
* Required skills
* Preferred skills
* Experience requirements
* Education requirements
* Important responsibilities

---

### 📄 Resume Processing

The system accepts resumes as:

* PDF
* DOCX
* JPG/JPEG
* PNG
* Photos
* Scanned/image-based PDFs

For normal documents, text is extracted directly.

For scanned or image-based resumes, Gemini Vision is used to understand the resume content.

---

### 🧠 AI Resume Analysis

Each candidate is analyzed against the Job Description.

The system identifies:

* Candidate name
* Match score
* Matched skills
* Missing/weak skills
* Experience match
* Education match
* Project relevance
* Resume improvement suggestions
* Recommended learning resources

---

### 🏆 Candidate Ranking

After screening multiple resumes, candidates are ranked based on their match score.

Example:

```text
🏆 FINAL CANDIDATE RANKING

🥇 Candidate A — 89%
🥈 Candidate B — 82%
🥉 Candidate C — 76%
4. Candidate D — 68%
```

---

## 🔄 System Workflow

```text
                 HR
                  │
                  ▼
               /start
                  │
                  ▼
        ┌──────────────────┐
        │ Job Description   │
        └──────────────────┘
                  │
          Text / PDF / DOCX
          Image / Photo
                  │
                  ▼
             Gemini AI
                  │
                  ▼
       Structured JD Requirements
                  │
                  ▼
              DONE_JD
                  │
                  ▼
        ┌──────────────────┐
        │     Resumes      │
        └──────────────────┘
                  │
       PDF / DOCX / Images
                  │
                  ▼
          Text Extraction /
            Gemini Vision
                  │
                  ▼
                DONE
                  │
                  ▼
        ┌──────────────────┐
        │ Candidate Match  │
        └──────────────────┘
                  │
                  ▼
             Gemini AI
                  │
                  ▼
       ┌─────────────────────┐
       │ Skill Matching      │
       │ Experience Matching │
       │ Education Matching  │
       │ Project Matching    │
       └─────────────────────┘
                  │
                  ▼
            Match Score
                  │
                  ▼
        Candidate Reports
                  │
                  ▼
          Final Ranking
```

---

## 🧩 Project Architecture

```text
resume-screening-bot/
│
├── bot.py
├── ai_analyzer.py
├── test_gemini.py
├── requirements.txt
├── .env
├── .gitignore
├── README.md
│
├── resumes/
│
└── venv/
```

### `bot.py`

Handles the Telegram chatbot workflow.

Responsibilities include:

* `/start`
* Job Description collection
* Resume collection
* File uploads
* Photo uploads
* Screening workflow
* Candidate reports
* Candidate ranking

### `ai_analyzer.py`

Contains the AI and document-processing logic.

Responsibilities include:

* Job Description analysis
* Resume analysis
* PDF text extraction
* DOCX text extraction
* Image/scanned document processing
* Gemini API communication
* Skill matching
* Candidate evaluation
* Course recommendations

### `test_gemini.py`

Used to verify that the Gemini API connection is working correctly.

---

## 🛠️ Technologies Used

* Python
* Telegram Bot API
* Python Telegram Bot
* Google Gemini API
* Gemini Vision
* PyPDF
* python-docx
* python-dotenv

---

## 📦 Installation

### 1. Clone the repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
cd resume-screening-bot
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

### 3. Activate the virtual environment

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

---

## 🔐 Environment Variables

Create a `.env` file:

```env
BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
GEMINI_MODEL=YOUR_GEMINI_MODEL
GEMINI_FALLBACK_MODEL=YOUR_FALLBACK_MODEL
```

**Never upload your `.env` file to GitHub.**

---

## ▶️ Running the Bot

Activate the virtual environment:

```powershell
.\venv\Scripts\Activate.ps1
```

Then run:

```powershell
python bot.py
```

You should see:

```text
🤖 AI Resume Screener is running...
```

Open the Telegram bot and send:

```text
/start
```

---

## 💬 Example Usage

### Step 1 — Send Job Description

The recruiter can send:

```text
Software Developer

Required:
Python
FastAPI
SQL
PostgreSQL
REST APIs

Preferred:
Docker
AWS
```

Or upload the JD as a PDF, DOCX, or image.

---

### Step 2 — Finish JD Collection

```text
DONE_JD
```

The system then processes the Job Description and prepares the requirements.

---

### Step 3 — Upload Resumes

Upload multiple candidates:

```text
Resume 1
Resume 2
Resume 3
Resume 4
Resume 5
```

---

### Step 4 — Start Screening

Send:

```text
DONE
```

The system analyzes the candidates.

---

## 📊 Candidate Evaluation

A candidate report can contain:

```text
👤 CANDIDATE #1

🎯 MATCH SCORE: 84%

✅ MATCHED SKILLS

• Python
• SQL
• PostgreSQL
• REST APIs

❌ MISSING / WEAK SKILLS

• FastAPI
• Docker

📊 EXPERIENCE MATCH

Candidate experience shows relevant software development
and Python-based project exposure.

🎓 EDUCATION MATCH

Education is aligned with the technical requirements.

🛠️ PROJECT MATCH

Projects demonstrate relevant backend and programming
experience.

💡 RESUME SUGGESTION

Develop practical FastAPI and Docker projects to strengthen
alignment with the target role.

📚 RECOMMENDED COURSES

• FastAPI
• Docker
```

---

## 🎯 Why This Project?

Traditional resume screening can require recruiters to manually:

1. Read each Job Description
2. Read every resume
3. Compare skills
4. Identify missing requirements
5. Evaluate experience
6. Rank candidates

This project automates much of that initial screening process through an AI-powered conversational interface.

---

## ⭐ Key Highlights

* 🤖 AI-powered resume screening
* 💬 Telegram-based recruiter interface
* 📄 Multiple document formats
* 🖼️ Image and scanned resume support
* 📋 Structured Job Description analysis
* 🔎 Skill gap identification
* 📊 Candidate scoring
* 🏆 Candidate ranking
* 📚 Learning recommendations
* 📦 Multiple resume processing
* 🔐 Environment-variable based API configuration

---

## ⚠️ Important Note

This system is designed as an AI-assisted screening tool.

AI-generated candidate evaluations should be reviewed by a qualified recruiter before making hiring decisions.

The system should support recruiters rather than replace human judgment.

---

## 🔮 Future Improvements

* Multi-JD and multi-candidate comparison dashboard
* Persistent database storage
* Recruiter web dashboard
* Advanced deterministic scoring engine
* OCR fallback for difficult scanned documents
* Candidate comparison charts
* Export reports to PDF/Excel
* Authentication and recruiter accounts
* Resume database
* Interview question generation
* Email integration

---

## 👨‍💻 Project

**AI Resume Screener**

Built using Python, Telegram Bot API, and Google Gemini AI.
