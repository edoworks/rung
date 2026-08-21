"""Cited sources for Rung governance checks.

Each source is classified by authority level. Rung is "informed by"
standards and industry practices, not every check is directly derived
from a standard.
"""

from rung.models import SourceClass

SOURCES = {
    "agents_md": {
        "name": "agents.md (Linux Foundation / AAIF)",
        "url": "https://agents.md",
        "note": "Cross-vendor agent policy spec, adopted by 60k+ repos. "
                "Defines AGENTS.md as the de-facto agent instruction file.",
        "classification": SourceClass.STANDARD,
    },
    "github_copilot": {
        "name": "GitHub Copilot repository custom instructions",
        "url": "https://docs.github.com/en/copilot/customizing-copilot/adding-repository-custom-instructions-for-github-copilot",
        "note": "Official GitHub docs for .github/copilot-instructions.md and "
                "AGENTS.md precedence (nearest file in directory tree wins).",
        "classification": SourceClass.PLATFORM_CONTROL,
    },
    "nist_rmf": {
        "name": "NIST AI Risk Management Framework 1.0",
        "url": "https://nist.gov/itl/ai-risk-management-framework",
        "note": "US government framework. Four functions: Govern, Map, "
                "Measure, Manage. Voluntary but widely adopted.",
        "classification": SourceClass.STANDARD,
    },
    "anthropic_multiagent": {
        "name": "Anthropic — How we built our multi-agent research system",
        "url": "https://www.anthropic.com/engineering/multi-agent-research-system",
        "note": "Production guidance on agent evaluation: LLM-as-judge rubrics, "
                "end-state evaluation, durable execution, checkpointing.",
        "classification": SourceClass.VENDOR_GUIDANCE,
    },
    "openai_codex": {
        "name": "openai/codex AGENTS.md (exemplar)",
        "url": "https://github.com/openai/codex/blob/main/AGENTS.md",
        "note": "322-line root AGENTS.md with 500/800 LoC thresholds, "
                "change-size guidance, mandatory integration tests.",
        "classification": SourceClass.EXEMPLAR,
    },
    "apache_airflow": {
        "name": "apache/airflow AGENTS.md (exemplar)",
        "url": "https://github.com/apache/airflow/blob/main/AGENTS.md",
        "note": "522-line AGENTS.md with Generated-by attribution, "
                "Drafted-by footer, Never-rules, apache-magpie framework.",
        "classification": SourceClass.EXEMPLAR,
    },
    "ibm_adlc": {
        "name": "IBM — Agent Development Lifecycle",
        "url": "https://www.ibm.com/think/topics/agent-development-lifecycle-adlc",
        "note": "Trace layer concept: every AI agent needs an action "
                "accountability trace.",
        "classification": SourceClass.VENDOR_GUIDANCE,
    },
    "slsa": {
        "name": "SLSA v1.2 (Supply-chain Levels for Software Artifacts)",
        "url": "https://slsa.dev/spec/v1.2/",
        "note": "OpenSSF standard for build provenance. Applies to "
                "agent-produced artifacts.",
        "classification": SourceClass.STANDARD,
    },
    "iso_42001": {
        "name": "ISO/IEC 42001:2023 — AI management system standard",
        "url": "https://www.iso.org/standard/83730.html",
        "note": "Certifiable AI Management System standard. Plan-do-check-act "
                "for AI.",
        "classification": SourceClass.STANDARD,
    },
    "github_branch_protection": {
        "name": "GitHub REST API — Branch Protection",
        "url": "https://docs.github.com/en/rest/branches/branch-protection",
        "note": "Branch protection settings require Administration read "
                "permission even for read operations on public repos.",
        "classification": SourceClass.PLATFORM_CONTROL,
    },
    "openssf_scorecard": {
        "name": "OpenSSF Scorecard",
        "url": "https://scorecard.dev/",
        "note": "Each check explains its risk, scoring logic, evidence, "
                "remediation, and limitations. Model for Rung's check format.",
        "classification": SourceClass.INDUSTRY_PRACTICE,
    },
}

SOURCE_EXTENSIONS = {".py", ".swift", ".gd", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".kt", ".rb"}
IGNORED_PARTS = {".git", "build", "dist", "node_modules", "DerivedData", ".venv", "venv", ".build", "Pods", "target", "__pycache__"}

WATCH_LOC = 500
SMELL_LOC = 800
DEFECT_LOC = 1200