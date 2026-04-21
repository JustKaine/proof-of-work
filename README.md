# Proof of Work

A policy-driven [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server that helps AI agents generate **truthful, ATS-optimized, tailored resumes**. Every claim is tagged with provenance, validated against JSON Schema contracts, evaluated by a 6-tier policy engine, and logged for audit so nothing is fabricated.

![Python 3.12](https://img.shields.io/badge/python-3.12-blue)
![MCP](https://img.shields.io/badge/protocol-MCP-green)
![Docker](https://img.shields.io/badge/docker-ready-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-yellow)

---

## Features

- **7 MCP tools** — Full workflow from JD analysis to resume mapping, draft generation, and finalization
- **6-tier policy engine (P0–P5)** — Truth safety, verification gates, workflow ordering, quality enforcement, ATS formatting, and user data isolation
- **Claim provenance tags** — Every resume bullet is tagged `[VERIFIED]`, `[INFERRED]`, `[STRETCH]`, or `[USER-VERIFY]`
- **JSON Schema contract validation** — All tool inputs and outputs validated against declared schemas
- **Per-user skill profiles** — Persistent supplemental skills injected as evidence during mapping/drafting
- **Structured audit logging** — JSON-lines log of every policy evaluation and tool invocation
- **Interactive questions** — Tools surface follow-up questions, suggestions, and verification prompts
- **Dynamic tool loading** — Drop custom `.py` tools into the tools directory at runtime

---

## Quick Start

### Docker Compose (recommended)

```bash
git clone https://github.com/JustKaine/proof-of-work.git
cd proof-of-work
docker compose -f docker/docker-compose.yml up --build -d
```

The server starts on **port 5359** by default with Streamable HTTP transport.
Set `MCP_PORT` to override:

```bash
MCP_PORT=8080 docker compose -f docker/docker-compose.yml up --build -d
```

Connect any MCP-compatible client to `http://localhost:${MCP_PORT:-5359}/mcp`.

### Local Python

```bash
git clone https://github.com/JustKaine/proof-of-work.git
cd proof-of-work
python -m venv venv && source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python server.py
```

> **Note:** Local mode uses `/data/` for logs and user data by default. Set environment variables (see [Configuration](#configuration)) to override paths.

### Connecting from VS Code (GitHub Copilot)

Once the server is running, add it as an MCP server in VS Code:

1. Open the Command Palette (`Ctrl+Shift+P`) → **MCP: Add Server…**
2. Choose **HTTP (Streamable HTTP)** as the transport type.
3. Enter the server URL: `http://localhost:5359/mcp`
4. Give it a name (e.g. `proof-of-work`) and choose where to save (`User settings` for all workspaces, or `Workspace settings` for this project only).

This creates an entry in your `settings.json`:

```jsonc
// .vscode/settings.json (workspace) or User settings.json
{
  "mcp": {
    "servers": {
      "proof-of-work": {
        "type": "http",
        "url": "http://localhost:5359/mcp"
      }
    }
  }
}
```

After adding, VS Code will show a **Start** button next to the server entry. Click it to connect. The server's 7 tools will then be available to Copilot in Agent mode — open Copilot Chat, switch to **Agent**, and the tools appear automatically.

> **Tip:** You can also create an `.vscode/mcp.json` file in your project root as an alternative to `settings.json`. This is useful for sharing the MCP config with collaborators:
>
> ```json
> {
>   "servers": {
>     "proof-of-work": {
>       "type": "http",
>       "url": "http://localhost:5359/mcp"
>     }
>   }
> }
> ```

---

## Architecture

```text
┌──────────────┐    MCP/HTTP      ┌────────────────────────────────────────┐
│  MCP Client  │ ◄──────────────► │  server.py (FastMCP)                   │
│  (AI Agent)  │                  │                                        │
└──────────────┘                  │  ┌──────────┐   ┌──────────────────┐   │
                                  │  │ tools/*  │──►│ engine/session   │   │
                                  │  │ (7 tools)│   │  ├─ policy_check │   │
                                  │  └──────────┘   │  ├─ contracts    │   │
                                  │                 │  ├─ audit        │   │
                                  │  ┌──────────┐   │  └─ policy_engine│   │
                                  │  │helpers/* │   └──────────────────┘   │
                                  │  │naming    │                          │
                                  │  │questions │   ┌──────────────────┐   │
                                  │  │user_store│   │ policies/        │   │
                                  │  └──────────┘   │  rules + schemas │   │
                                  │                 └──────────────────┘   │
                                  └────────────────────────────────────────┘
```

**Request flow:** Client calls tool via MCP → Tool validates input (contracts) → Tool builds response scaffold → `engine.session.finalize_tool_response()` runs policy evaluation → Audit event logged → Result returned (or blocked with reasons).

---

## Tools

| Tool | Purpose | Workflow Step |
| ---- | ------- | ------------- |
| `analyze_jd` | Extract and prioritize requirements from 1–3 job descriptions | 1 |
| `map_resume` | Map resume evidence to JD requirements with confidence scores | 2 |
| `draft_resume` | Generate tagged draft with provenance labels and verification questions | 3 |
| `finalize` | Produce final resume after all verification items are resolved | 4 |
| `identify_user` | Set user identity for persistent skill profiles | Setup |
| `manage_skills` | Add, list, or remove supplemental skills in user profile | Setup |
| `faq` | Answer questions about workflow, folder layout, policies, etc. | Anytime |

See [tools/README.md](tools/README.md) for detailed documentation on each tool.

---

## How To Use

The main README is intentionally focused on building, running, and integrating the server.

For the day-to-day user workflow, see [USE_README.md](USE_README.md). That guide covers:

- Resume workspace layout
- Job description file guidance, including `.txt` and `.md` examples
- Tool order and example prompts
- Verification flow and user instructions
- HTML page-break usage for formatted output

See [templates/README.md](templates/README.md) for the template files that seed the workspace.

---

## Configuration

All paths are configurable via environment variables:

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `POLICY_PACK_PATH` | `/app/policies/policy-rules.yaml` | Path to policy rules YAML |
| `CONTRACTS_PATH` | `/app/policies/tool-contracts.json` | Path to JSON Schema contracts |
| `AUDIT_LOG_PATH` | `/data/logs/audit.jsonl` | Path to audit log file |
| `LOG_DIR` | `/data/logs` | Directory for server logs |
| `TOOLS_DIR` | `/data/tools` | Directory to scan for tool plugins |
| `USERS_DIR` | `/data/users` | Per-user data storage root |
| `MCP_PORT` | `5359` | HTTP port used by the MCP server |

---

## Policy Engine

Six policy tiers enforce resume quality, truthfulness, and user-scope safety:

| Rule | Name | Effect |
| ---- | ---- | ------ |
| **P0** | Truth Safety | No fabrication — every claim must carry a provenance tag |
| **P1** | Verification Gate | `finalize` blocked while unresolved `[USER-VERIFY]` items exist |
| **P2** | Workflow Order | `analyze_jd` must run before `finalize`; domain-shift alerting |
| **P3** | Quality | Action + Context + Result bullet format; seniority alignment |
| **P4** | ATS Format | No markdown tables/images in final output; sections match profile |
| **P5** | User Data Isolation | User-scoped data and profile evidence protections |

See [policies/README.md](policies/README.md) for the full rule specification.

---

## Project Structure

```text
proof-of-work/
├── server.py                    ← Entry point — MCP bootstrap + tool loader
├── entrypoint.sh                ← Docker container bootstrap script
├── requirements.txt             ← Python dependencies
├── LICENSE                      ← MIT license
│
├── engine/                      ← Core infrastructure (policy, contracts, session, audit)
│   ├── __init__.py
│   ├── audit.py                 ← JSON-lines audit logger
│   ├── contracts.py             ← JSON Schema contract validation
│   ├── policy_engine.py         ← P0–P4 policy rule evaluation
│   └── session.py               ← Per-user session state + policy enforcement hub
│
├── helpers/                     ← Utilities consumed by tools
│   ├── __init__.py
│   ├── naming.py                ← Workspace paths, filenames, and directory setup
│   ├── questions.py             ← Interactive question generation
│   └── user_store.py            ← Per-user data persistence (skills, prefs, history)
│
├── tools/                       ← MCP tool plugins (dynamically loaded)
│   ├── analyze_jd.py
│   ├── draft_resume.py
│   ├── faq.py
│   ├── finalize.py
│   ├── identify_user.py
│   ├── manage_skills.py
│   └── map_resume.py
│
├── policies/                    ← Policy rules + JSON Schema contracts
│   ├── policy-rules.yaml
│   └── tool-contracts.json
│
├── templates/                   ← User-facing markdown templates
│   ├── jd-template.md
│   ├── master-profile-template.md
│   └── resume-source-template.md
│
└── docker/                      ← Docker deployment files
    ├── Dockerfile
    ├── docker-compose.yml
    └── healthcheck.sh
```

---

## License

This project is licensed under the [MIT License](LICENSE).

## About the Name

**Proof of Work** — borrowed from crypto, repurposed for resumes. In blockchain, proof-of-work means you burned real compute to earn a token. Here, it means every bullet on your resume is backed by real evidence to earn its place. The server will not let a claim through without provenance: no fabrication, no embellishment, just proof.

---

## Example FAQ Questions

- "How do I build a resume?" (returns step-by-step guide with templates)
- "How do I get started?" (same — workspace setup + preparation steps 1 & 2)
- "What should I put in my master profile?" (content guidance, ACR bullet format)
- "What if I'm missing requirements?" (gap strategies, transferable skills)
- "I'm changing careers" (domain shift handling, cross-domain framing)
- "Can I reuse my profile for multiple jobs?" (multi-application workflow)
- "What output format should I use?" (md, txt, docx, pdf + ATS guidance)
- "What folder structure works best to create resumes with this MCP?"
- "What types of resumes can be built?"
- "How should I name the files I want to use?"
- "What does each tool do?"
- "What policy rules can block finalization?"

For workspace layout, example prompts, job description file guidance, user instructions, and output-formatting notes, see [USE_README.md](USE_README.md).
