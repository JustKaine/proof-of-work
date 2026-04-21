"""Tool: faq

Answer common questions about using the MCP resume server, covering workspace
folder layout, resume types, file naming, workflow steps, what each tool does,
verification tags, and policy rules.

When the question is about folder structure or workspace setup the response
also includes a ``workspace_setup`` object whose ``readme_content`` field
contains a ready-to-save README for the user's resume-workspace/ root.
"""
from __future__ import annotations

from typing import Any

from engine.audit import log_event
from engine.contracts import ContractValidationError
from helpers.naming import build_full_workspace_setup, _read_template
import engine.session as session_state

# ---------------------------------------------------------------------------
# README content returned inside workspace_setup for folder/workspace questions
# ---------------------------------------------------------------------------

_README_CONTENT = """\
# README — Resume Workspace

## Folder Structure

```
📁 resume-workspace/
│
├── 📁 source/                     ← Your base resumes and master profile
│   ├── master-profile.md          ← Comprehensive "everything" resume (used in map_resume)
│   ├── resume-tech.md             ← Tech-focused base resume
│   ├── resume-hybrid.md           ← Hybrid base resume
│   └── resume-executive.md        ← Executive base resume
│
├── 📁 job-descriptions/           ← One file per job description
│   ├── template.md                ← Copy this for each new JD
│   └── company-role-YYYY-MM.md    ← e.g., microsoft-sre-2026-03.md
│
├── 📁 tailored/                   ← One subfolder per job application
│   └── 📁 company-role-YYYY-MM/
│       ├── jd-analysis.md         ← Output from analyze_jd
│       ├── mapping.md             ← Output from map_resume
│       ├── draft.md               ← Output from draft_resume
│       └── final.md               ← Output from finalize
│
└── 📁 archive/
    └── 📁 old-resumes/            ← Previous versions for reference
```

## Workflow

1. Fill out `source/master-profile.md` with all your experience.
2. Copy `job-descriptions/template.md` → rename to `company-role-YYYY-MM.md` and paste the JD.
3. Run `analyze_jd` on the JD file.
4. Run `map_resume` with your master profile + JD analysis output.
5. Run `draft_resume` to generate the tailored resume draft.
6. Answer all verification questions surfaced by `draft_resume`.
7. Run `finalize` to produce the final output (blocked until all [USER-VERIFY] items are resolved).
8. Save all outputs in a new `tailored/company-role-YYYY-MM/` folder.

## Resume Types

| Type        | Best For                                                         |
|-------------|------------------------------------------------------------------|
| `tech`      | Software engineers, architects, DevOps, data engineers           |
| `non_tech`  | Business, operations, HR, finance, sales roles                   |
| `hybrid`    | Product managers, engineering managers, technical leads          |
| `executive` | VPs, Directors, C-suite targeting board/org-level roles          |

Pass `resume_type` to any tool call. The server will auto-select a profile if
you omit it, based on the job description and your resume content.

## File Naming Conventions

- **JD files:** `company-role-YYYY-MM.md` — e.g., `acme-sre-2026-03.md`
- **Tailored folders:** `company-role-YYYY.MM` — e.g., `acme-sre-2026.03/`
- **Default resume filename:** `resume.md`
- **Master profile:** `source/master-profile.md`

Suggested subfolders inside each tailored output folder:

| Sub-folder | Purpose                              |
|------------|--------------------------------------|
| `v1/`      | First iteration of the tailored resume |
| `brief/`   | Single-page condensed version        |
| `detailed/`| Multi-page expanded version          |
| `exec/`    | Executive / board-level version      |

## Tools Reference

| Tool           | Purpose                                                            |
|----------------|--------------------------------------------------------------------|
| `analyze_jd`   | Extract and prioritize requirements from 1–3 job descriptions      |
| `map_resume`   | Map resume evidence to JD requirements; score gaps, detect shifts  |
| `draft_resume` | Generate a tagged draft with provenance labels and verification Qs |
| `finalize`     | Produce the final resume after all verification items are resolved |
| `faq`          | Answer questions about folder layout, types, naming, workflow, etc.|

## Verification Tags

Every claim in a generated resume is tagged to show its confidence level:

| Tag            | Meaning                                                          |
|----------------|------------------------------------------------------------------|
| `[VERIFIED]`   | Directly supported by evidence in your resume text               |
| `[INFERRED]`   | Reasonably inferred from adjacent or related experience          |
| `[STRETCH]`    | Plausible claim that needs your confirmation                     |
| `[USER-VERIFY]`| Must be confirmed by you before `finalize` will unblock          |

When answering verification questions use status values:
`verified` · `rejected` · `deferred`

## Policy Rules (P0–P4)

| Rule | Name              | Effect                                                          |
|------|-------------------|-----------------------------------------------------------------|
| P0   | Truth Safety      | No fabrication; every claim must carry a provenance tag         |
| P1   | Verification Gate | `finalize` is blocked while unresolved [USER-VERIFY] items exist|
| P2   | Workflow Order    | `analyze_jd` must run before `finalize`; domain-shift alerting  |
| P3   | Quality           | Action + Context + Result bullet format; seniority alignment    |
| P4   | ATS Format        | No markdown tables/images in final output; sections match profile|

## FAQ

**Q: What folder structure works best to create resumes with this MCP?**
Use the `resume-workspace/` layout above: `source/` for base profiles,
`job-descriptions/` for each JD, and `tailored/company-role-YYYY-MM/` for
each application's outputs. Ask the `faq` tool with topic *folder_structure*
to receive the full workspace_setup object you can save as this README.

**Q: What types of resumes can be built?**
Four profiles — `tech`, `non_tech`, `hybrid`, and `executive` — each
emphasising different sections and signal types. See the Resume Types table.

**Q: How should I name the files I want to use?**
JD files: `company-role-YYYY-MM.md`. Master profile: `source/master-profile.md`.
Output folders: `company-role-YYYY.MM/`. Resumes: `resume.md`.
"""

