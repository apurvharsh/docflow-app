"""Service-layer workflow for drafting, scanning, and saving project documents."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from app.retrieval.embeddings import generate_gemini_text

BASE_DIR = Path(__file__).resolve().parents[1]
DRAFTS_DIR = BASE_DIR.parent / "drafts"
DRAFTS_DIR.mkdir(exist_ok=True, parents=True)

DOCUMENT_TYPE_ALIASES = {
    "PRD": ["prd", "product requirements document", "product requirement doc"],
    "BRD": ["brd", "business requirements document"],
    "SRS": ["srs", "software requirements specification"],
    "ADR": ["adr", "architecture decision record"],
    "API Specification": ["api specification", "api spec", "openapi", "rest api"],
    "Project Plan": ["project plan", "implementation plan"],
    "Design Document": ["design document", "technical design"],
    "Risk Register": ["risk register", "risks"],
    "Test Plan": ["test plan"],
    "Runbook": ["runbook", "operations runbook"],
    "Release Notes": ["release notes"],
    "Proposal": ["proposal", "statement of work"],
    "Meeting Notes": ["meeting notes", "meeting summary"],
    "Other": ["other document", "general doc", "document"],
}

STAGE_ALIASES = {
    "Intake": ["intake"],
    "Discovery": ["discovery", "research"],
    "Requirements": ["requirements", "requirement"],
    "Planning": ["planning", "plan"],
    "Architecture": ["architecture", "architectural"],
    "Design": ["design"],
    "Development": ["development", "build"],
    "Integration": ["integration"],
    "Quality Assurance": ["quality assurance", "qa", "testing"],
    "User Acceptance Testing": ["uat", "user acceptance testing"],
    "Release": ["release"],
    "Operations": ["operations", "ops"],
    "Maintenance": ["maintenance"],
    "Retirement": ["retirement"],
}


def _match_aliases(message: str, aliases: dict[str, list[str]]) -> str | None:
    lowered = message.lower()
    for label, patterns in aliases.items():
        for pattern in patterns:
            if pattern in lowered:
                return label
    return None


def extract_document_context(message: str) -> dict[str, Any]:
    text = (message or "").strip()
    stage = _match_aliases(text, STAGE_ALIASES)
    doc_type = _match_aliases(text, DOCUMENT_TYPE_ALIASES)

    if not doc_type:
        for pattern, label in (
            (r"\b(\w+\s+requirements? document)\b", "PRD"),
            (r"\b(\w+\s+requirements? specification)\b", "SRS"),
            (r"\b(architecture decision record)\b", "ADR"),
            (r"\b(api specification|api spec)\b", "API Specification"),
            (r"\b(test plan|test case)\b", "Test Plan"),
        ):
            if re.search(pattern, text, flags=re.IGNORECASE):
                doc_type = label
                break

    if not stage:
        stage = "Unspecified"
    if not doc_type:
        doc_type = "General Document"

    return {
        "document_type": doc_type,
        "project_stage": stage,
        "template": _infer_template(text, doc_type, stage),
        "raw_message": text,
    }


def _infer_template(message: str, doc_type: str, stage: str) -> str | None:
    lowered = message.lower()
    for token in ("template", "follow", "use"):
        if token in lowered:
            for part in re.split(r"\btemplate\b|\bfollow\b|\buse\b", message, flags=re.IGNORECASE):
                if part.strip():
                    return part.strip()
    return None


def build_context_summary(context: dict[str, Any]) -> str:
    doc_type = context.get("document_type") or "General Document"
    stage = context.get("project_stage") or "Unspecified"
    status = context.get("draft_status") or "new"
    content_len = len((context.get("current_content") or "").strip())
    return (
        "Active context:\n"
        f"- Document type: {doc_type}\n"
        f"- Project stage: {stage}\n"
        f"- Draft status: {status}\n"
        f"- Current draft length: {content_len} chars\n"
    )


def _domain_requirements(request_text: str) -> dict[str, list[str]] | None:
    lowered = request_text.lower()
    if not any(token in lowered for token in ("school", "student", "teacher", "classroom", "academic")):
        return None
    return {
        "needs": [
            "School administrators need a single source of truth for students, staff, classes, and academic records.",
            "Teachers need fast access to attendance, schedules, assignments, and student progress.",
            "Students and guardians need secure access to schedules, results, attendance, fees, and school notices.",
        ],
        "requirements": [
            "The system shall provide role-based access for administrators, teachers, students, guardians, and finance staff.",
            "The system shall maintain student profiles, enrollment history, guardian relationships, and emergency contacts.",
            "The system shall manage classes, sections, subjects, academic terms, timetables, and teacher assignments.",
            "Teachers shall be able to record daily attendance and authorized users shall be able to review attendance history and alerts.",
            "Teachers shall be able to create assignments, record grades, and publish report cards with an approval workflow.",
            "Finance staff shall be able to configure fee structures, record payments, issue receipts, and track outstanding balances.",
            "The system shall send role-appropriate announcements and notifications to students, guardians, and staff.",
            "Administrators shall be able to generate reports for enrollment, attendance, academic performance, and fees.",
            "The system shall maintain an audit trail for changes to student records, grades, attendance, payments, and permissions.",
            "The system shall protect personal data with authentication, authorization, encryption in transit, and configurable retention rules.",
        ],
        "acceptance": [
            "An administrator can create a school term, class, subject, and user account with the correct role.",
            "A teacher can record attendance and a guardian can view attendance only for their linked student.",
            "A teacher can submit grades for review and an authorized administrator can publish a report card.",
            "A finance user can record a fee payment and retrieve an accurate receipt and balance.",
            "Unauthorized users cannot access records outside their assigned school, class, or student relationship.",
            "Critical record changes are visible in the audit log with actor, timestamp, and before/after context.",
        ],
        "discovery": [
            "Primary users are school administrators, teachers, students, guardians, and finance staff.",
            "The discovery scope includes enrollment, student records, class and timetable management, attendance, grades, fees, notifications, and reporting.",
            "Research should validate current school workflows, paper or spreadsheet dependencies, approval responsibilities, and privacy obligations.",
            "Key assumptions are that each user has a defined role, students may have multiple guardians, and academic data is organized by term and class.",
            "Alternatives to evaluate include integrating with an existing student information system versus introducing a unified school management platform.",
        ],
        "open_questions": [
            "Which roles can create, edit, approve, and export student, attendance, grade, and finance records?",
            "How should the system model schools, campuses, academic years, terms, classes, sections, and guardian relationships?",
            "Which notifications are required, which channels are allowed, and how is consent managed?",
            "What retention, export, audit, and privacy requirements apply to student and financial data?",
            "Which existing systems must integrate with the school management app at launch?",
        ],
    }


def _generic_requirements(request_text: str, project_stage: str) -> dict[str, list[str]]:
    """Build useful project-specific content when no known domain blueprint applies."""
    subject = re.sub(r"^\s*(create|build|design|develop|draft|generate|make)\s+", "", request_text, flags=re.IGNORECASE).strip(" .")
    subject = subject or request_text.strip(" .")
    return {
        "needs": [
            f"Users need a reliable way to achieve the outcome requested for {subject}.",
            f"Owners need visibility into scope, decisions, dependencies, and progress for {subject}.",
            f"Stakeholders need measurable evidence that {subject} works for its intended users.",
        ],
        "requirements": [
            f"The solution shall deliver the core capabilities required by {subject}.",
            f"Users shall be able to complete the primary {subject} workflow with clear validation and useful error messages.",
            f"The system shall enforce authentication, authorization, input validation, and safe handling of user data for {subject}.",
            f"The solution shall record status, ownership, dependencies, and audit evidence for the {project_stage} stage.",
            f"The solution shall expose observable success and failure signals so the team can support {subject}.",
        ],
        "acceptance": [
            f"A representative user can complete the primary {subject} workflow from start to finish.",
            f"Invalid, unauthorized, and unavailable-service scenarios produce actionable errors without data loss.",
            f"Each requested capability has an owner, test evidence, and a measurable completion condition.",
            f"The {project_stage} deliverable is reviewable by stakeholders and traceable to the original instruction.",
        ],
        "discovery": [
            f"Identify the primary users, business owner, constraints, and alternatives for {subject}.",
            f"Validate the current workflow, data sources, dependencies, and success measures for {subject}.",
            f"Document assumptions and evidence needed before committing to the {project_stage} deliverable.",
        ],
        "open_questions": [
            f"Who owns {subject}, and which user roles need different permissions?",
            f"What inputs, outputs, integrations, and data-retention rules does {subject} require?",
            f"Which constraints, risks, and measurable success targets must be agreed before delivery?",
        ],
    }


def _fallback_draft(document_type: str, project_stage: str, template: str | None = None, current_content: str | None = None) -> str:
    request_text = (template or current_content or f"Draft {document_type} for the {project_stage} stage.").strip()
    overview = f"This draft is based on the following instruction: {request_text}"
    domain = _domain_requirements(request_text) or _generic_requirements(request_text, project_stage)
    stage_sections = {
        "Intake": ["Purpose", "Stakeholders", "Objectives", "Scope"],
        "Discovery": ["Context", "Research Summary", "Findings", "Open Questions"],
        "Requirements": ["Objective", "User Needs", "Functional Requirements", "Acceptance Criteria"],
        "Planning": ["Plan Overview", "Timeline", "Dependencies", "Risks"],
        "Architecture": ["System Overview", "Key Components", "Interfaces", "Constraints"],
        "Design": ["Design Goals", "Interaction Model", "UI / UX", "Implementation Notes"],
        "Development": ["Build Approach", "Technical Tasks", "Code Ownership", "Validation"],
        "Integration": ["Integration Points", "Contracts", "Dependencies", "Rollout Considerations"],
        "Quality Assurance": ["Test Strategy", "Test Cases", "Exit Criteria", "Defect Handling"],
        "User Acceptance Testing": ["User Scenarios", "Validation Notes", "Sign-off Checklist", "Exit Criteria"],
        "Release": ["Release Plan", "Rollout Steps", "Backward Compatibility", "Roll-back"],
        "Operations": ["Operating Model", "Monitoring", "Ownership", "Support"],
        "Maintenance": ["Maintenance Plan", "Monitoring", "Known Issues", "Update Cadence"],
        "Retirement": ["Retirement Scope", "Migration Notes", "Impact", "Closure Criteria"],
    }
    sections = stage_sections.get(project_stage, ["Overview", "Scope", "Key Details", "Status"])
    stage_guidance = {
        "Intake": [
            "Capture the business request, sponsor, constraints, stakeholders, and expected outcome.",
            "Record the decision needed to move this work into discovery.",
        ],
        "Discovery": [
            "Document research findings, user problems, assumptions, alternatives, and open questions.",
            "Define the evidence required before the solution is committed.",
        ],
        "Requirements": [
            "Define actors, functional behavior, non-functional requirements, dependencies, and measurable acceptance criteria.",
            "Trace each requirement to an owner and validation evidence.",
        ],
        "Planning": [
            "Break the request into milestones, deliverables, owners, dependencies, estimates, and delivery risks.",
            "Define the decision gates and status reporting required to control execution.",
        ],
        "Architecture": [
            "Describe the components, data flows, interfaces, deployment boundaries, security controls, and architectural decisions.",
            "Record trade-offs, constraints, failure modes, and operational quality attributes.",
        ],
        "Design": [
            "Define the user journeys, interaction states, information hierarchy, visual behavior, accessibility, and responsive requirements.",
            "Describe the design decisions needed to implement the requested experience.",
        ],
        "Development": [
            "Translate the request into implementable technical tasks, contracts, data changes, error handling, ownership, and review checkpoints.",
            "Define coding, testing, observability, and completion evidence for the implementation.",
        ],
        "Integration": [
            "Specify integration contracts, payloads, authentication, retries, failure handling, environments, and compatibility requirements.",
            "Define end-to-end validation across every connected system.",
        ],
        "Quality Assurance": [
            "Define test strategy, positive and negative scenarios, test data, automation coverage, defects, and exit criteria.",
            "Map the requested behavior to repeatable evidence that proves it works.",
        ],
        "User Acceptance Testing": [
            "Define business-user scenarios, expected outcomes, evidence, sign-off owners, and release blockers.",
            "Record the acceptance decision and unresolved limitations.",
        ],
        "Release": [
            "Define rollout sequencing, migration, feature flags, communications, monitoring, rollback, and support ownership.",
            "Specify the go-live checklist and measurable release success criteria.",
        ],
        "Operations": [
            "Define runbooks, monitoring, alerts, on-call ownership, incident response, backups, and service-level expectations.",
            "Describe how the delivered capability will be supported in production.",
        ],
        "Maintenance": [
            "Define support cadence, patching, technical debt, performance monitoring, ownership, and change controls.",
            "Set measurable criteria for keeping the capability healthy over time.",
        ],
        "Retirement": [
            "Define decommissioning scope, data retention or migration, user communication, dependencies, and rollback safeguards.",
            "Specify evidence required to close the capability safely.",
        ],
    }
    guidance = stage_guidance.get(project_stage, [
        f"Define the deliverables, owners, dependencies, risks, and validation evidence for the {project_stage} stage.",
        "Make every decision and outcome traceable to the requested input.",
    ])
    document = [
        f"# {document_type} — {project_stage}",
        "",
        f"## Overview",
        f"{overview}",
        "",
    ]
    for section in sections:
        document.append(f"## {section}")
        if section in {"Objective", "Purpose", "Design Goals", "Plan Overview"}:
            document.append(f"Deliver the outcome requested here: {request_text}")
            document.append(f"The objective is to produce a reviewable {document_type} for the {project_stage.lower()} phase.")
        elif section in {"User Needs", "Stakeholders", "Context", "Scope", "Overview"}:
            if domain and section == "User Needs":
                document.extend(f"- {need}" for need in domain["needs"])
            elif domain and section in {"Context", "Scope"}:
                document.extend(f"- {finding}" for finding in domain["discovery"])
            else:
                document.append(f"The document addresses the business and user needs described in this request: {request_text}")
                document.append("- Identify the primary users, owners, and stakeholders.")
                document.append("- Confirm the in-scope outcome and record exclusions before implementation.")
        elif domain and section in {"Research Summary", "Findings"}:
            document.extend(f"- {finding}" for finding in domain["discovery"])
        elif domain and section == "Open Questions":
            document.extend(f"- {question}" for question in domain["open_questions"])
        elif section in {"Functional Requirements", "Technical Tasks", "Key Components", "Integration Points", "User Scenarios"}:
            if domain and section == "Functional Requirements":
                document.extend(f"- {requirement}" for requirement in domain["requirements"])
            else:
                document.append(f"- The solution shall implement the capabilities described in: {request_text}")
                document.append("- Each capability shall have a clear owner, input, expected outcome, and acceptance condition.")
                document.append("- Requirements shall be traceable to validation evidence before sign-off.")
        elif section == "Acceptance Criteria":
            if domain:
                document.extend(f"- {criterion}" for criterion in domain["acceptance"])
            else:
                document.append(f"- The requested outcome is delivered: {request_text}")
                document.append("- Requirements are clear, testable, and measurable.")
                document.append("- Owners, dependencies, and sign-off are captured before release.")
        elif section == "Risks":
            document.append("- Risk: missing stakeholder alignment.")
            document.append("- Mitigation: define ownership and decision path.")
        else:
            document.extend(f"- {item}" for item in guidance)
            document.append(f"- Apply these controls to the requested outcome: {request_text}")
        document.append("")
    document.append("## Approval")
    document.append("Ready for review and scan before final sign-off.")
    return "\n".join(document)


def generate_draft(document_type: str, project_stage: str, user_prompt: str = "", template: str | None = None, current_content: str | None = None) -> str:
    if not document_type:
        document_type = "General Document"
    if not project_stage:
        project_stage = "Unspecified"
    text = user_prompt.strip() if user_prompt else (current_content or "")
    stage_focus = {
        "Intake": "capture the request, business context, stakeholders, goals, constraints, and initial scope",
        "Discovery": "summarize research, current-state findings, user needs, alternatives, assumptions, and open questions",
        "Requirements": "define user needs, functional and non-functional requirements, business rules, traceability, and testable acceptance criteria",
        "Planning": "define work breakdown, sequencing, milestones, estimates, owners, dependencies, risks, and delivery controls",
        "Architecture": "define system boundaries, components, data flows, interfaces, technology decisions, security, scalability, and operational constraints",
        "Design": "define user experience, interaction flows, information architecture, states, accessibility, visual behavior, and implementation-ready design decisions",
        "Development": "define implementation work, technical tasks, coding standards, configuration, error handling, observability, and developer completion criteria",
        "Integration": "define connected systems, contracts, mappings, authentication, synchronization, failure handling, and end-to-end validation",
        "Quality Assurance": "define test strategy, scenarios, test data, automation, defects, regression coverage, and exit criteria",
        "User Acceptance Testing": "define business-user scenarios, expected outcomes, evidence, sign-off owners, and release blockers",
        "Release": "define rollout sequence, migration, feature flags, communications, monitoring, rollback, and go-live criteria",
        "Operations": "define runbooks, monitoring, alerts, on-call ownership, incident response, backups, and service levels",
        "Maintenance": "define support cadence, patching, technical debt, performance monitoring, ownership, and change controls",
        "Retirement": "define decommissioning, data retention or migration, communications, dependencies, and closure evidence",
    }.get(project_stage, f"define the deliverables, decisions, owners, risks, and validation evidence for the {project_stage} stage")
    prompt = (
        "You are DocFlow's Drafting Agent. Create a complete, professional, publication-ready first draft.\n"
        f"Document type: {document_type}\n"
        f"SDLC stage: {project_stage}\n"
        f"Stage focus: {stage_focus}\n"
        f"User instructions: {text or 'Create a suitable document for this type and stage.'}\n"
        + (
            f"\nCurrent draft to revise:\n{current_content}\n"
            "Revise the current draft according to the user's instructions while preserving useful content."
            if current_content else ""
        )
        + (
            "\nStage constraint: draft for the selected SDLC stage only. Do not substitute a PRD, architecture, "
            "test plan, or generic project summary for the selected stage. The document must make the selected "
            "stage explicit and its sections, terminology, decisions, and acceptance criteria must match that stage. "
            "Use clean Markdown formatting: start with one # title, then use ## section headings, "
            "short paragraphs, and - bullet lists where appropriate. Include practical, specific content "
            "rather than filler. For requirements documents, include objectives, scope, users, functional "
            "requirements, non-functional requirements, assumptions, risks, dependencies, and acceptance "
            "criteria when relevant. Keep terminology consistent and make requirements testable. "
            "Return only the document content. Do not mention these instructions, Gemini, prompts, or fallback behavior."
        )
    )
    generated = generate_gemini_text(prompt)
    if generated:
        return generated
    return _fallback_draft(document_type, project_stage, template=template or user_prompt or current_content)


def score_document(document_text: str, document_type: str, project_stage: str) -> dict[str, Any]:
    text = (document_text or "").strip()
    word_count = len(re.findall(r"\S+", text)) if text else 0
    heading_count = len(re.findall(r"^#{1,6}\s+", text, flags=re.MULTILINE))
    bullet_count = len(re.findall(r"^[-*+]\s+", text, flags=re.MULTILINE))
    has_title = bool(re.search(r"^#\s+|^Title\s*:\s*", text, flags=re.MULTILINE))
    has_stage_reference = project_stage.lower() in text.lower() or document_type.lower() in text.lower()

    structural = min(20, 8 + 5 * min(2, heading_count) + (2 if has_title else 0) + (3 if bullet_count >= 2 else 0))
    completeness = min(
        20,
        max(
            0,
            min(
                20,
                6
                + word_count // 20
                + (2 if has_stage_reference else 0)
                + (4 if heading_count >= 2 else 0)
                + (2 if bullet_count >= 2 else 0),
            ),
        ),
    )
    labeling = min(20, 8 + (4 if has_title else 0) + (4 if has_stage_reference else 0) + (4 if heading_count >= 2 else 0))

    criteria = [
        {
            "name": "Structural clarity",
            "score": structural,
            "max_score": 20,
            "minimum": 12,
            "weight": 1,
            "reason": "Checked headings, title, and section organization.",
        },
        {
            "name": "Completeness",
            "score": completeness,
            "max_score": 20,
            "minimum": 12,
            "weight": 1,
            "reason": "Checked how much useful detail is present and whether the required scope is covered.",
        },
        {
            "name": "Labeling accuracy",
            "score": labeling,
            "max_score": 20,
            "minimum": 12,
            "weight": 1.5,
            "reason": "Checked whether the document type and stage are clearly reflected in the content.",
        },
    ]

    total = sum(item["score"] * item["weight"] for item in criteria)
    weighted_max = sum(item["max_score"] * item["weight"] for item in criteria)
    pct = (total / weighted_max) * 100 if weighted_max else 0
    total_points = sum(item["score"] for item in criteria)
    total_threshold = 36
    min_metric_ok = all(item["score"] >= item["minimum"] for item in criteria)
    passed = total_points >= total_threshold and min_metric_ok and pct >= 60
    return {
        "document_type": document_type,
        "project_stage": project_stage,
        "criteria": criteria,
        "total": total_points,
        "threshold": total_threshold,
        "percent": round(pct, 2),
        "passed": passed,
        "clean": passed,
        "status": "clean" if passed else "needs_revision",
        "summary": f"Score: {total_points}/60 ({pct:.2f}%); minimum metric checks: {'pass' if min_metric_ok else 'fail'}.",
    }


def reform_document(document_text: str, document_type: str, project_stage: str, score_result: dict[str, Any] | None = None) -> str:
    cleaned = (document_text or "").strip() or f"{document_type} for {project_stage}"
    sections = [
        f"# {document_type} — {project_stage}",
        "",
        "## Title",
        "A clear title that reflects the document purpose and ownership.",
        "",
        "## Overview",
        "Describe the purpose, business context, and expected result of this document.",
        "",
        "## Scope",
        "- Objective",
        "- In-scope items",
        "- Out-of-scope items",
        "",
        "## Key Details",
        "Capture the main facts, requirements, or process steps that define this deliverable.",
        "",
        "## Acceptance Criteria",
        "- The output is clear and measurable.",
        "- The owner and review path are named.",
        "- The content is aligned to the target stage and document type.",
        "",
        "## Notes",
        "Include open questions, risks, or follow-up actions that still need review.",
    ]
    revised = "\n".join(sections)
    if cleaned and cleaned.lower() not in {"bad text", "n/a"}:
        revised = revised + "\n\n### Original Notes\n" + cleaned
    return revised


def save_document(document_text: str, document_type: str, project_stage: str, filename: str | None = None) -> dict[str, str]:
    safe_name = (filename or f"{document_type.lower().replace(' ', '_')}_{project_stage.lower().replace(' ', '_')}").strip()
    safe_name = re.sub(r"[^a-zA-Z0-9_.-]+", "_", safe_name)
    path = DRAFTS_DIR / f"{safe_name or 'draft'}.md"
    path.write_text(document_text.strip() + "\n", encoding="utf-8")
    return {"path": str(path), "filename": path.name}


def load_saved_documents() -> list[str]:
    return sorted(p.name for p in DRAFTS_DIR.glob("*.md"))
