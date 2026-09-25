import os
import json
import time
from urllib.parse import quote_plus

from dotenv import load_dotenv
from google import genai
from google.genai import types


# =========================================================
# ENVIRONMENT
# =========================================================

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

PRIMARY_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.5-flash-lite"
)

FALLBACK_MODEL = os.getenv(
    "GEMINI_FALLBACK_MODEL",
    "gemini-3.8-flash"
)

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is missing from .env")


# =========================================================
# GEMINI CLIENT
# =========================================================

client = genai.Client(api_key=GEMINI_API_KEY)


# =========================================================
# CONSTANTS
# =========================================================

MAX_TEXT_CHARS = 30000

BASE_WEIGHTS = {
    "required_skills": 55.0,
    "preferred_skills": 10.0,
    "experience": 20.0,
    "projects": 10.0,
    "education": 5.0,
}

STATUS_VALUE = {
    "strong": 1.0,
    "matched": 1.0,
    "partial": 0.5,
    "weak": 0.5,
    "unclear": 0.25,
    "missing": 0.0,
    "not_found": 0.0,
}


# =========================================================
# JSON CLEANING
# =========================================================

def clean_json(text):
    if not text:
        raise ValueError("Gemini returned an empty response.")

    text = text.strip()

    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]

    if text.endswith("```"):
        text = text[:-3]

    return text.strip()


# =========================================================
# JSON PARSING
# =========================================================

