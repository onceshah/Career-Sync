"""
CareerSync Feature API Extensions: Resume RAG Scoring, AI Response Generator, & Manual Entry.
"""

import logging
import re
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.domain.ats_enums import ApplicationLifecycleState, ReviewStatus
from app.domain.ats_models import Application
from app.infrastructure.persistence.database import SessionLocal
from app.infrastructure.persistence.repository import ATSRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Extended Features"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# In-memory candidate resume store for RAG matching
CANDIDATE_RESUME_TEXT = """
Experienced Software Engineer proficient in Python, FastAPI, React, SQL, PostgreSQL, Docker, AWS, Data Structures, Algorithms, REST APIs, Git, Pytest, Machine Learning, LangChain, Microservices, System Design, CI/CD pipelines, LLMs, and System Architecture.
Degree: B.Tech Computer Science Engineering.
Experience: 3 years developing web applications and scalable backend infrastructure.
"""

# Common skills taxonomy for matching
SKILL_TAXONOMY = {
    "python", "fastapi", "django", "flask", "react", "javascript", "typescript",
    "html", "css", "sql", "postgresql", "sqlite", "mongodb", "docker", "kubernetes",
    "aws", "azure", "gcp", "git", "pytest", "machine learning", "ai", "llm",
    "langchain", "microservices", "system design", "rest api", "ci/cd", "linux",
    "java", "c++", "data structures", "algorithms", "redux", "tailwind", "node.js"
}


class ResumeUploadResponse(BaseModel):
    status: str
    character_count: int
    extracted_skills: List[str]
    message: str


class CompatibilityResult(BaseModel):
    application_id: str
    company_name: str
    job_title: str
    match_score: int
    match_category: str
    matching_skills: List[str]
    missing_skills: List[str]
    summary_analysis: str


class DraftResponseRequest(BaseModel):
    intent: str = Field(
        default="interview_confirm",
        description="Type of email response: interview_confirm, reschedule, follow_up, salary_inquiry, decline"
    )
    custom_notes: Optional[str] = Field(default="", description="Additional candidate notes to inject")


class DraftResponseResult(BaseModel):
    application_id: str
    company_name: str
    job_title: str
    subject: str
    draft_body: str
    intent: str


class CreateApplicationRequest(BaseModel):
    company_name: str
    job_title: str
    requisition_id: Optional[str] = None
    platform: Optional[str] = "Manual Entry"
    initial_state: ApplicationLifecycleState = ApplicationLifecycleState.APPLIED


@router.post("/resume/upload", response_model=ResumeUploadResponse, summary="Upload candidate resume for RAG matching")
async def upload_resume(
    file: Optional[UploadFile] = File(None),
    raw_text: Optional[str] = Form(None)
):
    global CANDIDATE_RESUME_TEXT
    resume_content = ""
    if file:
        content_bytes = await file.read()
        try:
            resume_content = content_bytes.decode("utf-8", errors="ignore")
        except Exception:
            resume_content = str(content_bytes)
    elif raw_text:
        resume_content = raw_text

    if not resume_content.strip():
        raise HTTPException(status_code=400, detail="No resume content provided.")

    CANDIDATE_RESUME_TEXT = resume_content

    # Extract skills
    content_lower = resume_content.lower()
    found_skills = [skill for skill in SKILL_TAXONOMY if skill in content_lower]

    logger.info("Uploaded candidate resume. Extracted %d skills.", len(found_skills))
    return ResumeUploadResponse(
        status="success",
        character_count=len(resume_content),
        extracted_skills=sorted(found_skills),
        message="Resume successfully parsed and indexed for RAG matching."
    )


@router.get("/applications/{application_id}/compatibility", response_model=CompatibilityResult, summary="Calculate RAG Job-Fit score")
def get_compatibility(application_id: str, db: Session = Depends(get_db)):
    repo = ATSRepository(db)
    app_record = repo.get_application_by_id(application_id)
    if not app_record:
        raise HTTPException(status_code=404, detail=f"Application {application_id} not found.")

    target_text = f"{app_record.job_title} {app_record.company_name}".lower()
    resume_lower = CANDIDATE_RESUME_TEXT.lower()

    # Required skills inferred from job title
    required_skills = set()
    for skill in SKILL_TAXONOMY:
        if skill in target_text:
            required_skills.add(skill)

    # General tech stack requirement default
    if not required_skills:
        required_skills = {"python", "react", "sql", "git", "rest api"}

    matching_skills = [s for s in required_skills if s in resume_lower]
    missing_skills = [s for s in required_skills if s not in resume_lower]

    # Calculate match score
    if required_skills:
        base_score = int((len(matching_skills) / len(required_skills)) * 60) + 35
    else:
        base_score = 75

    base_score = min(98, max(40, base_score))

    if base_score >= 80:
        match_cat = "Strong Match"
    elif base_score >= 60:
        match_cat = "Moderate Match"
    else:
        match_cat = "Potential Skills Gap"

    analysis = (
        f"Candidate profile matches {len(matching_skills)} out of {len(required_skills)} key requirements for "
        f"the {app_record.job_title} role at {app_record.company_name}."
    )

    return CompatibilityResult(
        application_id=application_id,
        company_name=app_record.company_name,
        job_title=app_record.job_title,
        match_score=base_score,
        match_category=match_cat,
        matching_skills=sorted(matching_skills),
        missing_skills=sorted(missing_skills),
        summary_analysis=analysis
    )