# ---------------------------------------------------------------------------
# Knowledge base
# ---------------------------------------------------------------------------

_KB: dict[str, dict[str, Any]] = {
    "getting_started": {
        "answer": (
            "Let me get you set up.\n\n"
            "STEP 1 — Create your workspace (do this first):\n"
            "  I can create the resume-workspace folder structure on your computer\n"
            "  right now, including seed files from the official templates.\n\n"
            "  ➜ Say 'yes' and I will create:\n"
            "    resume-workspace/\n"
            "    ├── source/master-profile.md      ← template pre-populated\n"
            "    ├── job-descriptions/template.md  ← template pre-populated\n"
            "    ├── tailored/\n"
            "    └── archive/old-resumes/\n\n"
            "  ➜ If you prefer not to create folders, say 'show me the template'\n"
            "    and I will paste the master-profile template in chat so you can\n"
            "    copy it manually.\n\n"
            "STEP 2 — Fill out source/master-profile.md:\n"
            "  Once the workspace exists, open source/master-profile.md and fill\n"
            "  in ALL your experience following the template guidance — every role,\n"
            "  skill, certification, and project, even items you wouldn't put on a\n"
            "  single targeted resume. This is the evidence source the tools use\n"
            "  when matching against job descriptions.\n\n"
            "STEP 3 — Add a job description:\n"
            "  Copy job-descriptions/template.md → rename to company-role-YYYY-MM.md\n"
            "  (e.g. acme-sre-2026-03.md) and paste the full JD text.\n\n"
            "Then run the 4-tool workflow:\n"
            "  4. analyze_jd   → extract and prioritize requirements\n"
            "  5. map_resume   → match your profile to the JD; surface gaps\n"
            "  6. draft_resume → generate a tagged draft + verification questions\n"
            "  7. finalize     → produce final output once all items are resolved\n\n"
            "Would you like me to create the workspace now?"
        ),
        "related_topics": ["folder_structure", "workflow", "resume_types"],
        "include_workspace": True,
        "include_templates": True,
    },
    "folder_structure": {
        "answer": (
            "The recommended workspace layout is:\n\n"
            "  resume-workspace/\n"
            "  ├── source/               ← Base resumes + master-profile.md\n"
            "  ├── job-descriptions/     ← One .md file per JD (use template.md)\n"
            "  ├── tailored/             ← One subfolder per application\n"
            "  │   └── company-role-YYYY-MM/\n"
            "  │       ├── jd-analysis.md\n"
            "  │       ├── mapping.md\n"
            "  │       ├── draft.md\n"
            "  │       └── final.md\n"
            "  └── archive/              ← Old versions\n"
            "      └── old-resumes/\n\n"
            "IMPORTANT: Use EXACTLY this structure. Do not create numbered folders\n"
            "(01-input/, 02-analysis/, etc.), extra directories, or alternative layouts.\n\n"
            "Place master-profile.md in source/. It is your 'everything' resume used "
            "by map_resume. Each tailored application gets its own subfolder under "
            "tailored/ named company-role-YYYY-MM.\n\n"
            "The workspace_setup field in this response includes the complete structure\n"
            "and template files to populate it."
        ),
        "related_topics": ["file_naming", "workflow", "getting_started"],
        "include_workspace": True,
    },
    "resume_types": {
        "answer": (
            _README_CONTENT = """
            # README — Resume Workspace

            ## Folder Structure

            ```
            📁 resume-workspace/
            ├── source/                     ← Your base resumes and master profile
            │   ├── master-profile.md       ← Comprehensive "everything" resume (used in map_resume)
            │   ├── resume-tech.md          ← Tech-focused base resume
            │   ├── resume-hybrid.md        ← Hybrid base resume
            │   └── resume-executive.md     ← Executive base resume
            ├── job-descriptions/           ← One file per job description
            │   ├── template.md             ← Copy this for each new JD
            │   ├── company-role-YYYY-MM.txt← Recommended: plain text is easiest
            │   └── company-role-YYYY-MM.md ← Also supported
            ├── tailored/                   ← One subfolder per job application
            │   └── company-role-YYYY-MM/
            │       ├── jd-analysis.md      ← Output from analyze_jd
            │       ├── mapping.md          ← Output from map_resume
            │       ├── draft.md            ← Output from draft_resume
            │       └── final.md            ← Output from finalize
            └── archive/
                └── old-resumes/            ← Previous versions for reference
            ```

            ## Workflow

            1. Fill out `source/master-profile.md` with all your experience.
            2. Add a job description file under `job-descriptions/` (plain text `.txt` is easiest, but `.md` is also supported).
            3. Run `analyze_jd` on the JD file.
            4. Run `map_resume` with your master profile + JD analysis output.
            5. Run `draft_resume` to generate the tailored resume draft.
            6. Answer all verification questions surfaced by `draft_resume`.
            7. Run `finalize` to produce the final output (blocked until all [USER-VERIFY] items are resolved).
            8. Save all outputs in a new `tailored/company-role-YYYY-MM/` folder.

            For full usage guidance, example prompts, and user instructions, see the root [USE_README.md](../USE_README.md).

            ## Resume Types

            | Type        | Best For                                                         |
            | ----------- | ---------------------------------------------------------------- |
            | `tech`      | Software engineers, architects, DevOps, data engineers           |
            | `non_tech`  | Business, operations, HR, finance, sales roles                   |
            | `hybrid`    | Product managers, engineering managers, technical leads          |
            | `executive` | VPs, Directors, C-suite targeting board/org-level roles          |

            Pass `resume_type` to any tool call. The server will auto-select a profile if you omit it, based on the job description and your resume content.

            ## File Naming Conventions

            - **JD files:** `company-role-YYYY-MM.txt` (recommended) or `.md` — e.g., `acme-sre-2026-03.txt`
            - **Tailored folders:** `company-role-YYYY.MM` — e.g., `acme-sre-2026.03/`
            - **Default resume filename:** `resume.md`
            - **Master profile:** `source/master-profile.md`

            Suggested subfolders inside each tailored output folder:

            | Sub-folder | Purpose                              |
            | ---------- | ------------------------------------ |
            | `v1/`      | First iteration of the tailored resume |
            | `brief/`   | Single-page condensed version        |
            | `detailed/`| Multi-page expanded version          |
            | `exec/`    | Executive / board-level version      |

            ## Tools Reference

            | Tool           | Purpose                                                            |
            | -------------- | ------------------------------------------------------------------ |
            | `analyze_jd`   | Extract and prioritize requirements from 1–3 job descriptions      |
            | `map_resume`   | Map resume evidence to JD requirements; score gaps, detect shifts  |
            | `draft_resume` | Generate a tagged draft with provenance labels and verification Qs |
            | `finalize`     | Produce the final resume after all verification items are resolved |
            | `faq`          | Answer questions about folder layout, types, naming, workflow, etc.|

            ## Verification Tags

            Every claim in a generated resume is tagged to show its confidence level:

            | Tag            | Meaning                                                          |
            | -------------- | --------------------------------------------------------------- |
            | `[VERIFIED]`   | Directly supported by evidence in your resume text               |
            | `[INFERRED]`   | Reasonably inferred from adjacent or related experience          |
            | `[STRETCH]`    | Plausible claim that needs your confirmation                     |
            | `[USER-VERIFY]`| Must be confirmed by you before `finalize` will unblock          |

            When answering verification questions use status values: `verified` · `rejected` · `deferred`

            ## Policy Rules (P0–P5)

            | Rule | Name              | Effect                                                          |
            | ---- | ----------------- | -------------------------------------------------------------- |
            | P0   | Truth Safety      | No fabrication; every claim must carry a provenance tag         |
            | P1   | Verification Gate | `finalize` is blocked while unresolved [USER-VERIFY] items exist|
            | P2   | Workflow Order    | `analyze_jd` must run before `finalize`; domain-shift alerting  |
            | P3   | Quality           | Action + Context + Result bullet format; seniority alignment    |
            | P4   | ATS Format        | No markdown tables/images in final output; sections match profile|
            | P5   | User Data Isolation | User-scoped data and profile evidence protections             |

            ## FAQ

            **Q: What folder structure works best to create resumes with this MCP?**
            Use the `resume-workspace/` layout above: `source/` for base profiles, `job-descriptions/` for each JD (plain text `.txt` is easiest), and `tailored/company-role-YYYY-MM/` for each application's outputs. Ask the `faq` tool with topic *folder_structure* to receive the full workspace_setup object you can save as this README.

            **Q: What types of resumes can be built?**
            Four profiles — `tech`, `non_tech`, `hybrid`, and `executive` — each emphasising different sections and signal types. See the Resume Types table.

            **Q: How should I name the files I want to use?**
            JD files: `company-role-YYYY-MM.txt` (recommended) or `.md`. Master profile: `source/master-profile.md`. Output folders: `company-role-YYYY.MM/`. Resumes: `resume.md`.

            For more usage examples, prompts, and user instructions, see the root [USE_README.md](../USE_README.md).
            """
            "include ALL experience, not just what fits one role.\n\n"
            "Key sections to fill out:\n\n"
            "  Contact           — Name, location, email, LinkedIn, portfolio/GitHub\n"
            "  Professional      — 3–5 sentences covering your full career arc\n"
            "    Summary           (breadth, not targeted to one role)\n"
            "  Core Competencies — ALL skills grouped by category with proficiency\n"
            "    • Technical:      Languages, cloud, data, tools & platforms\n"
            "    • Leadership:     Team size, cross-functional, process, domain\n"
            "  Experience        — EVERY role, including short stints and consulting\n"
            "  Certifications    — All current and expired (note dates)\n"
            "  Education         — Degrees, relevant coursework\n"
            "  Additional        — Side projects, open source, publications, awards\n\n"
            "Writing effective bullets — use Action + Context + Result format:\n\n"
            "  GOOD:  'Migrated 12 production services from EC2 to EKS, reducing\n"
            "          deployment time by 60% and saving $40K/month in compute costs'\n\n"
            "  WEAK:  'Worked on Kubernetes migration project'\n\n"
            "Tips for strong evidence:\n"
            "  • Quantify outcomes: cost saved, time reduced, users impacted, SLA improved\n"
            "  • Include scope indicators: team size, budget, org reach\n"
            "  • Show progression: increasing responsibility across roles\n"
            "  • Cover breadth: the map_resume tool can only match what's in your profile\n\n"
            "Use the master-profile-template.md to get started — it has all sections\n"
            "pre-structured with guidance comments."
        ),
        "related_topics": ["getting_started", "resume_types", "workflow"],
        "include_workspace": False,
        "include_templates": True,
    },
    "gaps_and_shifts": {
        "answer": (
            "When map_resume finds gaps between your experience and job requirements,\n"
            "you have several strategies:\n\n"
            "Missing requirements — fill the gap with adjacent evidence:\n"
            "  • Transferable skills from another domain or role\n"
            "  • Side projects, open source contributions, or volunteer work\n"
            "  • Certifications or coursework (even in-progress)\n"
            "  • Skills used informally that aren't on your current resume\n\n"
            "  map_resume will tag these as [INFERRED] or [STRETCH] so you\n"
            "  can decide which claims to keep, strengthen, or remove.\n\n"
            "Partial matches — strengthen with specifics:\n"
            "  • Add metrics, scope, or context to partial-match bullets\n"
            "  • Reference adjacent tools/platforms in the same ecosystem\n"
            "  • Connect the partial to a concrete business outcome\n\n"
            "Career pivots and domain shifts:\n"
            "  The server computes a domain_shift_score (0–1) during map_resume.\n"
            "  If the score is >= 0.35, a domain-shift alert is triggered.\n"
            "  This means the JD targets a significantly different domain than\n"
            "  your resume evidence.\n\n"
            "  For high domain-shift scenarios:\n"
            "  • Emphasize transferable patterns (scaling, automation, leadership)\n"
            "  • Lead with outcomes and impact rather than specific technologies\n"
            "  • Use the hybrid or executive profile to frame cross-domain value\n"
            "  • Add a 'Career Transition' or 'Relevant Projects' section to\n"
            "    your master profile highlighting crossover experience\n\n"
            "The interactive questions from map_resume will ask specifically\n"
            "about your missing and partial items — answer with as much\n"
            "detail as possible so draft_resume has evidence to work with."
        ),
        "related_topics": ["master_profile", "workflow", "verification_tags"],
        "include_workspace": False,
    },
    "multiple_applications": {
        "answer": (
            "You can reuse the same master profile for unlimited job applications.\n"
            "Each application is independent — here's the workflow:\n\n"
            "  1. Your source/master-profile.md stays the same (update it when\n"
            "     your experience changes, not per application).\n\n"
            "  2. For each new job, copy job-descriptions/template.md and rename\n"
            "     to company-role-YYYY-MM.md (e.g. acme-sre-2026-03.md).\n\n"
            "  3. Run the full 4-tool workflow against that JD:\n"
            "     analyze_jd → map_resume → draft_resume → finalize\n\n"
            "  4. All outputs land in tailored/company-role-YYYY-MM/:\n"
            "     jd-analysis.md, mapping.md, draft.md, final.md\n\n"
            "  5. Each tailored folder is self-contained — you can compare\n"
            "     applications side by side.\n\n"
            "Applying to similar roles?\n"
            "  • The server auto-selects a resume profile (tech, hybrid, etc.)\n"
            "    based on each JD — it may pick differently for related roles.\n"
            "  • Reuse variant subfolders (v1/, brief/, detailed/, exec/) when\n"
            "    you need multiple versions for the same application.\n\n"
            "Updating your master profile:\n"
            "  If map_resume keeps surfacing the same gaps across applications,\n"
            "  consider adding that experience to your master profile so it's\n"
            "  available for future runs."
        ),
        "related_topics": ["getting_started", "folder_structure", "file_naming"],
        "include_workspace": False,
    },
    "output_formats": {
        "answer": (
            "The draft_resume tool supports these output formats via the\n"
            "output_format parameter:\n\n"
            "  md     Markdown (default). Best for editing and iteration.\n"
            "         All verification tags and evidence_log are preserved.\n\n"
            "  txt    Plain text. ATS-safe by default — no formatting that\n"
            "         could confuse applicant tracking systems.\n\n"
            "  docx   Word document. Good for recruiters and hiring managers\n"
            "         who expect a polished .docx attachment.\n\n"
            "  pdf    PDF. Best for final submission when formatting must be\n"
            "         pixel-perfect. Note: some ATS systems struggle with PDFs.\n\n"
            "ATS considerations (Policy P4):\n"
            "  • No markdown tables or images in final output\n"
            "  • Section headings must match the selected profile's expected layout\n"
            "  • Stick to standard section names: Summary, Experience, Skills, Education\n"
            "  • Avoid columns, text boxes, or graphics — they break ATS parsers\n"
            "  • txt format is the safest for ATS; md is best for iteration\n\n"
            "Recommended approach:\n"
            "  1. Draft and iterate in md format\n"
            "  2. Run finalize\n"
            "  3. Export to txt (ATS submission) or docx (email/recruiter) as needed"
        ),
        "related_topics": ["workflow", "policies", "tools"],
        "include_workspace": False,
    },
}