def parse_json(text):
    cleaned = clean_json(text)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try to recover the first JSON object.
    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start != -1 and end != -1 and end > start:
        candidate = cleaned[start:end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    raise ValueError("Gemini returned invalid JSON.")


# =========================================================
# GEMINI REQUEST WITH RETRY + FALLBACK
# =========================================================

def generate_response(contents, json_mode=False):
    models = []

    for model_name in [PRIMARY_MODEL, FALLBACK_MODEL]:
        if model_name and model_name not in models:
            models.append(model_name)

    delays = [3, 6, 12]
    last_error = None

    for model_name in models:
        for attempt in range(3):
            try:
                print(f"🧠 Gemini model: {model_name}")
                print(f"🧠 Attempt {attempt + 1}/3")

                config_kwargs = {
                    "temperature": 0.0
                }

                if json_mode:
                    config_kwargs["response_mime_type"] = "application/json"

                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        **config_kwargs
                    )
                )

                if not response.text:
                    raise ValueError("Gemini returned empty text.")

                return response

            except Exception as e:
                last_error = e
                error_text = str(e)

                print(f"⚠️ Gemini error: {error_text}")

                temporary = any(
                    marker in error_text
                    for marker in [
                        "503",
                        "UNAVAILABLE",
                        "429",
                        "RESOURCE_EXHAUSTED",
                        "500",
                        "INTERNAL",
                        "504",
                        "DEADLINE_EXCEEDED",
                    ]
                )

                if not temporary:
                    raise

                if attempt < 2:
                    delay = delays[attempt]
                    print(f"🔄 Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    print("➡️ Trying next model if available...")

    if last_error:
        raise last_error

    raise RuntimeError("No Gemini model is configured.")


# =========================================================
# SMALL HELPERS
# =========================================================

def as_clean_string(value, default=""):
    if value is None:
        return default
    return str(value).strip()


def as_string_list(value):
    if not isinstance(value, list):
        return []

    output = []

    for item in value:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = as_clean_string(item.get("skill") or item.get("name"))
        else:
            text = str(item).strip()

        if text:
            output.append(text)

    return list(dict.fromkeys(output))


def clamp(value, low=0.0, high=100.0):
    return max(low, min(high, float(value)))


def status_score(status):
    return STATUS_VALUE.get(
        as_clean_string(status).lower(),
        0.25
    ) * 100.0


def normalize_years(value):
    try:
        if value is None or value == "":
            return None
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None


def unique_preserve_order(items):
    seen = set()
    result = []

    for item in items:
        key = str(item).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(str(item).strip())

    return result


# =========================================================
# JOB DESCRIPTION NORMALIZATION
# =========================================================

def normalize_jd_analysis(result):
    if not isinstance(result, dict):
        raise ValueError("JD analysis must be a JSON object.")

    result["job_title"] = as_clean_string(
        result.get("job_title"),
        "Unknown Role"
    )

    result["required_skills"] = as_string_list(
        result.get("required_skills")
    )

    result["preferred_skills"] = as_string_list(
        result.get("preferred_skills")
    )

    experience = result.get("experience_requirements", [])

    if not isinstance(experience, list):
        experience = [experience] if experience else []

    cleaned_experience = []

    for item in experience:
        if isinstance(item, dict):
            minimum_years = normalize_years(
                item.get("minimum_years")
            )
            details = as_clean_string(
                item.get("details")
            )

            cleaned_experience.append({
                "minimum_years": minimum_years,
                "details": details
            })
        else:
            cleaned_experience.append({
                "minimum_years": None,
                "details": as_clean_string(item)
            })

    result["experience_requirements"] = cleaned_experience

    result["education_requirements"] = as_string_list(
        result.get("education_requirements")
    )

    result["important_responsibilities"] = as_string_list(
        result.get("important_responsibilities")
    )

    return result


# =========================================================
# JOB DESCRIPTION ANALYZER
# =========================================================

def analyze_job_description(job_description):
    if not job_description or not job_description.strip():
        raise ValueError("Job Description is empty.")

    job_description = job_description.strip()[:MAX_TEXT_CHARS]

    prompt = f"""
You are a senior technical recruiter and job-requirement extraction specialist.

Read the Job Description carefully and extract ONLY requirements that are
actually supported by the text.

JOB DESCRIPTION
===============
{job_description}

IMPORTANT RULES
===============
1. Do not invent technologies, qualifications, years of experience, or duties.
2. Preserve the meaning of the JD.
3. Put genuinely mandatory/core skills in required_skills.
4. Put nice-to-have/preferred skills in preferred_skills.
5. If the JD does not explicitly state an experience minimum, use null for
   minimum_years rather than guessing.
6. Education requirements must come from the JD. Do not add a degree merely
   because it is common for the role.
7. Use concise canonical skill names such as Python, FastAPI, PostgreSQL,
   React, Docker, AWS, SQL, Java.
8. Do not treat a responsibility as a skill unless the JD clearly presents it
   as a technology, competency, tool, framework, language, platform, or method.
9. Return JSON only.

OUTPUT JSON
===========
{{
  "job_title": "",
  "required_skills": [],
  "preferred_skills": [],
  "experience_requirements": [
    {{
      "minimum_years": null,
      "details": ""
    }}
  ],
  "education_requirements": [],
  "important_responsibilities": []
}}
"""

    response = generate_response(
        contents=prompt,
        json_mode=True
    )

    return normalize_jd_analysis(
        parse_json(response.text)
    )


# =========================================================
# RESUME EVIDENCE PROMPT
# =========================================================

def build_resume_evaluation_prompt(jd_analysis):
    jd_json = json.dumps(
        jd_analysis,
        ensure_ascii=False,
        indent=2
    )

    return f"""
You are a senior technical recruiter performing evidence-based resume screening.

You must compare ONE candidate against ONE Job Description.

STRUCTURED JOB REQUIREMENTS
===========================
{jd_json}

CORE PRINCIPLE
==============
Only give credit when the resume contains evidence.
Do not invent experience, education, projects, certifications, tools, or years.
Do not give credit just because two terms look vaguely related.
Equivalent wording is allowed only when it truly means the same skill.

SKILL MATCHING RULE
===================
For EVERY required skill AND EVERY preferred skill, return exactly one
skill_assessment entry using the same skill name from the JD.

status must be one of:
- strong: clearly demonstrated with meaningful evidence
- partial: some evidence, but depth or context is limited
- unclear: the resume may mention something related but proof is insufficient
- missing: no credible evidence found

Do NOT count a skill as strong merely because it appears once in a keyword list.
A project, work experience, internship, certification, or detailed skill section
can be evidence when appropriate.

EXPERIENCE RULE
===============
Compare actual candidate experience to explicit JD experience requirements.
Extract only years that the resume itself supports.
If years are not stated clearly, years_found must be null.

EDUCATION RULE
==============
Compare the actual degree/field/education in the resume with only what the JD
requires. Do not assume a degree is required when the JD does not say so.

PROJECT RULE
============
Judge project relevance using the actual project descriptions, technologies,
and responsibilities in the resume.

SUGGESTION RULE
===============
Write exactly 2-3 sentences, highly specific to this candidate and this JD.
Mention the most important missing/weak requirement(s) or the strongest JD-
relevant improvement. Never write generic advice such as "improve your resume".

COURSE RULE
===========
Recommend 2-4 course names ONLY for important missing/weak skills.
Do not recommend courses for skills that are already strong.
Course names must be real-sounding and specific to the skill.
Do not create URLs. The application will create search links.

OUTPUT JSON ONLY
================
{{
  "candidate_name": "",
  "skill_assessment": [
    {{
      "skill": "",
      "category": "required",
      "status": "strong",
      "evidence": ""
    }}
  ],
  "experience_assessment": {{
    "status": "strong",
    "years_found": null,
    "years_required": null,
    "evidence": ""
  }},
  "education_assessment": {{
    "status": "strong",
    "evidence": ""
  }},
  "project_assessment": {{
    "status": "strong",
    "evidence": ""
  }},
  "suggestion": "",
  "recommended_courses": [
    {{
      "skill": "",
      "course": ""
    }}
  ]
}}
"""


# =========================================================
# RESUME EVIDENCE NORMALIZATION
# =========================================================

def normalize_evidence_result(result, jd_analysis):
    if not isinstance(result, dict):
        raise ValueError("Resume analysis must be a JSON object.")

    candidate_name = as_clean_string(
        result.get("candidate_name"),
        "Unknown"
    )

    # -----------------------------------------------------
    # Build required/preferred skill lists from JD
    # -----------------------------------------------------

    required_skills = jd_analysis.get(
        "required_skills",
        []
    )

    preferred_skills = jd_analysis.get(
        "preferred_skills",
        []
    )

    expected = []

    for skill in required_skills:
        expected.append((skill, "required"))

    for skill in preferred_skills:
        expected.append((skill, "preferred"))

    raw_skill_assessment = result.get(
        "skill_assessment",
        []
    )

    if not isinstance(raw_skill_assessment, list):
        raw_skill_assessment = []

    # Match model output back to expected JD skills.
    by_skill = {}

    for item in raw_skill_assessment:
        if not isinstance(item, dict):
            continue

        skill = as_clean_string(item.get("skill"))

        if not skill:
            continue

        by_skill[skill.lower()] = item

    skill_assessment = []

    for skill, category in expected:
        item = by_skill.get(skill.lower(), {})

        status = as_clean_string(
            item.get("status"),
            "unclear"
        ).lower()

        if status not in STATUS_VALUE:
            status = "unclear"

        evidence = as_clean_string(
            item.get("evidence")
        )

        skill_assessment.append({
            "skill": skill,
            "category": category,
            "status": status,
            "evidence": evidence
        })

    # -----------------------------------------------------
    # Experience
    # -----------------------------------------------------

    experience = result.get(
        "experience_assessment",
        {}
    )

    if not isinstance(experience, dict):
        experience = {}

    exp_status = as_clean_string(
        experience.get("status"),
        "unclear"
    ).lower()

    if exp_status not in STATUS_VALUE:
        exp_status = "unclear"

    years_found = normalize_years(
        experience.get("years_found")
    )

    years_required = normalize_years(
        experience.get("years_required")
    )

    # Prefer explicit minimum from our own JD extraction.
    jd_required_years = []

    for item in jd_analysis.get(
        "experience_requirements",
        []
    ):
        if isinstance(item, dict):
            years = normalize_years(
                item.get("minimum_years")
            )
            if years is not None:
                jd_required_years.append(years)

    if jd_required_years:
        years_required = max(jd_required_years)

    # -----------------------------------------------------
    # Education
    # -----------------------------------------------------

    education = result.get(
        "education_assessment",
        {}
    )

    if not isinstance(education, dict):
        education = {}

    education_status = as_clean_string(
        education.get("status"),
        "unclear"
    ).lower()

    if education_status not in STATUS_VALUE:
        education_status = "unclear"

    # -----------------------------------------------------
    # Projects
    # -----------------------------------------------------

    project = result.get(
        "project_assessment",
        {}
    )

    if not isinstance(project, dict):
        project = {}

    project_status = as_clean_string(
        project.get("status"),
        "unclear"
    ).lower()

    if project_status not in STATUS_VALUE:
        project_status = "unclear"

    # -----------------------------------------------------
    # Courses
    # -----------------------------------------------------

    courses = result.get(
        "recommended_courses",
        []
    )

    if not isinstance(courses, list):
        courses = []

    cleaned_courses = []

    for course in courses:
        if not isinstance(course, dict):
            continue

        skill = as_clean_string(
            course.get("skill")
        )

        course_name = as_clean_string(
            course.get("course")
        )

        if skill and course_name:
            cleaned_courses.append({
                "skill": skill,
                "course": course_name
            })

    # -----------------------------------------------------
    # Suggestion
    # -----------------------------------------------------

    suggestion = as_clean_string(
        result.get("suggestion")
    )

    # -----------------------------------------------------
    # Matched / missing skills from deterministic statuses
    # -----------------------------------------------------

    matched_skills = [
        item["skill"]
        for item in skill_assessment
        if item["status"] in ("strong", "matched")
    ]

    missing_skills = [
        item["skill"]
        for item in skill_assessment
        if item["status"] in ("missing", "unclear", "partial", "weak")
    ]

    return {
        "candidate_name": candidate_name,
        "skill_assessment": skill_assessment,
        "experience_assessment": {
            "status": exp_status,
            "years_found": years_found,
            "years_required": years_required,
            "evidence": as_clean_string(
                experience.get("evidence")
            )
        },
        "education_assessment": {
            "status": education_status,
            "evidence": as_clean_string(
                education.get("evidence")
            )
        },
        "project_assessment": {
            "status": project_status,
            "evidence": as_clean_string(
                project.get("evidence")
            )
        },
        "suggestion": suggestion,
        "recommended_courses": cleaned_courses[:4],
        "matched_skills": unique_preserve_order(matched_skills),
        "missing_skills": unique_preserve_order(missing_skills),
    }


# =========================================================
# EXPERIENCE SCORE
# =========================================================

def calculate_experience_score(experience_assessment):
    status = experience_assessment.get(
        "status",
        "unclear"
    )

    years_found = normalize_years(
        experience_assessment.get("years_found")
    )

    years_required = normalize_years(
        experience_assessment.get("years_required")
    )

    # Explicit JD year requirement.
    if years_required is not None and years_required > 0:
        if years_found is None:
            # Relevant work may exist, but exact years are not evidenced.
            return status_score(status)

        ratio = clamp(
            (years_found / years_required) * 100.0
        )

        # Do not allow a merely "partial" semantic judgment to become 100.
        if status in ("partial", "weak"):
            ratio = min(ratio, 75.0)
        elif status == "unclear":
            ratio = min(ratio, 50.0)

        return ratio

    # No explicit minimum in JD; use evidence quality.
    return status_score(status)


# =========================================================
# DETERMINISTIC MATCH SCORE
# =========================================================

def compute_match_score(jd_analysis, evidence):
    required_items = [
        item for item in evidence["skill_assessment"]
        if item["category"] == "required"
    ]

    preferred_items = [
        item for item in evidence["skill_assessment"]
        if item["category"] == "preferred"
    ]

    category_scores = {}
    applicable_weights = {}

    # -----------------------------------------------------
    # Required skills
    # -----------------------------------------------------

    if required_items:
        category_scores["required_skills"] = sum(
            STATUS_VALUE.get(item["status"], 0.25)
            for item in required_items
        ) / len(required_items) * 100.0

        applicable_weights["required_skills"] = BASE_WEIGHTS[
            "required_skills"
        ]

    # -----------------------------------------------------
    # Preferred skills
    # -----------------------------------------------------

    if preferred_items:
        category_scores["preferred_skills"] = sum(
            STATUS_VALUE.get(item["status"], 0.25)
            for item in preferred_items
        ) / len(preferred_items) * 100.0

        applicable_weights["preferred_skills"] = BASE_WEIGHTS[
            "preferred_skills"
        ]

    # -----------------------------------------------------
    # Experience
    # -----------------------------------------------------

    experience_requirements = jd_analysis.get(
        "experience_requirements",
        []
    )

    has_exp_requirement = bool(
        experience_requirements
        and any(
            as_clean_string(
                item.get("details") if isinstance(item, dict) else item
            )
            for item in experience_requirements
        )
    )

    if has_exp_requirement:
        category_scores["experience"] = calculate_experience_score(
            evidence["experience_assessment"]
        )
        applicable_weights["experience"] = BASE_WEIGHTS[
            "experience"
        ]

    # -----------------------------------------------------
    # Projects
    # -----------------------------------------------------

    category_scores["projects"] = status_score(
        evidence["project_assessment"].get("status", "unclear")
    )

    applicable_weights["projects"] = BASE_WEIGHTS[
        "projects"
    ]

    # -----------------------------------------------------
    # Education
    # -----------------------------------------------------

    education_requirements = jd_analysis.get(
        "education_requirements",
        []
    )

    if education_requirements:
        category_scores["education"] = status_score(
            evidence["education_assessment"].get("status", "unclear")
        )
        applicable_weights["education"] = BASE_WEIGHTS[
            "education"
        ]

    # -----------------------------------------------------
    # Redistribute weights when JD does not contain a category.
    # This prevents missing optional JD sections from unfairly
    # reducing the candidate's score.
    # -----------------------------------------------------

    total_applicable = sum(applicable_weights.values())

    if total_applicable <= 0:
        return 0

    total_score = sum(
        category_scores[name] * weight
        for name, weight in applicable_weights.items()
    ) / total_applicable

    # Round to one decimal for stable reporting, but keep integer
    # output because the Telegram bot displays a percentage.
    return int(round(clamp(total_score)))


# =========================================================
# BUILD FINAL RESULT
# =========================================================

def build_final_resume_result(jd_analysis, raw_result):
    evidence = normalize_evidence_result(
        raw_result,
        jd_analysis
    )

    score = compute_match_score(
        jd_analysis,
        evidence
    )

    return normalize_result({
        "candidate_name": evidence["candidate_name"],
        "match_score": score,
        "matched_skills": evidence["matched_skills"],
        "missing_skills": evidence["missing_skills"],
        "experience_match": format_experience_match(
            evidence["experience_assessment"]
        ),
        "education_match": format_evidence_text(
            evidence["education_assessment"],
            "Education"
        ),
        "projects_match": format_evidence_text(
            evidence["project_assessment"],
            "Projects"
        ),
        "suggestion": evidence["suggestion"],
        "recommended_courses": evidence["recommended_courses"],
    })


# =========================================================
# DISPLAY HELPERS
# =========================================================

def format_evidence_text(section, label):
    status = section.get("status", "unclear")
    evidence = as_clean_string(section.get("evidence"))

    status_text = status.replace("_", " ").title()

    if evidence:
        return f"{status_text}: {evidence}"

    return f"{status_text}: No additional evidence extracted."


def format_experience_match(experience):
    status = experience.get("status", "unclear")
    years_found = experience.get("years_found")
    years_required = experience.get("years_required")
    evidence = as_clean_string(experience.get("evidence"))

    parts = [
        status.replace("_", " ").title()
    ]

    if years_found is not None:
        parts.append(f"Candidate evidence: {years_found:g} year(s)")

    if years_required is not None:
        parts.append(f"JD requirement: {years_required:g} year(s)")

    if evidence:
        parts.append(evidence)

    return " — ".join(parts)


# =========================================================
# NORMALIZE FINAL RESULT FOR BOT
# =========================================================

def normalize_result(result):
    if not isinstance(result, dict):
        result = {}

    # Score
    try:
        score = int(round(float(result.get("match_score", 0))))
    except (TypeError, ValueError):
        score = 0

    result["match_score"] = int(
        max(0, min(100, score))
    )

    # Candidate
    result["candidate_name"] = as_clean_string(
        result.get("candidate_name"),
        "Unknown"
    )

    # Lists
    result["matched_skills"] = unique_preserve_order(
        as_string_list(result.get("matched_skills"))
    )

    result["missing_skills"] = unique_preserve_order(
        as_string_list(result.get("missing_skills"))
    )

    # Strings
    for field in [
        "experience_match",
        "education_match",
        "projects_match",
        "suggestion"
    ]:
        result[field] = as_clean_string(
            result.get(field)
        )

    # Courses
    courses = result.get(
        "recommended_courses",
        []
    )

    cleaned_courses = []

    if isinstance(courses, list):
        for course in courses:
            if not isinstance(course, dict):
                continue

            skill = as_clean_string(
                course.get("skill")
            )

            course_name = as_clean_string(
                course.get("course")
            )

            if skill and course_name:
                cleaned_courses.append({
                    "skill": skill,
                    "course": course_name
                })

    result["recommended_courses"] = cleaned_courses[:4]

    return result


# =========================================================
# RESUME TEXT ANALYSIS
# =========================================================

def analyze_resume(jd_analysis, resume_text):
    if not resume_text or not resume_text.strip():
        raise ValueError("Resume text is empty.")

    resume_text = resume_text.strip()[:MAX_TEXT_CHARS]

    prompt = build_resume_evaluation_prompt(
        jd_analysis
    )

    prompt += f"""

CANDIDATE RESUME
================
{resume_text}
"""

    response = generate_response(
        contents=prompt,
        json_mode=True
    )

    raw_result = parse_json(
        response.text
    )

    return build_final_resume_result(
        jd_analysis,
        raw_result
    )


# =========================================================
# VISUAL RESUME ANALYSIS
# =========================================================

def analyze_resume_image(jd_analysis, file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(file_path)

    print(f"📤 Uploading visual resume: {file_path}")

    uploaded_file = client.files.upload(
        file=file_path
    )

    print("✅ File uploaded to Gemini.")

    prompt = build_resume_evaluation_prompt(
        jd_analysis
    )

    prompt += """

CANDIDATE DOCUMENT
==================
The attached file is the candidate resume.
It may be a scanned PDF, image, photographed resume, JPG, JPEG, or PNG.
Read the visible content carefully before producing the JSON.
If a field is not readable or not present, mark it as unclear/missing rather
than inventing information.
"""

    response = generate_response(
        contents=[
            uploaded_file,
            prompt
        ],
        json_mode=True
    )

    raw_result = parse_json(
        response.text
    )

    return build_final_resume_result(
        jd_analysis,
        raw_result
    )


# =========================================================
# PDF TEXT EXTRACTION
# =========================================================

def extract_pdf_text(file_path):
    from pypdf import PdfReader

    reader = PdfReader(file_path)
    parts = []

    for page in reader.pages:
        text = page.extract_text()
        if text:
            parts.append(text)

    return "\n".join(parts).strip()


# =========================================================
# DOCX TEXT EXTRACTION
# =========================================================

def extract_docx_text(file_path):
    from docx import Document

    document = Document(file_path)
    parts = []

    for paragraph in document.paragraphs:
        if paragraph.text.strip():
            parts.append(paragraph.text)

    # Also read table cells because many resumes/JDs put content in tables.
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                text = cell.text.strip()
                if text:
                    parts.append(text)

    return "\n".join(parts).strip()


# =========================================================
# GEMINI FILE TO PLAIN TEXT
# =========================================================

def extract_visual_text(file_path, document_name="document"):
    if not os.path.exists(file_path):
        raise FileNotFoundError(file_path)

    uploaded_file = client.files.upload(
        file=file_path
    )

    prompt = f"""
Read the attached {document_name} carefully.

Extract ALL readable text in the correct logical order.
Do not summarize.
Do not omit headings, requirements, skills, experience, education, or
responsibilities that are visible.
Do not invent unreadable text.
Return plain text only.
"""

    response = generate_response(
        contents=[
            uploaded_file,
            prompt
        ],
        json_mode=False
    )

    text = response.text.strip()

    if not text:
        raise ValueError(
            f"Gemini could not extract readable text from {document_name}."
        )

    return text


# =========================================================
# JOB DESCRIPTION FILE READER
# =========================================================

def extract_job_description_from_file(file_path):
    extension = os.path.splitext(file_path)[1].lower()

    # PDF
    if extension == ".pdf":
        text = extract_pdf_text(file_path)

        if len(text.strip()) >= 50:
            return text

        return extract_visual_text(
            file_path,
            "Job Description PDF"
        )

    # DOCX
    if extension == ".docx":
        text = extract_docx_text(file_path)

        if len(text.strip()) < 50:
            raise ValueError(
                "DOCX Job Description has insufficient readable text."
            )

        return text

    # Images
    if extension in (".jpg", ".jpeg", ".png"):
        return extract_visual_text(
            file_path,
            "Job Description image"
        )

    raise ValueError(
        "Unsupported Job Description format."
    )


# =========================================================
# COURSE URLS
# =========================================================

def add_course_urls(result):
    courses = result.get(
        "recommended_courses",
        []
    )

    for course in courses:
        query = quote_plus(
            f"{course.get('course', '')} {course.get('skill', '')}"
        )

        course["url"] = (
            "https://www.coursera.org/search?query="
            + query
        )

    result["recommended_courses"] = courses[:4]

    return result


# =========================================================
# BASIC SELF-TEST
# =========================================================

if __name__ == "__main__":
    test_jd = """
    Python Backend Developer

    Required:
    Python
    FastAPI
    SQL
    PostgreSQL
    REST APIs
    Docker

    Preferred:
    AWS

    Experience:
    2 years backend development.

    Education:
    Bachelor's degree in Computer Science or related field.

    Responsibilities:
    Build and maintain backend APIs and database-driven services.
    """

    jd_analysis = analyze_job_description(test_jd)

    print("\n===== JD ANALYSIS =====")
    print(
        json.dumps(
            jd_analysis,
            indent=4,
            ensure_ascii=False
        )
    )
