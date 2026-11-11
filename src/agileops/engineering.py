"""Inspect and patch a disposable reporting repository."""

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

from pydantic import BaseModel

from agileops.agents import EngineeringHandoff

FILE = "report_query.py"
KNOWN_BUG = "gross_cents"
CORRECT_COLUMN = "amount_cents"
TEST_FILE = "check_report.py"
REGRESSION_FILE = "test_regression.py"
BASE_SOURCE = 'REPORT_SQL = "SELECT region, COUNT(*), SUM(gross_cents) FROM reporting_orders GROUP BY region"\n'
TEST_SOURCE = """from pathlib import Path
import runpy
import sqlite3

query = runpy.run_path(str(Path(__file__).with_name("report_query.py")))["REPORT_SQL"]
with sqlite3.connect(":memory:") as db:
    db.execute("CREATE TABLE reporting_orders (region TEXT, amount_cents INTEGER)")
    db.executemany("INSERT INTO reporting_orders VALUES (?, ?)",
                   [("Central", 12000), ("East", 5525), ("Central", 7995)])
    rows = db.execute(query).fetchall()
    assert rows == [("Central", 2, 19995), ("East", 1, 5525)], rows
print("Reporting reconciliation passed.")
"""
REGRESSION_SOURCE = """from pathlib import Path
import runpy
import sqlite3

query = runpy.run_path(str(Path(__file__).with_name("report_query.py")))["REPORT_SQL"]
with sqlite3.connect(":memory:") as db:
    db.execute("CREATE TABLE reporting_orders (region TEXT, amount_cents INTEGER)")
    db.execute("INSERT INTO reporting_orders VALUES ('West', 425)")
    assert db.execute(query).fetchone() == ("West", 1, 425)
print("Missing-column regression passed.")
"""


class EngineeringPlan(BaseModel):
    ticket_id: str
    file: str
    symbol: str
    observed: str
    change: str
    matches: list[str]


class EngineeringResult(BaseModel):
    workspace: str
    patch: str
    tests_passed: bool
    output: str


class ValidationResult(BaseModel):
    passed: bool
    checks: list[str]
    output: str


def _run(
    command: list[str], cwd: Path, timeout: int = 30
) -> subprocess.CompletedProcess:
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATHEXT"}
    }
    environment.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    return subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def _git(path: Path, *arguments: str) -> str:
    result = _run(["git", "-c", f"core.hooksPath={os.devnull}", *arguments], path)
    if result.returncode:
        raise RuntimeError(f"Git failed: {result.stderr[-1200:]}")
    return result.stdout


def prepare_repository(root: Path) -> Path:
    base = root / "reporting-source"
    base.mkdir(parents=True, exist_ok=True)
    if not (base / ".git").exists():
        _git(base, "init", "-q")
    try:
        _git(base, "rev-parse", "--verify", "HEAD")
    except RuntimeError:
        (base / FILE).write_text(BASE_SOURCE, encoding="utf-8")
        (base / TEST_FILE).write_text(TEST_SOURCE, encoding="utf-8")
        _git(base, "add", "--", FILE, TEST_FILE)
        _git(
            base,
            "-c",
            "user.name=AgileOps Lab",
            "-c",
            "user.email=lab@example.invalid",
            "commit",
            "-qm",
            "Seed the reporting lab",
        )
    return base


def code_context(base: Path, symbol: str) -> str | None:
    source = (base / FILE).read_text(encoding="utf-8")
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == symbol
            for target in node.targets
        ):
            return ast.get_source_segment(source, node)
    return None


def search_repository(base: Path, text: str) -> list[str]:
    files = _git(base, "ls-files", "--", FILE, TEST_FILE).splitlines()
    return [
        f"{name}:{line_number}: {line.strip()}"
        for name in files
        for line_number, line in enumerate(
            (base / name).read_text(encoding="utf-8").splitlines(), 1
        )
        if text in line
    ][:12]


