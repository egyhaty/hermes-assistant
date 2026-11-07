"""Deterministic, evidence-locked resume/cover-letter tailoring for Hermes Jobs.

No external model calls, no personal data in repository. The runtime must load an
approved private profile and the job description. Output is a draft, not submission.
"""
import re
from dataclasses import dataclass
from typing import Mapping, Sequence

@dataclass(frozen=True)
class Evidence:
    skill: str
    proof: str
    category: str = "professional"  # professional | personal_project | foundational

def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z][a-z0-9+#.-]*", text.lower()))

def tailor(job_description: str, evidence: Sequence[Evidence], approved_summary: str,
           company: str, role: str, approved_contact: Mapping[str, str]) -> dict:
    if not job_description.strip() or not evidence or not approved_summary.strip():
        raise ValueError("Job description, verified evidence and approved summary required")
    if not company.strip() or not role.strip():
        raise ValueError("Company and role required")
    job = _tokens(job_description)
    matched = []
    unmatched = []
    for item in evidence:
        # Require an explicit skill phrase, not a vague single-word similarity.
        skill = item.skill.lower().strip()
        if skill and re.search(r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])",
                               job_description.lower()):
            matched.append(item)
        else:
            unmatched.append(item)
    matched.sort(key=lambda e: (e.category != "professional", e.skill.lower()))
    # Preserve all evidence, but order job-relevant items first. No generated claims.
    ordered = matched + unmatched
    lines = [approved_contact.get("name", "Candidate"), role,
             approved_contact.get("email", ""), approved_contact.get("phone", ""),
             "", "PROFESSIONAL SUMMARY", approved_summary, "", "RELEVANT SKILLS & EVIDENCE"]
    for item in ordered:
        label = "Personal project" if item.category == "personal_project" else (
            "Foundational knowledge" if item.category == "foundational" else "Professional experience")
        lines.append(f"- {item.skill} ({label}): {item.proof}")
    cover = (f"Dear Hiring Team at {company},\n\n"
             f"I am interested in the {role} position. {approved_summary}\n\n"
             + ("Relevant experience includes: " + "; ".join(
                 f"{e.skill} — {e.proof}" for e in matched[:3]) + ".\n\n" if matched else
                "I would welcome a conversation about how my background fits your needs.\n\n")
             + "Kind regards,\n" + approved_contact.get("name", "Candidate"))
    return {"resume_text": "\n".join(lines), "cover_letter_text": cover,
            "matched_skills": [e.skill for e in matched],
            "unmatched_skills": [e.skill for e in unmatched],
            "requires_review": True, "submitted": False}
