"""Static release gates that do not need Django or a database.

These checks protect the assembled repository from packaging and test-harness
regressions that are easy to miss when business tests are all green.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent
FIRST_PARTY_APPS = (
    "accounts",
    "projects",
    "workflow",
    "project_management",
    "notifications",
    "grades",
    "committees",
    "project_imports",
    "gitlab_integration",
    "dy_forms",
)
SOURCE_DIRS = tuple(BACKEND_ROOT / app for app in FIRST_PARTY_APPS) + (BACKEND_ROOT / "backend",)
IGNORED_DIR_NAMES = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    ".test-media",
    ".test-artifacts",
    "htmlcov",
}


def _iter_files(root: Path, suffixes: set[str] | None = None):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_DIR_NAMES for part in path.parts):
            continue
        if suffixes is not None and path.suffix.lower() not in suffixes:
            continue
        yield path


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def test_no_merge_conflict_markers_in_source():
    offenders = []
    for source_dir in SOURCE_DIRS:
        for path in _iter_files(source_dir, {".py"}):
            text = _read(path)
            if re.search(r"(?m)^(?:<<<<<<<(?: .*)?|=======|>>>>>>>(?: .*)?)$", text):
                offenders.append(str(path.relative_to(BACKEND_ROOT)))
    assert offenders == []


def test_no_debugger_calls_in_production_python():
    offenders = []
    for source_dir in SOURCE_DIRS:
        for path in _iter_files(source_dir, {".py"}):
            if "tests" in path.parts or "migrations" in path.parts:
                continue
            text = _read(path)
            if "breakpoint(" in text or "pdb.set_trace(" in text:
                offenders.append(str(path.relative_to(BACKEND_ROOT)))
    assert offenders == []


def _gitignore_text() -> str:
    return _read(PROJECT_ROOT / ".gitignore")


def test_project_gitignore_exists():
    assert (PROJECT_ROOT / ".gitignore").is_file()


def test_gitignore_excludes_environment_files():
    text = _gitignore_text()
    assert ".env" in text
    assert ".env.*" in text


def test_gitignore_excludes_local_database_files():
    text = _gitignore_text()
    assert "*.sqlite" in text
    assert "*.sqlite3" in text
    assert "*.db" in text


def test_gitignore_excludes_python_test_and_coverage_artifacts():
    text = _gitignore_text()
    for pattern in ("__pycache__/", "*.py[cod]", ".pytest_cache/", ".coverage", ".test-artifacts/", ".test-media/"):
        assert pattern in text


def test_gitignore_excludes_frontend_dependency_and_build_artifacts():
    text = _gitignore_text()
    for pattern in ("node_modules/", "dist/", "build/"):
        assert pattern in text

def test_required_test_dependencies_are_declared():
    text = _read(BACKEND_ROOT / "requirements-test.txt").lower()
    for package in ("pytest", "pytest-django", "pytest-cov", "coverage[toml]", "factory-boy", "freezegun"):
        assert package in text


def test_pytest_uses_dedicated_test_settings():
    text = _read(BACKEND_ROOT / "pytest.ini")
    assert "DJANGO_SETTINGS_MODULE = backend.settings_test" in text


def test_pytest_uses_importlib_import_mode():
    text = _read(BACKEND_ROOT / "pytest.ini")
    assert "--import-mode=importlib" in text


def test_pytest_enables_strict_configuration_and_markers():
    text = _read(BACKEND_ROOT / "pytest.ini")
    assert "--strict-config" in text
    assert "--strict-markers" in text


def test_pytest_testpaths_cover_every_first_party_app():
    text = _read(BACKEND_ROOT / "pytest.ini")
    for app in FIRST_PARTY_APPS:
        assert f"{app}/tests" in text
    assert "tests" in text


def test_every_first_party_app_has_tests_package():
    missing = [app for app in FIRST_PARTY_APPS if not (BACKEND_ROOT / app / "tests").is_dir()]
    assert missing == []


def test_every_first_party_test_package_is_importable_package():
    missing = [app for app in FIRST_PARTY_APPS if not (BACKEND_ROOT / app / "tests" / "__init__.py").is_file()]
    assert missing == []


def test_every_first_party_app_has_api_regression_tests():
    missing = [app for app in FIRST_PARTY_APPS if not (BACKEND_ROOT / app / "tests" / "test_api.py").is_file()]
    assert missing == []


def test_every_first_party_app_has_security_regression_tests():
    missing = [app for app in FIRST_PARTY_APPS if not (BACKEND_ROOT / app / "tests" / "test_security.py").is_file()]
    assert missing == []


def test_every_first_party_app_has_model_tests():
    missing = [app for app in FIRST_PARTY_APPS if not (BACKEND_ROOT / app / "tests" / "test_models.py").is_file()]
    assert missing == []


def test_expected_cross_app_integration_files_exist():
    integration = BACKEND_ROOT / "tests" / "integration"
    expected = {
        "test_project_lifecycle.py",
        "test_api_lifecycle.py",
        "test_security_lifecycle.py",
    }
    assert expected <= {path.name for path in integration.glob("test_*.py")}


def test_expected_smoke_gate_files_exist():
    smoke = BACKEND_ROOT / "tests" / "smoke"
    expected = {"test_test_environment.py", "test_project_quality_gates.py"}
    assert expected <= {path.name for path in smoke.glob("test_*.py")}


def test_release_runner_exists():
    assert (BACKEND_ROOT / "tests" / "run_release_gates.ps1").is_file()


def test_release_runner_executes_all_gate_layers_and_coverage():
    text = _read(BACKEND_ROOT / "tests" / "run_release_gates.ps1")
    for required in (
        "tests/release",
        "tests/smoke",
        "tests/integration",
        "--cov=accounts",
        "--cov=dy_forms",
        "--cov-report=xml:.test-artifacts/coverage.xml",
        "--cov-report=html:.test-artifacts/htmlcov",
        "--cov-fail-under=70",
    ):
        assert required in text


def test_coverage_configuration_exists_and_tracks_branches():
    text = _read(BACKEND_ROOT / ".coveragerc")
    assert "[run]" in text
    assert "branch = True" in text


def test_coverage_configuration_omits_tests_and_migrations():
    text = _read(BACKEND_ROOT / ".coveragerc")
    assert "*/tests/*" in text
    assert "*/migrations/*" in text


def test_all_backend_python_files_parse_successfully():
    failures = []
    for path in _iter_files(BACKEND_ROOT, {".py"}):
        try:
            ast.parse(_read(path), filename=str(path))
        except SyntaxError as exc:
            failures.append(f"{path.relative_to(BACKEND_ROOT)}:{exc.lineno}:{exc.msg}")
    assert failures == []


def test_every_migration_package_has_init_file():
    missing = []
    for app in FIRST_PARTY_APPS:
        migrations = BACKEND_ROOT / app / "migrations"
        if migrations.is_dir() and not (migrations / "__init__.py").is_file():
            missing.append(app)
    assert missing == []