def propose_patch(base: Path, handoff: EngineeringHandoff) -> EngineeringPlan | None:
    if handoff.investigation.diagnosis_code != "REPORT_COLUMN_MISSING":
        return None
    context = code_context(base, "REPORT_SQL")
    if context is None or KNOWN_BUG not in context:
        return None
    return EngineeringPlan(
        ticket_id=handoff.ticket_id,
        file=FILE,
        symbol="REPORT_SQL",
        observed=context,
        change=f"Replace {KNOWN_BUG} with {CORRECT_COLUMN} and add a regression test.",
        matches=search_repository(base, KNOWN_BUG),
    )


def _workspace(root: Path, workflow_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{32}", workflow_id):
        raise ValueError("Invalid workflow ID.")
    worktree = root / workflow_id
    if worktree.resolve().parent != root.resolve():
        raise ValueError("Invalid controlled worktree path.")
    return worktree.resolve()


def _validate_files(worktree: Path) -> None:
    expected = BASE_SOURCE.replace(KNOWN_BUG, CORRECT_COLUMN)
    for name, content in (
        (FILE, expected),
        (TEST_FILE, TEST_SOURCE),
        (REGRESSION_FILE, REGRESSION_SOURCE),
    ):
        path = worktree / name
        if (
            path.is_symlink()
            or not path.is_file()
            or path.read_text(encoding="utf-8") != content
        ):
            raise ValueError(f"Unexpected content in controlled file {name}.")
        ast.parse(content, filename=name)


def apply_patch(
    root: Path, base: Path, workflow_id: str, plan: EngineeringPlan
) -> EngineeringResult:
    if plan.file != FILE or plan.symbol != "REPORT_SQL":
        raise ValueError("The proposed edit is outside the permitted reporting query.")
    worktree = _workspace(root, workflow_id)
    if not worktree.exists():
        _git(base, "worktree", "add", "--detach", str(worktree), "HEAD")
    source = worktree / FILE
    if source.is_symlink() or not source.is_file():
        raise ValueError("The reporting query is outside the allowed worktree.")
    current = source.read_text(encoding="utf-8")
    if current == BASE_SOURCE:
        source.write_text(
            BASE_SOURCE.replace(KNOWN_BUG, CORRECT_COLUMN), encoding="utf-8"
        )
    regression = worktree / REGRESSION_FILE
    if not regression.exists() and not regression.is_symlink():
        regression.write_text(REGRESSION_SOURCE, encoding="utf-8")
    _validate_files(worktree)
    _git(worktree, "add", "-N", "--", REGRESSION_FILE)
    patch = _git(worktree, "diff", "--", FILE, REGRESSION_FILE)
    result = _run([sys.executable, "-I", REGRESSION_FILE], worktree)
    return EngineeringResult(
        workspace=worktree.name,
        patch=patch,
        tests_passed=result.returncode == 0,
        output=(result.stdout + result.stderr)[-2500:],
    )


def review_patch(root: Path, workflow_id: str) -> ValidationResult:
    worktree = _workspace(root, workflow_id)
    try:
        _validate_files(worktree)
        changes = _git(worktree, "status", "--porcelain").splitlines()
        if set(changes) != {f" M {FILE}", f" A {REGRESSION_FILE}"}:
            raise ValueError(
                "The worktree contains changes outside the approved query patch."
            )
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        return ValidationResult(
            passed=False,
            checks=["scope", "static"],
            output=str(error),
        )
    return ValidationResult(
        passed=True, checks=["scope", "static"], output="Controlled patch verified."
    )


def validate_patch(root: Path, workflow_id: str) -> ValidationResult:
    review = review_patch(root, workflow_id)
    if not review.passed:
        return review
    worktree = _workspace(root, workflow_id)
    result = _run([sys.executable, "-I", TEST_FILE], worktree)
    return ValidationResult(
        passed=result.returncode == 0,
        checks=["scope", "static", "reconciliation"],
        output=(result.stdout + result.stderr)[-2500:],
    )
