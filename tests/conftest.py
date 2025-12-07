"""Shared pytest fixtures for Phaser tests."""

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from tools.storage import PhaserStorage
from tools.events import EventEmitter

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def hook_inputs_dir() -> Path:
    """Return path to hook input fixtures."""
    return FIXTURES_DIR / "hook_inputs"


@pytest.fixture
def contracts_dir() -> Path:
    """Return path to contract fixtures."""
    return FIXTURES_DIR / "contracts"


@pytest.fixture
def write_simple_input(hook_inputs_dir: Path) -> dict:
    """Load write_simple.json fixture."""
    with open(hook_inputs_dir / "write_simple.json") as f:
        return json.load(f)


@pytest.fixture
def edit_simple_input(hook_inputs_dir: Path) -> dict:
    """Load edit_simple.json fixture."""
    with open(hook_inputs_dir / "edit_simple.json") as f:
        return json.load(f)


@pytest.fixture
def temp_dir() -> Path:
    """Create a temporary directory for tests."""
    d = Path(tempfile.mkdtemp())
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def storage(temp_dir: Path) -> PhaserStorage:
    """Create a PhaserStorage instance with temp directory."""
    return PhaserStorage(root=temp_dir)


@pytest.fixture
def emitter(storage: PhaserStorage) -> EventEmitter:
    """Create an EventEmitter with storage."""
    return EventEmitter(storage=storage)


@pytest.fixture
def emitter_no_storage() -> EventEmitter:
    """Create an EventEmitter without storage (in-memory only)."""
    return EventEmitter(storage=None)


@pytest.fixture
def sample_project(temp_dir: Path) -> Path:
    """Create a sample project structure for testing."""
    (temp_dir / "src").mkdir()
    (temp_dir / "src" / "main.py").write_text("print('hello')")
    (temp_dir / "README.md").write_text("# Test Project")
    return temp_dir


@pytest.fixture
def sample_manifest(sample_project: Path):
    """Capture manifest of sample project."""
    from tools.diff import capture_manifest
    return capture_manifest(sample_project)


@pytest.fixture
def git_repo(temp_dir: Path) -> Path:
    """Create a temporary git repository."""
    import subprocess

    subprocess.run(["git", "init"], cwd=temp_dir, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=temp_dir,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=temp_dir,
        capture_output=True,
        check=True,
    )

    # Create initial commit with .gitignore for .phaser
    (temp_dir / ".gitignore").write_text(".phaser/\n")
    (temp_dir / "README.md").write_text("# Test Repo")
    subprocess.run(["git", "add", "."], cwd=temp_dir, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=temp_dir,
        capture_output=True,
        check=True,
    )

    return temp_dir


@pytest.fixture
def git_repo_with_files(git_repo: Path) -> Path:
    """Git repo with some source files."""
    import subprocess

    src = git_repo / "src"
    src.mkdir()
    (src / "main.py").write_text("print('hello')")
    (src / "utils.py").write_text("def helper(): pass")
    subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Add source files"],
        cwd=git_repo,
        capture_output=True,
        check=True,
    )
    return git_repo
