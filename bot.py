import os
import asyncio

from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from ai_analyzer import (
    analyze_job_description,
    analyze_resume,
    analyze_resume_image,
    extract_pdf_text,
    extract_docx_text,
    extract_job_description_from_file,
    add_course_urls
)


# =========================================================
# ENVIRONMENT
# =========================================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is missing from .env")


# =========================================================
# FOLDER
# =========================================================

RESUME_FOLDER = "resumes"

os.makedirs(
    RESUME_FOLDER,
    exist_ok=True
)


# =========================================================
# SAVE TELEGRAM FILE
# =========================================================

async def save_telegram_file(
    telegram_file,
    file_path
):
    await telegram_file.download_to_drive(
        file_path
    )


# =========================================================
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    context.user_data.clear()

    # -----------------------------
    # SESSION STATE
    # -----------------------------

    context.user_data["state"] = "waiting_for_jds"

    # Multiple Job Descriptions
    context.user_data["job_descriptions"] = []

    # Multiple resumes
    context.user_data["resumes"] = []

    await update.message.reply_text(

        "🤖 AI RESUME SCREENER\n\n"

        "📋 STEP 1 — JOB DESCRIPTIONS\n\n"

        "You can send ONE or MULTIPLE Job Descriptions.\n\n"

        "Supported JD formats:\n"
        "• Text\n"
        "• PDF\n"
        "• DOCX\n"
        "• JPG/JPEG\n"
        "• PNG\n"
        "• Photo\n\n"

        "Send JD 1, JD 2, JD 3...\n\n"

        "When you have finished sending all Job Descriptions, type:\n\n"

        "DONE_JD"
    )


# =========================================================
# ADD JD
# =========================================================

async def add_job_description(
    update,
    context,
    jd_text,
    file_name="Text JD"
):

    if not jd_text or not jd_text.strip():

        await update.message.reply_text(
            "❌ The Job Description appears to be empty.\n"
            "Please send it again."
        )

        return False

    jd_text = jd_text.strip()

    context.user_data["job_descriptions"].append({

        "file_name": file_name,

        "text": jd_text

    })

    number = len(
        context.user_data["job_descriptions"]
    )

    await update.message.reply_text(

        f"✅ Job Description {number} received!\n\n"

        f"📄 {file_name}\n"

        f"📝 {len(jd_text)} characters captured.\n\n"

        "Send another Job Description or type:\n\n"

        "DONE_JD"
    )

    return True


# =========================================================
# PROCESS ALL JDS
# =========================================================