# ---------------------------------------------------------------------------
# Topic detection: ordered list of (keywords, topic_key)
# ---------------------------------------------------------------------------

_ROUTING: list[tuple[list[str], str]] = [
    (["getting started", "get started", "how to build", "build a resume",
      "create a resume", "make a resume", "preparation",
      "first step", "where do i start", "how do i start",
      "new resume", "start building", "help me build",
      "start creating"], "getting_started"),
    (["master profile", "master-profile", "everything resume",
      "what should i put", "what to put", "what to include",
      "write my profile", "write my resume", "good bullet",
      "write experience", "how to write", "action context result",
      "acr format"], "master_profile"),
    (["gap", "missing", "don't have", "dont have", "lack",
      "career change", "career pivot", "changing career",
      "domain shift", "switching", "transition",
      "not qualified", "under-qualified"], "gaps_and_shifts"),
    (["multiple", "another job", "second job", "reuse", "re-use",
      "apply again", "next application", "different job",
      "more than one", "several", "batch"], "multiple_applications"),
    (["format", "output format", "docx", "word doc", "pdf",
      "plain text", ".txt", "export", "file type",
      "ats safe", "ats-safe", "ats friendly"], "output_formats"),
    (["folder", "structure", "layout", "directory", "directories",
      "workspace", "organis", "organiz", "setup"], "folder_structure"),
    (["type", "kind", "profile", "which resume", "what resume",
      "non_tech", "non-tech", "hybrid", "executive", "kinds of"], "resume_types"),
    (["name", "naming", "filename", "file name", "rename",
      "what to call", "title", "how should i name"], "file_naming"),
    (["workflow", "step", "process", "order", "sequence",
      "start", "begin", "how to use", "how do i use",
      "prepare"], "workflow"),
    (["tag", "verified", "inferred", "stretch", "user-verify",
      "user_verify", "claim", "provenance", "label"], "verification_tags"),
    (["tool", "analyze_jd", "map_resume",
      "draft_resume", "finalize", "faq", "available"], "tools"),
    (["polic", "rule", "block", "p0", "p1", "p2", "p3", "p4",
      "truth", "ats", "fabricat", "enforc"], "policies"),
]


