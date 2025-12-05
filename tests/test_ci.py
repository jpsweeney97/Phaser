"""Tests for the CI integration module."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.ci import (
    CIConfig,
    CIPlatform,
    CIStatus,
    PHASER_VERSION,
    format_ci_status,
    generate_workflow,
    get_ci_status,
    init_ci,
    remove_ci,
)
from tools.storage import PhaserStorage


class TestCIPlatform:
    """Tests for CIPlatform enum."""

    def test_github_value(self) -> None:
        """GitHub platform has correct value."""
        assert CIPlatform.GITHUB.value == "github"

    def test_gitlab_value(self) -> None:
        """GitLab platform has correct value."""
        assert CIPlatform.GITLAB.value == "gitlab"

    def test_circleci_value(self) -> None:
        """CircleCI platform has correct value."""
        assert CIPlatform.CIRCLECI.value == "circleci"


class TestCIConfig:
    """Tests for CIConfig dataclass."""

    def test_to_dict(self) -> None:
        """to_dict produces correct structure."""
        config = CIConfig(
            platform=CIPlatform.GITHUB,
            workflow_path=Path(".github/workflows/phaser.yml"),
            generated_at="2025-12-05T10:00:00Z",
            phaser_version="1.3.0",
            python_version="3.11",
            on_push=True,
            on_pr=True,
            branches=["main", "master"],
            fail_on_warning=False,
        )
        result = config.to_dict()

        assert result["version"] == 1
        assert result["platform"] == "github"
        assert result["phaser_version"] == "1.3.0"
        assert result["options"]["python_version"] == "3.11"
        assert result["options"]["branches"] == ["main", "master"]

    def test_from_dict(self) -> None:
        """from_dict reconstructs CIConfig."""
        data = {
            "platform": "github",
            "workflow_path": ".github/workflows/phaser.yml",
            "generated_at": "2025-12-05T10:00:00Z",
            "phaser_version": "1.3.0",
            "options": {
                "python_version": "3.12",
                "on_push": False,
                "on_pr": True,
                "branches": ["main"],
                "fail_on_warning": True,
            },
        }
        config = CIConfig.from_dict(data)

        assert config.platform == CIPlatform.GITHUB
        assert config.python_version == "3.12"
        assert config.on_push is False
        assert config.fail_on_warning is True


class TestGenerateWorkflow:
    """Tests for generate_workflow function."""

    def test_github_workflow_basic(self) -> None:
        """Generates valid GitHub Actions workflow."""
        config = CIConfig(
            platform=CIPlatform.GITHUB,
            workflow_path=Path(".github/workflows/phaser.yml"),
            generated_at="2025-12-05T10:00:00Z",
            phaser_version=PHASER_VERSION,
            python_version="3.11",
            on_push=True,
            on_pr=True,
            branches=["main"],
            fail_on_warning=False,
        )
        result = generate_workflow(CIPlatform.GITHUB, config)

        assert "name: Phaser Contract Check" in result
        assert 'python-version: "3.11"' in result
        assert "phaser check --fail-on-error" in result
        assert "push:" in result
        assert "pull_request:" in result

    def test_github_workflow_no_push(self) -> None:
        """Workflow without push trigger."""
        config = CIConfig(
            platform=CIPlatform.GITHUB,
            workflow_path=Path(".github/workflows/phaser.yml"),
            generated_at="2025-12-05T10:00:00Z",
            phaser_version=PHASER_VERSION,
            python_version="3.11",
            on_push=False,
            on_pr=True,
            branches=["main"],
            fail_on_warning=False,
        )
        result = generate_workflow(CIPlatform.GITHUB, config)

        assert "push:" not in result
        assert "pull_request:" in result

    def test_github_workflow_fail_on_warning(self) -> None:
        """Workflow with fail-on-warning flag."""
        config = CIConfig(
            platform=CIPlatform.GITHUB,
            workflow_path=Path(".github/workflows/phaser.yml"),
            generated_at="2025-12-05T10:00:00Z",
            phaser_version=PHASER_VERSION,
            python_version="3.11",
            on_push=True,
            on_pr=True,
            branches=["main"],
            fail_on_warning=True,
        )
        result = generate_workflow(CIPlatform.GITHUB, config)

        assert "--fail-on-warning" in result

    def test_gitlab_not_supported(self) -> None:
        """GitLab raises not supported error."""
        config = CIConfig(
            platform=CIPlatform.GITLAB,
            workflow_path=Path(".gitlab-ci.yml"),
            generated_at="2025-12-05T10:00:00Z",
            phaser_version=PHASER_VERSION,
        )

        with pytest.raises(ValueError, match="not yet supported"):
            generate_workflow(CIPlatform.GITLAB, config)


class TestInitCI:
    """Tests for init_ci function."""

    def test_creates_workflow_file(self, tmp_path: Path) -> None:
        """init_ci creates workflow file."""
        storage = PhaserStorage(tmp_path / ".phaser")
        root = tmp_path

        workflow_path, config = init_ci(
            storage=storage,
            root=root,
            platform=CIPlatform.GITHUB,
        )

        assert workflow_path.exists()
        assert "name: Phaser Contract Check" in workflow_path.read_text()
        assert config.platform == CIPlatform.GITHUB

    def test_saves_config(self, tmp_path: Path) -> None:
        """init_ci saves configuration."""
        storage = PhaserStorage(tmp_path / ".phaser")
        root = tmp_path

        init_ci(storage=storage, root=root)

        config_path = storage.get_path("ci.yaml")
        assert config_path.exists()

    def test_refuses_overwrite_without_force(self, tmp_path: Path) -> None:
        """init_ci refuses to overwrite existing workflow."""
        storage = PhaserStorage(tmp_path / ".phaser")
        root = tmp_path

        # Create initial workflow
        init_ci(storage=storage, root=root)

        # Try to create again
        with pytest.raises(FileExistsError):
            init_ci(storage=storage, root=root)

    def test_overwrites_with_force(self, tmp_path: Path) -> None:
        """init_ci overwrites with force=True."""
        storage = PhaserStorage(tmp_path / ".phaser")
        root = tmp_path

        # Create initial workflow
        init_ci(storage=storage, root=root, python_version="3.10")

        # Overwrite
        workflow_path, config = init_ci(
            storage=storage,
            root=root,
            python_version="3.12",
            force=True,
        )

        assert "3.12" in workflow_path.read_text()

    def test_invalid_python_version(self, tmp_path: Path) -> None:
        """init_ci rejects invalid Python version."""
        storage = PhaserStorage(tmp_path / ".phaser")
        root = tmp_path

        with pytest.raises(ValueError, match="Invalid Python version"):
            init_ci(storage=storage, root=root, python_version="2.7")


class TestGetCIStatus:
    """Tests for get_ci_status function."""

    def test_no_config(self, tmp_path: Path) -> None:
        """Status when no CI configured."""
        storage = PhaserStorage(tmp_path / ".phaser")
        storage.ensure_directories()

        status = get_ci_status(storage, tmp_path)

        assert status.workflow_exists is False
        assert status.config is None

    def test_with_config(self, tmp_path: Path) -> None:
        """Status when CI is configured."""
        storage = PhaserStorage(tmp_path / ".phaser")
        init_ci(storage=storage, root=tmp_path)

        status = get_ci_status(storage, tmp_path)

        assert status.workflow_exists is True
        assert status.config is not None
        assert status.platform == CIPlatform.GITHUB


class TestRemoveCI:
    """Tests for remove_ci function."""

    def test_removes_workflow(self, tmp_path: Path) -> None:
        """remove_ci deletes workflow file."""
        storage = PhaserStorage(tmp_path / ".phaser")
        workflow_path, _ = init_ci(storage=storage, root=tmp_path)

        assert workflow_path.exists()

        removed = remove_ci(storage, tmp_path)

        assert removed is True
        assert not workflow_path.exists()

    def test_returns_false_if_not_found(self, tmp_path: Path) -> None:
        """remove_ci returns False if no workflow."""
        storage = PhaserStorage(tmp_path / ".phaser")
        storage.ensure_directories()

        removed = remove_ci(storage, tmp_path)

        assert removed is False


class TestFormatCIStatus:
    """Tests for format_ci_status function."""

    def test_format_active(self) -> None:
        """Formats active CI status."""
        config = CIConfig(
            platform=CIPlatform.GITHUB,
            workflow_path=Path(".github/workflows/phaser.yml"),
            generated_at="2025-12-05T10:00:00Z",
            phaser_version=PHASER_VERSION,
            branches=["main"],
        )
        status = CIStatus(
            platform=CIPlatform.GITHUB,
            workflow_exists=True,
            workflow_path=Path(".github/workflows/phaser.yml"),
            config=config,
            contract_count=5,
            error_count=3,
            warning_count=2,
        )

        result = format_ci_status(status)

        assert "Status: Active" in result
        assert "Contracts: 5 enabled" in result
        assert "3 error-severity" in result

    def test_format_not_configured(self) -> None:
        """Formats unconfigured CI status."""
        status = CIStatus(
            platform=CIPlatform.GITHUB,
            workflow_exists=False,
            workflow_path=None,
            config=None,
            contract_count=0,
            error_count=0,
            warning_count=0,
        )

        result = format_ci_status(status)

        assert "Status: Not configured" in result