async def process_all_jds(
    update,
    context
):

    job_descriptions = context.user_data.get(
        "job_descriptions",
        []
    )

    if not job_descriptions:

        await update.message.reply_text(

            "⚠️ No Job Descriptions received.\n\n"

            "Please send at least one JD before "
            "typing DONE_JD."
        )

        return False

    await update.message.reply_text(

        "🧠 ANALYZING JOB DESCRIPTIONS...\n\n"

        f"📋 Total JDs: {len(job_descriptions)}"
    )

    successful_jds = []

    failed_jds = []

    # -----------------------------------------------------
    # Analyze each JD only once
    # -----------------------------------------------------

    for index, jd in enumerate(
        job_descriptions,
        start=1
    ):

        await update.message.reply_text(

            f"🔎 UNDERSTANDING JD {index}/{len(job_descriptions)}\n\n"

            f"📄 {jd['file_name']}"
        )

        try:

            jd_analysis = await asyncio.to_thread(

                analyze_job_description,

                jd["text"]

            )

            jd["analysis"] = jd_analysis

            successful_jds.append(jd)

            role = jd_analysis.get(
                "job_title",
                "Job Role"
            )

            required = jd_analysis.get(
                "required_skills",
                []
            )

            await update.message.reply_text(

                f"✅ JD {index} ready\n\n"

                f"💼 Role: {role}\n"

                f"🎯 Required skills: {len(required)}"
            )

        except Exception as e:

            print(
                f"❌ JD {index} ERROR:",
                e
            )

            failed_jds.append({

                "number": index,

                "file_name": jd["file_name"],

                "error": str(e)

            })

    # -----------------------------------------------------
    # Replace list with only successful JDs
    # -----------------------------------------------------

    context.user_data[
        "job_descriptions"
    ] = successful_jds

    if not successful_jds:

        await update.message.reply_text(

            "❌ None of the Job Descriptions "
            "could be analyzed.\n\n"

            "Please type /start and try again."
        )

        return False

    # -----------------------------------------------------
    # Failed JD notice
    # -----------------------------------------------------

    if failed_jds:

        failed_text = "⚠️ Some Job Descriptions failed:\n\n"

        for item in failed_jds:

            failed_text += (
                f"JD {item['number']}: "
                f"{item['file_name']}\n"
            )

        await send_long_message(
            update,
            failed_text
        )

    # -----------------------------------------------------
    # Move to resume stage
    # -----------------------------------------------------

    context.user_data[
        "state"
    ] = "waiting_for_resumes"

    await update.message.reply_text(

        "✅ JOB DESCRIPTIONS READY\n\n"

        f"📋 Active JDs: {len(successful_jds)}\n\n"

        "📄 STEP 2 — RESUMES\n\n"

        "Send resumes as:\n"
        "• PDF\n"
        "• DOCX\n"
        "• JPG/JPEG\n"
        "• PNG\n"
        "• Photos\n\n"

        "You can send 1, 5, 10, 20 or more.\n\n"

        "When finished, type:\n\n"

        "DONE"
    )

    return True


# =========================================================
# TEXT HANDLER
# =========================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.message.text.strip()

    state = context.user_data.get(
        "state"
    )

    # =====================================================
    # WAITING FOR MULTIPLE JDS
    # =====================================================

    if state == "waiting_for_jds":

        # -----------------------------------------------
        # DONE_JD
        # -----------------------------------------------

        if message.upper() == "DONE_JD":

            await process_all_jds(
                update,
                context
            )

            return

        # -----------------------------------------------
        # JD TEXT
        # -----------------------------------------------

        await add_job_description(

            update,

            context,

            message,

            file_name=(
                f"JD_{len(context.user_data.get('job_descriptions', [])) + 1}_text"
            )

        )

        return

    # =====================================================
    # WAITING FOR RESUMES
    # =====================================================

    if state == "waiting_for_resumes":

        # -----------------------------------------------
        # DONE
        # -----------------------------------------------

        if message.upper() == "DONE":

            resumes = context.user_data.get(
                "resumes",
                []
            )

            if not resumes:

                await update.message.reply_text(

                    "⚠️ No resumes received.\n\n"

                    "Please upload at least one resume."
                )

                return

            context.user_data[
                "state"
            ] = "analyzing"

            jds = context.user_data.get(
                "job_descriptions",
                []
            )

            total_comparisons = (
                len(jds) * len(resumes)
            )

            await update.message.reply_text(

                "🔍 SCREENING STARTED\n\n"

                f"📋 Total Job Descriptions: {len(jds)}\n"

                f"👥 Total resumes: {len(resumes)}\n\n"

                f"🧪 Total comparisons: {total_comparisons}\n\n"

                "Every resume will be compared "
                "against every Job Description."
            )

            await analyze_all_resumes(
                update,
                context
            )

            return

        await update.message.reply_text(

            "📄 Please upload a resume "
            "or type DONE when finished."
        )

        return

    # =====================================================
    # OTHER STATES
    # =====================================================

    await update.message.reply_text(

        "⚠️ Type /start to begin a new screening session."
    )


# =========================================================
# DOCUMENT HANDLER
# =========================================================