def _detect_topic(question: str) -> str:
    """Return the best-matching KB topic key for *question*.

    Iterates ``_ROUTING`` keyword lists and returns the first match,
    or ``"general"`` when no keyword matches.
    """
    q = question.lower()
    for keywords, topic in _ROUTING:
        if any(kw in q for kw in keywords):
            return topic
    return "general"


def _build_workspace_setup() -> dict[str, Any]:
    """Construct a workspace-setup dict with an embedded README."""
    setup = build_full_workspace_setup()
    setup["readme_content"] = _README_CONTENT
    return setup


# ---------------------------------------------------------------------------
# Tool handler
# ---------------------------------------------------------------------------

def answer_faq(
    question: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Answer common questions about the MCP resume server.

    Routes the question to a built-in knowledge base by keyword
    matching.  For workspace/folder-related topics the response
    includes a ``workspace_setup`` object with full directory
    structure and optional template file content.

    Args:
        question: Free-text question from the user.
        context: Optional dict of extra context from the calling LLM.

    Returns:
        Tool response dict with ``answer``, ``topic``,
        ``related_topics``, and optional ``workspace_setup``.
    """
    payload: dict[str, Any] = {"question": question}
    if context:
        payload["context"] = context

    try:
        session_state.contracts.validate_input("faq", payload)
    except ContractValidationError as exc:
        return {"status": "error", "error": str(exc)}

    topic = _detect_topic(question)
    kb_entry = _KB.get(topic)

    if kb_entry:
        answer = kb_entry["answer"]
        related: list[str] = kb_entry["related_topics"]
        include_workspace: bool = kb_entry["include_workspace"]
        include_templates: bool = kb_entry.get("include_templates", False)
    else:
        answer = (
            "I can answer questions about: getting started, writing your master "
            "profile, folder structure, resume types, file naming, workflow steps, "
            "individual tools, handling gaps and career changes, applying to "
            "multiple jobs, output formats, verification tags, and policy rules. "
            "Try rephrasing your question using one of those topics."
        )
        related = list(_KB.keys())
        include_workspace = False
        include_templates = False

    ws = _build_workspace_setup() if include_workspace else None

    # Inject template file content when requested (getting_started, master_profile)
    if include_templates:
        if ws is None:
            ws = {"template_content": {}}
        ws["template_content"] = ws.get("template_content", {})
        master_tpl = _read_template("master-profile-template.md")
        if master_tpl:
            ws["template_content"]["source/master-profile.md"] = master_tpl
        jd_tpl = _read_template("jd-template.md")
        if jd_tpl:
            ws["template_content"]["job-descriptions/template.md"] = jd_tpl
        resume_tpl = _read_template("resume-source-template.md")
        if resume_tpl:
            ws["template_content"]["source/resume-source-template.md"] = resume_tpl

    result: dict[str, Any] = {
        "answer": answer,
        "topic": topic,
        "related_topics": related,
        "workspace_setup": ws,
        "interactive": {
            "questions": [],
            "suggestions": [
                f"Related topics you may also want to explore: {', '.join(related)}."
            ],
            "verification_needed": [],
        },
    }

    log_event("tool_call", "faq", payload)
    return session_state.finalize_tool_response("faq", payload, result)


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------

TOOL_DEF = {
    "name": "faq",
    "description": (
        "Answer common questions about using the MCP resume server.\n\n"
        "Topics covered: getting started / how to build a resume, "
        "workspace folder layout, resume types "
        "(tech / non_tech / hybrid / executive), file naming conventions, "
        "the 4-step workflow, what each tool does, "
        "verification tags (VERIFIED / INFERRED / STRETCH / USER-VERIFY), "
        "and policy rules (P0–P4).\n\n"
        "When asked 'how to build a resume' or 'getting started', the response "
        "includes step-by-step preparation guidance, the workspace folder "
        "structure, and template file contents so the client can create the "
        "workspace and seed files for the user.\n\n"
        "When asked about folder structure or workspace setup, the response "
        "includes a workspace_setup object with agent_instructions that "
        "specify the EXACT folder layout to create — the client agent must "
        "follow these instructions and not invent alternative structures.\n\n"
        "Args:\n"
        "    question: The question to answer "
        "(e.g. 'How do I build a resume?', "
        "'What folder structure works best?', "
        "'What types of resumes can be built?', "
        "'How should I name my files?').\n"
        "    context:  Optional extra hints "
        "(e.g. {'resume_type': 'tech', 'profile': 'hybrid'})."
    ),
    "parameters": {
        "question": {"type": "str", "required": True},
        "context": {"type": "dict", "required": False, "default": None},
    },
    "handler": answer_faq,
}
