import re
import uuid
import json
import asyncio
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
from sqlalchemy import select

from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.utils.function_calling import convert_to_openai_tool

from app.core.config import settings
from app.services.github import github_service
from app.services.scoring import calculate_pr_risk
from app.db.models import User, Review, ReviewIssue, ReviewComment, ReviewStatus, ReviewSummary, PullRequest, Repository, SeverityLevel, IssueCategory, CommentStatus

# --- 1. Token Optimization Diff Parsers ---

def should_analyze_file(file_path: str) -> bool:
    """Ignore binaries, generated, lock files, and minified scripts to optimize token budget."""
    exclude_patterns = [
        # Lock files
        "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "poetry.lock", "go.sum", "Cargo.lock",
        # Binaries/Images
        ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".tar.gz", ".tar",
        # Generated files / Caches
        "node_modules/", ".next/", "dist/", "build/", ".pyc", ".git/", "venv/", ".venv/",
        # Minified files
        ".min.js", ".min.css"
    ]
    for pattern in exclude_patterns:
        if pattern in file_path or file_path.endswith(pattern):
            return False
    return True

def parse_diff_to_changed_lines(diff_text: str) -> Dict[str, List[int]]:
    """Parse raw unified diff text to identify added/modified line numbers for each file."""
    changed_files = {}
    current_file = None
    current_line = 0
    
    lines = diff_text.splitlines()
    for line in lines:
        # Check for target file path (destination file)
        if line.startswith("+++ b/"):
            current_file = line[6:]
            changed_files[current_file] = []
            current_line = 0
            continue
        elif line.startswith("--- a/"):
            # Source file header line
            continue
            
        # Check for diff hunk headers
        if line.startswith("@@"):
            match = re.search(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if match:
                current_line = int(match.group(1))
            continue
            
        if current_file:
            if line.startswith("+"):
                # If it's a file header prefix like +++ b/ skip it
                if line.startswith("+++"):
                    continue
                changed_files[current_file].append(current_line)
                current_line += 1
            elif line.startswith("-"):
                # Deleted line, does not increment destination line counter
                continue
            else:
                # Unchanged context line
                current_line += 1
                
    # Filter files based on exclusions
    return {k: v for k, v in changed_files.items() if should_analyze_file(k) and len(v) > 0}

# --- 2. Pydantic Models for Structured AI Output ---

class ReviewIssueModel(BaseModel):
    file_path: str = Field(description="The path of the file containing the issue.")
    line_number: int = Field(description="The line number of the issue (1-indexed).")
    issue_type: str = Field(description="The category: BUG, SECURITY, PERFORMANCE, CODE_QUALITY, TEST.")
    severity: str = Field(description="The severity level: LOW, MEDIUM, HIGH, CRITICAL.")
    message: str = Field(description="Detailed explanation of the issue, standard breached, and risk description.")
    suggestion: Optional[str] = Field(None, description="Clear code suggestion block showing how to correct the issue.")
    context_diff: Optional[str] = Field(None, description="The specific code block snippet where the issue resides.")

class ReviewReportModel(BaseModel):
    risk_score: int = Field(description="Overall risk score for the pull request, between 0 and 100.")
    severity: str = Field(description="Overall PR severity level: LOW, MEDIUM, HIGH, CRITICAL.")
    summary: str = Field(description="Detailed markdown report summarizing findings, major issues, and clean code score.")
    issues: List[ReviewIssueModel] = Field(default=[], description="List of specific code issues identified in the diff.")

# --- 3. LangChain Agent Tools Wiring ---

@tool
def get_file_content_tool(owner: str, repo: str, path: str, ref: str, token: str) -> str:
    """Fetch the contents of a specific file in the repository to provide code context."""
    # Running async loop in sync tool block
    return asyncio.run(github_service.fetch_file_content(owner, repo, path, ref, token))

@tool
def search_repository_tool(owner: str, repo: str, query: str, token: str) -> str:
    """Search code files in the repository for specific patterns or symbols."""
    res = asyncio.run(github_service.search_repository(owner, repo, query, token))
    return json.dumps(res, indent=2)

@tool
def get_related_files_tool(owner: str, repo: str, path: str, ref: str, token: str) -> str:
    """Examine imports in a file to return potential related context workspace files."""
    res = asyncio.run(github_service.get_related_files(owner, repo, path, ref, token))
    return json.dumps(res, indent=2)

# --- 4. Agent Execution Loop & Mock Fallback ---

def _find_exact_line(pattern: str, added_lines_with_numbers: List[tuple]) -> tuple:
    """Returns (file_path, line_number, matching_line_text) for the first added line matching pattern."""
    for file_path, line_num, line_text in added_lines_with_numbers:
        if re.search(pattern, line_text.lower()):
            return file_path, line_num, line_text.strip()
    return None, None, None

def _build_added_lines_index(diff_text: str) -> List[tuple]:
    """
    Returns list of (file_path, line_number, line_text) for every added line in the diff.
    line_number is the actual destination file line number from the @@ hunk header.
    """
    result = []
    current_file = None
    current_line = 0
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:]
            current_line = 0
        elif line.startswith("--- a/"):
            continue
        elif line.startswith("@@"):
            m = re.search(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if m:
                current_line = int(m.group(1))
        elif current_file:
            if line.startswith("+") and not line.startswith("+++"):
                result.append((current_file, current_line, line[1:]))
                current_line += 1
            elif not line.startswith("-"):
                current_line += 1
    return result

def _fix_for(pattern: str, buggy_line: str, file_path: str) -> Optional[str]:
    """Generate a language-aware fixed code snippet for a known bug pattern."""
    ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
    stripped = buggy_line.strip()
    indent = " " * (len(buggy_line) - len(buggy_line.lstrip()))

    # Security fixes
    if re.search(r'password\s*=\s*["\']', pattern) or re.search(r'password\s*=\s*["\']', stripped.lower()):
        if ext == "cs":
            return f'{indent}string password = Environment.GetEnvironmentVariable("DB_PASSWORD");\nif (string.IsNullOrEmpty(password)) throw new InvalidOperationException("Missing DB_PASSWORD env variable");'
        return f'{indent}password = os.getenv("DB_PASSWORD")\nif not password:\n{indent}    raise EnvironmentError("Missing DB_PASSWORD environment variable")'
    if re.search(r'api_key\s*=\s*["\']', stripped.lower()):
        return f'{indent}api_key = os.getenv("API_KEY")\nif not api_key:\n{indent}    raise EnvironmentError("Missing API_KEY environment variable")'
    if re.search(r'secret\s*=\s*["\']', stripped.lower()):
        return f'{indent}secret = os.getenv("SECRET_KEY")\nif not secret:\n{indent}    raise EnvironmentError("Missing SECRET_KEY environment variable")'
    if re.search(r'token\s*=\s*["\']', stripped.lower()):
        return f'{indent}token = os.getenv("ACCESS_TOKEN")\nif not token:\n{indent}    raise EnvironmentError("Missing ACCESS_TOKEN environment variable")'

    # C# fixes
    if ext == "cs":
        if re.search(r'i\s*<=\s*\w+\s*;\s*i\+\+', stripped.lower()):
            fixed = re.sub(r'<=', '<', stripped)
            return f'{indent}{fixed}  // Fixed: changed <= to < to prevent off-by-one error'
        if re.search(r'convert\.toint32|int\.parse\b', stripped.lower()):
            # Extract the variable name being assigned to, if any
            m = re.match(r'\s*(\w+)\s*\w+\s*=\s*(?:Convert\.ToInt32|int\.Parse)\s*\((.*)\)', stripped, re.IGNORECASE)
            if m:
                varname, arg = m.group(1), m.group(2)
                return (f'{indent}if (!int.TryParse({arg}, out int {varname}))\n'
                        f'{indent}{{\n'
                        f'{indent}    Console.WriteLine("Invalid input — please enter a valid integer.");\n'
                        f'{indent}    return;\n'
                        f'{indent}}}')
            return f'{indent}// Use int.TryParse instead:\n{indent}if (!int.TryParse(input, out int result))\n{indent}{{\n{indent}    Console.WriteLine("Invalid number");\n{indent}    return;\n{indent}}}'
        if re.search(r'console\.readline\(\)', stripped.lower()):
            return (f'{indent}string? input = Console.ReadLine();\n'
                    f'{indent}if (input == null) {{ Console.WriteLine("No input provided."); return; }}')
        if re.search(r'\w+\s*/\s*\w+', stripped) and ext == "cs":
            # Extract denominator
            m = re.search(r'/\s*(\w+)', stripped)
            denom = m.group(1) if m else "b"
            return (f'{indent}if ({denom} == 0)\n'
                    f'{indent}{{\n'
                    f'{indent}    Console.WriteLine("Error: Cannot divide by zero.");\n'
                    f'{indent}    return;\n'
                    f'{indent}}}\n'
                    f'{indent}{stripped}  // safe — zero-check added above')

    # Python fixes
    if re.search(r'except\s*:', stripped.lower()):
        return f'{indent}except (ValueError, TypeError) as e:\n{indent}    logger.error("Caught error: %s", e)\n{indent}    raise'
    if re.search(r'except\s+exception', stripped.lower()):
        return f'{indent}except (ValueError, KeyError, RuntimeError) as e:\n{indent}    logger.error("Unexpected error: %s", e)\n{indent}    raise'
    if re.search(r'==\s*none\b', stripped.lower()):
        fixed = re.sub(r'==\s*None', 'is None', stripped, flags=re.IGNORECASE)
        return f'{indent}{fixed}'
    if re.search(r'!=\s*none\b', stripped.lower()):
        fixed = re.sub(r'!=\s*None', 'is not None', stripped, flags=re.IGNORECASE)
        return f'{indent}{fixed}'
    if re.search(r'\w+\s*/\s*\w+', stripped):
        m = re.search(r'/\s*(\w+)', stripped)
        denom = m.group(1) if m else "divisor"
        return f'{indent}if {denom} == 0:\n{indent}    raise ValueError(f"Division by zero: {{{denom}}} cannot be zero")\n{indent}{stripped}  # safe'

    # JS/TS fixes
    if re.search(r'var\s+\w+', stripped.lower()):
        fixed = re.sub(r'\bvar\b', 'const', stripped)
        return f'{indent}{fixed}  // Use const (or let if reassigned)'
    if re.search(r'console\.log\s*\(', stripped.lower()):
        return f'{indent}// Removed debug log — use a proper logger:\n{indent}// logger.debug({stripped[stripped.find("(")+1:stripped.rfind(")")]})'

    return None  # No specific fix available

def generate_mock_review(diff_text: str, changed_lines: Dict[str, List[int]], guidelines_context: str = "") -> ReviewReportModel:
    """
    Rule-based static analysis reviewer for mock/local mode.
    Scans the actual diff content for common bug patterns with exact line numbers and fix suggestions.
    """
    issues = []

    # Build an indexed list of (file_path, actual_line_number, line_text) for added lines only
    added_index = _build_added_lines_index(diff_text)
    added_text  = "\n".join(t for _, _, t in added_index)
    added_lower = added_text.lower()

    has_test_file = any("test" in f.lower() for f in changed_lines.keys())

    def first_file_and_line():
        for fp, lines in changed_lines.items():
            return fp, lines[0] if lines else 1
        return "unknown", 1

    # ── ALL PATTERNS (security + bug + performance) ────────────────────
    all_patterns = [
        # type, pattern, message, severity
        # SECURITY
        ("SECURITY", r'password\s*=\s*["\'][^"\']{3,}["\']',  "Hardcoded password literal — store in environment variables, never in source code.", "CRITICAL"),
        ("SECURITY", r'secret\s*=\s*["\'][^"\']{3,}["\']',    "Hardcoded secret value — use environment variable or secrets manager.", "CRITICAL"),
        ("SECURITY", r'api_key\s*=\s*["\'][^"\']{3,}["\']',   "Hardcoded API key — rotate the key and move it to an environment variable immediately.", "CRITICAL"),
        ("SECURITY", r'token\s*=\s*["\'][^"\']{3,}["\']',     "Hardcoded token — store tokens in environment variables, not source code.", "HIGH"),
        ("SECURITY", r'private_key\s*=\s*["\']',              "Hardcoded private key detected — never commit private keys to source control.", "CRITICAL"),
        ("SECURITY", r'eval\s*\(',                             "eval() executes arbitrary code — remove it and use safe alternatives.", "HIGH"),
        ("SECURITY", r'shell\s*=\s*true',                      "shell=True in subprocess allows shell injection — set shell=False and pass args as a list.", "HIGH"),
        ("SECURITY", r'verify\s*=\s*false',                    "SSL verification disabled — remove verify=False to prevent MITM attacks.", "HIGH"),
        ("SECURITY", r'sql\s*=.*\+.*input|query\s*=.*\+',     "SQL string concatenation with user input — use parameterized queries to prevent SQL injection.", "CRITICAL"),
        ("SECURITY", r'md5\s*\(',                              "MD5 is cryptographically broken — use hashlib.sha256() instead.", "MEDIUM"),
        ("SECURITY", r'http://',                               "Plain HTTP URL — switch to HTTPS to encrypt data in transit.", "MEDIUM"),
        # BUGS — Python
        ("BUG", r'except\s*:',                                 "Bare except: swallows ALL exceptions including system signals. Catch specific exception types.", "HIGH"),
        ("BUG", r'except\s+exception\s*:',                     "Catching base Exception hides real errors. Use specific exception types (e.g. ValueError, IOError).", "HIGH"),
        ("BUG", r'==\s*none\b',                                "Use 'is None' instead of '== None' for identity comparison (PEP 8).", "LOW"),
        ("BUG", r'!=\s*none\b',                                "Use 'is not None' instead of '!= None' for identity comparison (PEP 8).", "LOW"),
        ("BUG", r'while\s+true\s*:(?!.*break)',                "Infinite while True loop with no break statement — potential infinite loop / hang.", "HIGH"),
        ("BUG", r'\[\s*\]\s*\*\s*\d+',                        "Mutable list created with * — all sub-lists share the same reference causing unexpected mutations.", "HIGH"),
        ("BUG", r'open\s*\([^)]+\)(?!\s*as\b)(?!.*with)',     "File opened outside a 'with' block — file handle may not close on exception.", "MEDIUM"),
        ("BUG", r'requests\.get\s*\([^)]*\)(?!.*timeout)',    "HTTP request with no timeout — connection can hang indefinitely.", "MEDIUM"),
        ("BUG", r'pickle\.loads?\s*\(',                       "pickle.loads() on untrusted data allows arbitrary code execution.", "CRITICAL"),
        # BUGS — C#
        ("BUG", r'i\s*<=\s*\w+\s*;\s*i\+\+',                 "Off-by-one error: loop uses <= on a 0-based index. Change <= to < to avoid iterating one step too far.", "HIGH"),
        ("BUG", r'convert\.toint32|int\.parse\b',             "Convert.ToInt32 / int.Parse throws FormatException on non-numeric input. Use int.TryParse with a validity check.", "HIGH"),
        ("BUG", r'console\.readline\(\)',                      "Console.ReadLine() can return null. Add a null-check before parsing to prevent NullReferenceException.", "MEDIUM"),
        ("BUG", r'catch\s*\(\s*exception\b',                  "Catching base Exception type hides specific errors. Catch only the exceptions you expect.", "MEDIUM"),
        ("BUG", r'\.result\b',                                 ".Result blocks the thread synchronously and can deadlock in async contexts. Use await instead.", "HIGH"),
        ("BUG", r'goto\s+\w+',                                 "goto disrupts control flow and makes code hard to maintain. Use loops or structured exception handling.", "MEDIUM"),
        # BUGS — JS/TS
        ("BUG", r'\.then\s*\([^)]*\)(?![\s\S]{0,200}\.catch)', "Promise .then() has no .catch() handler — unhandled rejections are silently swallowed.", "HIGH"),
        ("BUG", r'dangerouslysetinnerhtml',                    "dangerouslySetInnerHTML with user content enables XSS attacks. Sanitize input before rendering.", "HIGH"),
        # BUGS — General (division by zero)
        ("BUG", r'\w+\s*/\s*\w+',                             "Division operation detected — ensure the divisor is never zero to prevent a runtime crash (DivideByZeroException / ZeroDivisionError).", "HIGH"),
        # PERFORMANCE
        ("PERFORMANCE", r'select\s+\*\s+from',                "SELECT * fetches all columns — specify only the columns you need to reduce I/O.", "MEDIUM"),
        ("PERFORMANCE", r'\.all\(\)(?!.*limit)',               "ORM .all() without .limit() may load the entire table into memory.", "MEDIUM"),
        ("PERFORMANCE", r'\+\s*["\'].*for.*in',               "String concatenation in a loop is O(n²) — use ''.join() instead.", "MEDIUM"),
        # CODE QUALITY
        ("CODE_QUALITY", r'print\s*\(',                        "Debug print() left in code — use the logging module for production output.", "LOW"),
        ("CODE_QUALITY", r'console\.log\s*\(',                 "console.log() left in code — remove debug statements before committing.", "LOW"),
        ("CODE_QUALITY", r'todo|fixme|hack\b',                 "TODO/FIXME/HACK marker found — unresolved technical debt in the changed lines.", "LOW"),
        ("CODE_QUALITY", r'var\s+\w+',                        "var declaration — use const (immutable) or let (reassignable) for clearer intent.", "LOW"),
    ]

    seen_keys: set = set()

    for issue_type, pattern, message, severity in all_patterns:
        fp, ln, matching_line = _find_exact_line(pattern, added_index)
        if fp is None:
            continue
        key = (fp, issue_type, severity)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        fix = _fix_for(pattern, matching_line, fp)

        issues.append(ReviewIssueModel(
            file_path=fp,
            line_number=ln,
            issue_type=issue_type,
            severity=severity,
            message=message,
            context_diff=matching_line,
            suggestion=fix,
        ))

    # ── CODE QUALITY: missing docstrings ──────────────────────────────
    for file_path, lines in changed_lines.items():
        if not lines:
            continue
        if re.search(r'def\s+\w+\s*\(|class\s+\w+', added_lower) and '"""' not in added_text and "'''" not in added_text:
            # Find the actual line of the first def/class
            fp2, ln2, ml2 = _find_exact_line(r'def\s+\w+|class\s+\w+', added_index)
            key = (fp2 or file_path, "CODE_QUALITY", "LOW")
            if key not in seen_keys:
                seen_keys.add(key)
                issues.append(ReviewIssueModel(
                    file_path=fp2 or file_path,
                    line_number=ln2 or lines[0],
                    issue_type="CODE_QUALITY",
                    severity="LOW",
                    message="Missing docstring: New function or class added without documentation.",
                    context_diff=ml2,
                    suggestion=(
                        'def your_function(param):\n'
                        '    """One-line summary.\n\n'
                        '    Args:\n'
                        '        param: Description.\n\n'
                        '    Returns:\n'
                        '        Description of return value.\n'
                        '    """\n'
                        '    pass'
                    ),
                ))
        break

    # ── TEST COVERAGE ─────────────────────────────────────────────────
    for file_path, lines in changed_lines.items():
        if "test" not in file_path.lower():
            if re.search(r'def\s+\w+|class\s+\w+|static\s+\w+\s+\w+\s*\(', added_lower) and not has_test_file:
                module_ref = file_path.replace('.py', '').replace('/', '.').replace('\\', '.')
                issues.append(ReviewIssueModel(
                    file_path=file_path,
                    line_number=1,
                    issue_type="TEST",
                    severity="MEDIUM",
                    message=f"No test file updated: new logic added to `{file_path}` has no corresponding unit tests.",
                    context_diff=None,
                    suggestion=(
                        "import pytest\n"
                        f"# from {module_ref} import YourClass\n\n"
                        "def test_happy_path():\n"
                        "    # Arrange\n"
                        "    expected = ...\n"
                        "    # Act\n"
                        "    result = ...  # call your function here\n"
                        "    # Assert\n"
                        "    assert result == expected\n\n"
                        "def test_edge_case_zero():\n"
                        "    # Test division by zero / boundary conditions\n"
                        "    with pytest.raises(ValueError):\n"
                        "        ...  # call with invalid input\n"
                    ),
                ))
        break

    # ── Calculate score ───────────────────────────────────────────────
    calculated_score, severity_label = calculate_pr_risk(issues, {"changed_lines": changed_lines})

    total_bugs    = sum(1 for i in issues if i.issue_type == "BUG")
    total_sec     = sum(1 for i in issues if i.issue_type == "SECURITY")
    total_perf    = sum(1 for i in issues if i.issue_type == "PERFORMANCE")
    total_tests   = sum(1 for i in issues if i.issue_type == "TEST")
    total_quality = sum(1 for i in issues if i.issue_type == "CODE_QUALITY")

    if not issues:
        summary_body = "No significant issues detected in this diff. Code looks clean! ✅"
    else:
        summary_body = (
            f"Reviewed **{len(changed_lines)} file(s)**. Found **{len(issues)} issue(s)**.\n\n"
            f"| Category | Count |\n|---|---|\n"
            f"| 🐛 Bugs | {total_bugs} |\n"
            f"| 🔐 Security | {total_sec} |\n"
            f"| ⚡ Performance | {total_perf} |\n"
            f"| 🧪 Test Coverage | {total_tests} |\n"
            f"| 📝 Code Quality | {total_quality} |\n\n"
            f"**Overall Risk Score**: `{calculated_score}/100` — **{severity_label}**"
        )

    summary = f"### ReviewPilot AI Report (Static Analysis Mode)\n\n{summary_body}"
    if guidelines_context and guidelines_context != "No relevant standards matched.":
        summary += f"\n\n---\n**Matched Guidelines**:\n{guidelines_context}"

    return ReviewReportModel(
        risk_score=calculated_score,
        severity=severity_label,
        summary=summary,
        issues=issues,
    )

async def run_ai_review(review_id: uuid.UUID, db_session):
    """Executes the complete LangChain agent review pipeline for a pull request."""
    # 1. Fetch review data and parent relationships
    query = select(Review).where(Review.id == review_id)
    result = await db_session.execute(query)
    review = result.scalar_one_or_none()
    if not review:
        return
        
    review.status = ReviewStatus.RUNNING
    await db_session.commit()
    
    try:
        # Load PullRequest and Repository details
        pr_query = select(PullRequest).where(PullRequest.id == review.pull_request_id)
        pr = (await db_session.execute(pr_query)).scalar_one()
        
        repo_query = select(Repository).where(Repository.id == pr.repository_id)
        repo = (await db_session.execute(repo_query)).scalar_one()
        
        # Decrypt OAuth access token
        from app.core.security import decrypt_token
        owner_query = select(User).where(User.id == repo.owner_id)
        owner_result = await db_session.execute(owner_query)
        owner = owner_result.scalar_one()
        token = decrypt_token(owner.encrypted_access_token)

        # 2. Fetch diff from GitHub API
        parts = repo.full_name.split("/")
        owner_name = parts[0]
        repo_name = parts[1]
        
        diff_text = await github_service.fetch_pr_diff(owner_name, repo_name, pr.pr_number, token)
        changed_lines = parse_diff_to_changed_lines(diff_text)
        
        if not changed_lines:
            # No files requiring review (e.g. only lock files modified)
            review.status = ReviewStatus.COMPLETED
            review.risk_score = 0
            review.severity = SeverityLevel.LOW
            review.summary = "No files found requiring AI analysis. Review skipped."
            review.completed_at = datetime.utcnow()
            
            # Save empty summary
            summary_rep = ReviewSummary(
                review_id=review.id,
                markdown_summary=review.summary,
                total_bugs=0,
                total_security_flaws=0,
                total_perf_issues=0
            )
            db_session.add(summary_rep)
            await db_session.commit()
            return

        # Retrieve semantically relevant coding guidelines from Qdrant Vector DB (RAG)
        from app.services.rag import rag_service
        retrieved_rules = await rag_service.retrieve_relevant_guidelines(diff_text, limit=3)
        rules_context = "\n".join([f"- {rule}" for rule in retrieved_rules]) if retrieved_rules else "No relevant standards matched."

        # 3. AI analysis processing
        if settings.GROQ_API_KEY.startswith("mock_"):
            report = generate_mock_review(diff_text, changed_lines, rules_context)
        else:
            # Initialize Groq LLM
            llm = ChatGroq(
                groq_api_key=settings.GROQ_API_KEY,
                model_name=settings.GROQ_MODEL,
                temperature=0.1
            )
            
            # Enforce structured output parsing matching our schema
            structured_llm = llm.with_structured_output(ReviewReportModel)
            
            # System prompt configuration
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", (
                    "You are a Senior AI Code Reviewer analyzing a Git Pull Request diff.\n"
                    "Focus only on lines changed, which are provided below.\n"
                    "Analyze for:\n"
                    "- Bugs (null pointers, logic flaws)\n"
                    "- Security (OWASP Top 10, SQL Injection, hardcoded secrets)\n"
                    "- Code Quality (SOLID, duplicates, readability)\n"
                    "- Performance (loops, database connection optimization)\n"
                    "- Tests (missing coverages, unit test code suggestions)\n\n"
                    "For any BUG, SECURITY, or PERFORMANCE issue, you MUST populate the 'suggestion' field with a complete, safe, and refactored code block showing how to correct the issue. Do NOT use placeholder comments, abbreviations, or ellipses like '// ...' in your code suggestions. Provide fully functional code snippets.\n\n"
                    "If the diff introduces critical business code changes (new functions, classes, routes, or modules) but lacks corresponding test updates or new test files, you MUST create a new finding of type 'TEST' at line 1 of the affected file. The 'message' field should explain the missing test coverage, and the 'suggestion' field MUST contain the complete generated unit test suite code (e.g., using pytest for Python, Jest/Vitest for JavaScript/TypeScript).\n\n"
                    "Apply the following retrieved Architectural & Security Guidelines to your analysis when relevant:\n"
                    "{guidelines}\n\n"
                    "Return a strictly structured output conforming to the schema."
                )),
                ("user", (
                    "Repository: {owner}/{repo}\n"
                    "Pull Request: #{pr_number}\n"
                    "Diff Lines Metadata:\n{metadata}\n\n"
                    "Raw Diff Text:\n{diff}"
                ))
            ])
            
            metadata_str = "\n".join([f"File: {f}, Modified Lines: {l}" for f, l in changed_lines.items()])
            
            # Invoke LLM chain
            chain = prompt_template | structured_llm
            report = await chain.ainvoke({
                "owner": owner_name,
                "repo": repo_name,
                "pr_number": pr.pr_number,
                "metadata": metadata_str,
                "diff": diff_text[:12000], # Trim diff text to fit context window safely
                "guidelines": rules_context
            })

        # 4. Save review results into PostgreSQL
        calculated_score, calculated_severity = calculate_pr_risk(report.issues, {"changed_lines": changed_lines})
        
        review.risk_score = calculated_score
        
        # Map overall severity string to Enum
        try:
            review.severity = SeverityLevel(calculated_severity.upper())
        except Exception:
            review.severity = SeverityLevel.LOW
            
        review.summary = report.summary
        review.completed_at = datetime.utcnow()
        review.status = ReviewStatus.COMPLETED
        
        # Save issues
        bugs_count = 0
        sec_count = 0
        perf_count = 0
        
        for issue_model in report.issues:
            # Map issue type string to Enum
            try:
                category = IssueCategory(issue_model.issue_type.upper())
            except Exception:
                category = IssueCategory.CODE_QUALITY

            if category == IssueCategory.BUG:
                bugs_count += 1
            elif category == IssueCategory.SECURITY:
                sec_count += 1
            elif category == IssueCategory.PERFORMANCE:
                perf_count += 1

            try:
                sev = SeverityLevel(issue_model.severity.upper())
            except Exception:
                sev = SeverityLevel.LOW

            db_issue = ReviewIssue(
                review_id=review.id,
                file_path=issue_model.file_path,
                line_number=issue_model.line_number,
                issue_type=category,
                severity=sev,
                message=issue_model.message,
                context_diff=issue_model.context_diff,
                suggestion=issue_model.suggestion
            )
            db_session.add(db_issue)
            await db_session.flush() # Flush to resolve ID for posting inline comments
            
            # Queue inline comments to be posted on GitHub PR in subsequent pipeline actions
            comment_body = (
                f"### ReviewPilot Finding ({db_issue.issue_type.value})\n"
                f"**Severity**: {db_issue.severity.value}\n\n"
                f"{db_issue.message}\n\n"
            )
            if db_issue.suggestion:
                comment_body += f"**Fix Suggestion**:\n```python\n{db_issue.suggestion}\n```"

            db_comment = ReviewComment(
                review_id=review.id,
                issue_id=db_issue.id,
                file_path=db_issue.file_path,
                line_number=db_issue.line_number,
                comment_body=comment_body,
                status=CommentStatus.PENDING
            )
            db_session.add(db_comment)

        # Save summary report
        summary_rep = ReviewSummary(
            review_id=review.id,
            markdown_summary=report.summary,
            total_bugs=bugs_count,
            total_security_flaws=sec_count,
            total_perf_issues=perf_count
        )
        db_session.add(summary_rep)
        await db_session.commit()
        
    except Exception as e:
        # Rollback and mark review as failed
        await db_session.rollback()
        review.status = ReviewStatus.FAILED
        review.summary = f"Execution failed: {str(e)}"
        review.completed_at = datetime.utcnow()
        await db_session.commit()
        raise