@router.post("/applications/{application_id}/draft-response", response_model=DraftResponseResult, summary="Generate AI Email Reply Draft")
def generate_draft_response(
    application_id: str,
    payload: DraftResponseRequest,
    db: Session = Depends(get_db)
):
    repo = ATSRepository(db)
    app_record = repo.get_application_by_id(application_id)
    if not app_record:
        raise HTTPException(status_code=404, detail=f"Application {application_id} not found.")

    company = app_record.company_name
    role = app_record.job_title
    intent = payload.intent
    notes = f" Note: {payload.custom_notes}" if payload.custom_notes else ""

    if intent == "interview_confirm":
        subject = f"Re: Interview Confirmation — {role} at {company}"
        body = (
            f"Dear Hiring Team at {company},\n\n"
            f"Thank you for reaching out regarding the {role} position. I am excited about this opportunity "
            f"and would be delighted to confirm my availability for the upcoming interview.{notes}\n\n"
            f"Please let me know if there are any specific materials or preparations required beforehand.\n\n"
            f"Best regards,\n[Candidate Name]"
        )
    elif intent == "reschedule":
        subject = f"Re: Interview Reschedule Request — {role} at {company}"
        body = (
            f"Dear Hiring Team at {company},\n\n"
            f"Thank you for inviting me to interview for the {role} position. Due to a scheduling conflict, "
            f"I would appreciate it if we could reschedule our session to an alternate time.{notes}\n\n"
            f"I am available on upcoming weekdays during regular business hours. Thank you for your flexibility.\n\n"
            f"Best regards,\n[Candidate Name]"
        )
    elif intent == "follow_up":
        subject = f"Status Inquiry — Application for {role} at {company}"
        body = (
            f"Dear Hiring Manager,\n\n"
            f"I hope this message finds you well. I am writing to follow up on my recent application for the "
            f"{role} position at {company}. I remain very interested in the team's work.{notes}\n\n"
            f"Could you please share any updates regarding the next steps in the recruitment process?\n\n"
            f"Thank you for your time and consideration.\n\n"
            f"Best regards,\n[Candidate Name]"
        )
    elif intent == "salary_inquiry":
        subject = f"Re: {role} Offer Details & Discussion — {company}"
        body = (
            f"Dear Hiring Team at {company},\n\n"
            f"Thank you very much for extending the offer for the {role} role. I am thrilled about the prospect of joining {company}.\n\n"
            f"Before finalizing, I would welcome a brief discussion regarding compensation and benefits structure.{notes}\n\n"
            f"Looking forward to connecting.\n\n"
            f"Best regards,\n[Candidate Name]"
        )
    else:  # decline
        subject = f"Re: Application Update — {role} at {company}"
        body = (
            f"Dear Hiring Team at {company},\n\n"
            f"Thank you for your time and consideration throughout the selection process for the {role} position. "
            f"At this stage, I have decided to pursue another opportunity that closely aligns with my immediate goals.\n\n"
            f"I sincerely appreciate your time and wish {company} all the best.\n\n"
            f"Best regards,\n[Candidate Name]"
        )

    return DraftResponseResult(
        application_id=application_id,
        company_name=company,
        job_title=role,
        subject=subject,
        draft_body=body,
        intent=intent
    )


@router.post("/applications/create", response_model=Application, summary="Manually create a new application")
def create_application(payload: CreateApplicationRequest, db: Session = Depends(get_db)):
    repo = ATSRepository(db)
    with repo.transaction():
        app_record = repo.get_or_create_application(
            company_name=payload.company_name,
            job_title=payload.job_title,
            requisition_id=payload.requisition_id,
            platform=payload.platform,
            initial_state=payload.initial_state,
        )
    logger.info("Manually created application: %s at %s", payload.job_title, payload.company_name)
    return app_record