async def handle_document(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    state = context.user_data.get(
        "state"
    )

    document = update.message.document

    original_name = (
        document.file_name
        or
        "uploaded_file"
    )

    extension = os.path.splitext(
        original_name
    )[1].lower()

    supported = (
        ".pdf",
        ".docx",
        ".jpg",
        ".jpeg",
        ".png"
    )

    if extension not in supported:

        await update.message.reply_text(

            "❌ Unsupported file format.\n\n"

            "Supported:\n"
            "PDF, DOCX, JPG, JPEG, PNG"
        )

        return

    # =====================================================
    # UNIQUE FILE NAME
    # =====================================================

    if state == "waiting_for_jds":

        count = len(
            context.user_data.get(
                "job_descriptions",
                []
            )
        ) + 1

        prefix = f"jd_{count}"

    elif state == "waiting_for_resumes":

        count = len(
            context.user_data.get(
                "resumes",
                []
            )
        ) + 1

        prefix = f"resume_{count}"

    else:

        await update.message.reply_text(
            "⚠️ Please type /start first."
        )

        return

    safe_name = (
        f"{prefix}_{os.path.basename(original_name)}"
    )

    file_path = os.path.join(
        RESUME_FOLDER,
        safe_name
    )

    # =====================================================
    # DOWNLOAD
    # =====================================================

    try:

        telegram_file = await document.get_file()

        await save_telegram_file(
            telegram_file,
            file_path
        )

        print(
            f"📥 Downloaded: {file_path}"
        )

    except Exception as e:

        print(
            "❌ DOWNLOAD ERROR:",
            e
        )

        await update.message.reply_text(
            "❌ Could not download the file."
        )

        return

    # =====================================================
    # JOB DESCRIPTION FILE
    # =====================================================

    if state == "waiting_for_jds":

        await update.message.reply_text(

            f"📄 Job Description received:\n"
            f"{original_name}\n\n"

            "🧠 Reading it..."
        )

        try:

            jd_text = await asyncio.to_thread(

                extract_job_description_from_file,

                file_path

            )

            if not jd_text or len(jd_text.strip()) < 20:

                await update.message.reply_text(

                    "❌ This Job Description contains "
                    "too little readable text."
                )

                return

        except Exception as e:

            print(
                "❌ JD FILE ERROR:",
                e
            )

            await update.message.reply_text(

                "❌ I could not read this "
                "Job Description file."
            )

            return

        await add_job_description(

            update,

            context,

            jd_text,

            file_name=original_name

        )

        return

    # =====================================================
    # NOT RESUME STATE
    # =====================================================

    if state != "waiting_for_resumes":

        await update.message.reply_text(
            "⚠️ Please type /start first."
        )

        return

    # =====================================================
    # PDF RESUME
    # =====================================================

    if extension == ".pdf":

        try:

            text = await asyncio.to_thread(

                extract_pdf_text,

                file_path

            )

        except Exception as e:

            print(
                "PDF TEXT ERROR:",
                e
            )

            text = ""

        # -----------------------------------------------
        # NORMAL TEXT PDF
        # -----------------------------------------------

        if len(text.strip()) >= 100:

            context.user_data[
                "resumes"
            ].append({

                "type": "text",

                "file_name": original_name,

                "file_path": file_path,

                "text": text

            })

            number = len(
                context.user_data[
                    "resumes"
                ]
            )

            await update.message.reply_text(

                f"✅ Resume {number} received!\n\n"

                f"📄 {original_name}\n"

                f"📝 {len(text)} characters extracted.\n\n"

                "Send another resume or type DONE."
            )

            return

        # -----------------------------------------------
        # SCANNED PDF
        # -----------------------------------------------

        context.user_data[
            "resumes"
        ].append({

            "type": "visual",

            "file_name": original_name,

            "file_path": file_path

        })

        number = len(
            context.user_data[
                "resumes"
            ]
        )

        await update.message.reply_text(

            f"✅ Resume {number} received!\n\n"

            f"📄 {original_name}\n\n"

            "🖼️ Scanned/image PDF detected.\n"

            "🤖 Gemini will read the document "
            "during screening.\n\n"

            "Send another resume or type DONE."
        )

        return

    # =====================================================
    # DOCX RESUME
    # =====================================================

    if extension == ".docx":

        try:

            text = await asyncio.to_thread(

                extract_docx_text,

                file_path

            )

        except Exception as e:

            print(
                "DOCX ERROR:",
                e
            )

            await update.message.reply_text(

                "❌ Could not read this DOCX resume."
            )

            return

        if len(text.strip()) < 50:

            await update.message.reply_text(

                "⚠️ This DOCX contains too little "
                "readable text."
            )

            return

        context.user_data[
            "resumes"
        ].append({

            "type": "text",

            "file_name": original_name,

            "file_path": file_path,

            "text": text

        })

        number = len(
            context.user_data[
                "resumes"
            ]
        )

        await update.message.reply_text(

            f"✅ Resume {number} received!\n\n"

            f"📄 {original_name}\n"

            f"📝 {len(text)} characters extracted.\n\n"

            "Send another resume or type DONE."
        )

        return

    # =====================================================
    # IMAGE RESUME FILE
    # =====================================================

    context.user_data[
        "resumes"
    ].append({

        "type": "visual",

        "file_name": original_name,

        "file_path": file_path

    })

    number = len(
        context.user_data[
            "resumes"
        ]
    )

    await update.message.reply_text(

        f"✅ Resume {number} received!\n\n"

        f"🖼️ {original_name}\n\n"

        "🤖 Gemini Vision will analyze it.\n\n"

        "Send another resume or type DONE."
    )


# =========================================================
# DIRECT PHOTO HANDLER
# =========================================================

async def handle_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    state = context.user_data.get(
        "state"
    )

    photo = update.message.photo[-1]

    # =====================================================
    # JD PHOTO
    # =====================================================

    if state == "waiting_for_jds":

        count = len(
            context.user_data.get(
                "job_descriptions",
                []
            )
        ) + 1

        file_name = (
            f"jd_photo_{count}_"
            f"{photo.file_unique_id}.jpg"
        )

    # =====================================================
    # RESUME PHOTO
    # =====================================================

    elif state == "waiting_for_resumes":

        count = len(
            context.user_data.get(
                "resumes",
                []
            )
        ) + 1

        file_name = (
            f"resume_photo_{count}_"
            f"{photo.file_unique_id}.jpg"
        )

    else:

        await update.message.reply_text(
            "⚠️ Please type /start first."
        )

        return

    file_path = os.path.join(
        RESUME_FOLDER,
        file_name
    )

    # =====================================================
    # DOWNLOAD
    # =====================================================

    try:

        telegram_file = await photo.get_file()

        await save_telegram_file(
            telegram_file,
            file_path
        )

    except Exception as e:

        print(
            "❌ PHOTO DOWNLOAD ERROR:",
            e
        )

        await update.message.reply_text(
            "❌ Could not save the image."
        )

        return

    # =====================================================
    # JD PHOTO
    # =====================================================

    if state == "waiting_for_jds":

        await update.message.reply_text(

            "🖼️ Job Description photo received.\n\n"

            "🧠 Reading it..."
        )

        try:

            jd_text = await asyncio.to_thread(

                extract_job_description_from_file,

                file_path

            )

            if not jd_text or len(jd_text.strip()) < 20:

                await update.message.reply_text(

                    "❌ This Job Description photo "
                    "contains too little readable text."
                )

                return

        except Exception as e:

            print(
                "❌ JD PHOTO ERROR:",
                e
            )

            await update.message.reply_text(

                "❌ Could not read the "
                "Job Description photo."
            )

            return

        await add_job_description(

            update,

            context,

            jd_text,

            file_name=file_name

        )

        return

    # =====================================================
    # RESUME PHOTO
    # =====================================================

    context.user_data[
        "resumes"
    ].append({

        "type": "visual",

        "file_name": file_name,

        "file_path": file_path

    })

    number = len(
        context.user_data[
            "resumes"
        ]
    )

    await update.message.reply_text(

        f"✅ Resume {number} received!\n\n"

        "🖼️ Resume photo saved.\n"

        "🤖 Gemini will analyze it during screening.\n\n"

        "Send another resume or type DONE."
    )


# =========================================================
# ANALYZE ALL RESUMES AGAINST ALL JDS
# =========================================================

async def analyze_all_resumes(
    update,
    context
):

    jds = context.user_data.get(
        "job_descriptions",
        []
    )

    resumes = context.user_data.get(
        "resumes",
        []
    )

    all_jd_results = []

    # =====================================================
    # LOOP THROUGH EVERY JD
    # =====================================================

    for jd_index, jd in enumerate(
        jds,
        start=1
    ):

        jd_analysis = jd.get(
            "analysis"
        )

        jd_role = jd_analysis.get(
            "job_title",
            f"Job {jd_index}"
        )

        await update.message.reply_text(

            "━━━━━━━━━━━━━━━━━━━━\n"
            f"💼 JD {jd_index}/{len(jds)}\n"
            f"📋 {jd_role}\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"

            f"👥 Checking {len(resumes)} resumes..."
        )

        jd_results = []

        # =================================================
        # LOOP THROUGH EVERY RESUME
        # =================================================

        for resume_index, resume in enumerate(
            resumes,
            start=1
        ):

            file_name = resume[
                "file_name"
            ]

            await update.message.reply_text(

                f"🔎 JD {jd_index}/{len(jds)}\n"

                f"👤 Candidate {resume_index}/{len(resumes)}\n\n"

                f"📄 {file_name}"
            )

            try:

                # -----------------------------------------
                # NORMAL TEXT RESUME
                # -----------------------------------------

                if resume["type"] == "text":

                    result = await asyncio.to_thread(

                        analyze_resume,

                        jd_analysis,

                        resume["text"]

                    )

                # -----------------------------------------
                # IMAGE / SCANNED PDF
                # -----------------------------------------

                else:

                    result = await asyncio.to_thread(

                        analyze_resume_image,

                        jd_analysis,

                        resume["file_path"]

                    )

                # -----------------------------------------
                # COURSE URLS
                # -----------------------------------------

                result = add_course_urls(
                    result
                )

                jd_results.append({

                    "candidate_number": resume_index,

                    "file_name": file_name,

                    "result": result,

                    "success": True

                })

                print(

                    f"✅ JD {jd_index} / "
                    f"Candidate {resume_index} complete"

                )

            except Exception as e:

                print(

                    f"❌ JD {jd_index} / "
                    f"Candidate {resume_index} ERROR:",
                    e

                )

                jd_results.append({

                    "candidate_number": resume_index,

                    "file_name": file_name,

                    "result": None,

                    "success": False,

                    "error": str(e)

                })

        # =================================================
        # STORE RESULTS FOR THIS JD
        # =================================================

        all_jd_results.append({

            "jd_number": jd_index,

            "jd_file_name": jd["file_name"],

            "jd_role": jd_role,

            "results": jd_results

        })


        # =================================================
        # SEND INDIVIDUAL REPORTS FOR THIS JD
        # =================================================

        successful = [

            item

            for item in jd_results

            if item["success"]

        ]

        await update.message.reply_text(

            f"📊 RESULTS FOR JD {jd_index}\n\n"

            f"💼 Role: {jd_role}\n"

            f"✅ Successfully analyzed: "
            f"{len(successful)}/{len(resumes)}"
        )

        # -------------------------------------------------
        # Detailed candidate reports
        # -------------------------------------------------

        for item in successful:

            await send_candidate_report(

                update,

                item["candidate_number"],

                item["file_name"],

                item["result"],

                jd_number=jd_index,

                jd_role=jd_role

            )

        # -------------------------------------------------
        # Failed candidate reports
        # -------------------------------------------------

        for item in jd_results:

            if not item["success"]:

                await update.message.reply_text(

                    f"⚠️ JD {jd_index} — "
                    f"CANDIDATE #{item['candidate_number']}\n\n"

                    f"📄 {item['file_name']}\n\n"

                    "AI analysis could not be completed.\n\n"

                    "❗ No false 0% score was assigned."
                )

        # =================================================
        # RANKING FOR THIS JD
        # =================================================

        ranked = sorted(

            successful,

            key=lambda item: normalize_score(

                item["result"].get(
                    "match_score",
                    0
                )

            ),

            reverse=True

        )

        if ranked:

            ranking_message = (

                "🏆 FINAL RANKING\n\n"

                f"💼 {jd_role}\n\n"

            )

            medals = [
                "🥇",
                "🥈",
                "🥉"
            ]

            for position, item in enumerate(
                ranked,
                start=1
            ):

                result = item[
                    "result"
                ]

                candidate_name = result.get(

                    "candidate_name",

                    item["file_name"]

                )

                score = result.get(
                    "match_score",
                    0
                )

                if position <= 3:

                    prefix = medals[
                        position - 1
                    ]

                else:

                    prefix = f"{position}."

                ranking_message += (

                    f"{prefix} "
                    f"{candidate_name}\n"

                    f"   📄 {item['file_name']}\n"

                    f"   🎯 {score}%\n\n"

                )

            await send_long_message(

                update,

                ranking_message

            )

    # =====================================================
    # FINAL CROSS-JD SUMMARY
    # =====================================================

    await send_cross_jd_summary(

        update,

        all_jd_results,

        len(resumes)

    )

    context.user_data[
        "state"
    ] = "completed"


# =========================================================
# SCORE NORMALIZER
# =========================================================

def normalize_score(score):

    try:

        return float(score)

    except Exception:

        return 0.0


# =========================================================
# CROSS JD SUMMARY
# =========================================================

async def send_cross_jd_summary(
    update,
    all_jd_results,
    total_resumes
):

    message = (
        "📊 OVERALL SCREENING SUMMARY\n\n"
    )

    message += (
        f"📋 Total Job Descriptions: "
        f"{len(all_jd_results)}\n"

        f"👥 Total Resumes: "
        f"{total_resumes}\n\n"
    )

    for jd in all_jd_results:

        successful = [

            item

            for item in jd["results"]

            if item["success"]

        ]

        ranked = sorted(

            successful,

            key=lambda item: normalize_score(

                item["result"].get(
                    "match_score",
                    0
                )

            ),

            reverse=True

        )

        message += (
            "━━━━━━━━━━━━━━━━━━━━\n"

            f"💼 {jd['jd_role']}\n\n"

        )

        if not ranked:

            message += (
                "❌ No successful analyses.\n\n"
            )

            continue

        # Show top 3 only in summary

        for position, item in enumerate(
            ranked[:3],
            start=1
        ):

            result = item[
                "result"
            ]

            candidate_name = result.get(

                "candidate_name",

                item["file_name"]

            )

            score = result.get(
                "match_score",
                0
            )

            message += (

                f"{position}. "
                f"{candidate_name} — "
                f"{score}%\n"

            )

        message += "\n"

    await send_long_message(

        update,

        message

    )

    await update.message.reply_text(

        "🎉 SCREENING COMPLETED\n\n"

        f"📋 Job Descriptions: "
        f"{len(all_jd_results)}\n"

        f"👥 Resumes: "
        f"{total_resumes}\n\n"

        "Every resume was evaluated against "
        "every successfully analyzed JD.\n\n"

        "Type /start for a new screening session."
    )


# =========================================================
# CANDIDATE REPORT
# =========================================================

async def send_candidate_report(
    update,
    number,
    file_name,
    result,
    jd_number=None,
    jd_role=None
):

    candidate_name = result.get(
        "candidate_name",
        "Unknown"
    )

    score = result.get(
        "match_score",
        0
    )

    matched = result.get(
        "matched_skills",
        []
    )

    missing = result.get(
        "missing_skills",
        []
    )

    experience = result.get(
        "experience_match",
        "Not available."
    )

    education = result.get(
        "education_match",
        "Not available."
    )

    projects = result.get(
        "projects_match",
        "Not available."
    )

    suggestion = result.get(
        "suggestion",
        "No suggestion available."
    )

    courses = result.get(
        "recommended_courses",
        []
    )

    matched_text = "\n".join(

        f"• {skill}"

        for skill in matched

    )

    missing_text = "\n".join(

        f"• {skill}"

        for skill in missing

    )

    if not matched_text:

        matched_text = (
            "• None clearly identified"
        )

    if not missing_text:

        missing_text = (
            "• No major gaps identified"
        )

    # =====================================================
    # COURSE TEXT
    # =====================================================

    course_text = ""

    for course in courses:

        course_text += (

            f"• {course.get('skill', 'Skill')}\n"

            f"  {course.get('course', 'Course')}\n"

            f"  🔗 {course.get('url', '')}\n\n"

        )

    if not course_text:

        course_text = (
            "• No specific course recommendations."
        )

    # =====================================================
    # JD HEADER
    # =====================================================

    jd_header = ""

    if jd_number is not None:

        jd_header = (

            f"💼 JD #{jd_number}\n"

            f"🎯 Role: {jd_role}\n\n"

        )

    # =====================================================
    # REPORT
    # =====================================================

    message = f"""

{jd_header}👤 CANDIDATE #{number}

🧑 {candidate_name}

📄 {file_name}

🎯 MATCH SCORE: {score}%

━━━━━━━━━━━━━━━━━━

✅ MATCHED SKILLS

{matched_text}

━━━━━━━━━━━━━━━━━━

❌ MISSING / WEAK SKILLS

{missing_text}

━━━━━━━━━━━━━━━━━━

📊 EXPERIENCE MATCH

{experience}

━━━━━━━━━━━━━━━━━━

🎓 EDUCATION MATCH

{education}

━━━━━━━━━━━━━━━━━━

🛠️ PROJECT MATCH

{projects}

━━━━━━━━━━━━━━━━━━

💡 RESUME SUGGESTION

{suggestion}

━━━━━━━━━━━━━━━━━━

📚 RECOMMENDED COURSES

{course_text}
"""

    await send_long_message(
        update,
        message
    )


# =========================================================
# LONG MESSAGE HANDLER
# =========================================================

async def send_long_message(
    update,
    message
):

    limit = 3900

    if len(message) <= limit:

        await update.message.reply_text(
            message
        )

        return

    current = ""

    for line in message.splitlines(
        keepends=True
    ):

        if len(current) + len(line) > limit:

            if current:

                await update.message.reply_text(
                    current
                )

            current = ""

        current += line

    if current:

        await update.message.reply_text(
            current
        )


# =========================================================
# MAIN
# =========================================================

def main():

    application = (

        Application

        .builder()

        .token(BOT_TOKEN)

        .build()

    )

    # =====================================================
    # /start
    # =====================================================

    application.add_handler(

        CommandHandler(
            "start",
            start
        )

    )

    # =====================================================
    # TEXT
    # =====================================================

    application.add_handler(

        MessageHandler(

            filters.TEXT &
            ~filters.COMMAND,

            handle_message

        )

    )

    # =====================================================
    # DOCUMENTS
    # =====================================================

    application.add_handler(

        MessageHandler(

            filters.Document.ALL,

            handle_document

        )

    )

    # =====================================================
    # PHOTOS
    # =====================================================

    application.add_handler(

        MessageHandler(

            filters.PHOTO,

            handle_photo

        )

    )

    print(
        "🤖 AI Resume Screener is running..."
    )

    application.run_polling()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    main()