"""Private candidate profile and job-specific application package builder.

Input profile is private runtime JSON; no personal details in source control.
This module never submits applications.
"""
import hashlib
import json
import re
from pathlib import Path
from .tailoring import Evidence, tailor

def build_package(job, profile, output_dir):
    required = ("company", "role", "description", "url")
    if any(not job.get(k) for k in required):
        raise ValueError("Missing required job field")
    if not profile.get("approved_summary") or not profile.get("evidence"):
        raise ValueError("Approved candidate profile required")
    evidence = [Evidence(**item) for item in profile["evidence"]]
    draft = tailor(job["description"], evidence, profile["approved_summary"],
                   job["company"], job["role"], profile.get("contact", {}))
    fingerprint = hashlib.sha256((job["company"].casefold().strip() + "|" +
        job["role"].casefold().strip() + "|" + job["url"].split("?")[0]).encode()).hexdigest()[:16]
    folder = Path(output_dir) / fingerprint
    folder.mkdir(parents=True, exist_ok=True)
    for name, content in (("resume.txt", draft["resume_text"]),
                          ("cover_letter.txt", draft["cover_letter_text"])):
        (folder / name).write_text(content, encoding="utf-8")
    manifest = {"job": {k: job[k] for k in required}, "job_key": fingerprint,
                "matched_skills": draft["matched_skills"],
                "requires_review": True, "submitted": False,
                "status": "draft", "resume_sha256": hashlib.sha256(
                    draft["resume_text"].encode()).hexdigest()}
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return folder, manifest
