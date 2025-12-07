"""Tests for contract loading and validation."""

from pathlib import Path

import pytest
import yaml

from tools.contract_loader import (
    Contract,
    LoadResult,
    load_contracts,
    load_contracts_from_dir,
    validate_contract,
)


class TestValidateContract:
    def test_valid_contract(self) -> None:
        data = {
            "rule_id": "no-print",
            "type": "forbid_pattern",
            "pattern": r"print\(",
            "file_glob": "**/*.py",
            "message": "Avoid print statements",
            "severity": "warning",
        }
        contract, error = validate_contract(data, "project")
        assert error is None
        assert contract is not None
        assert contract.rule_id == "no-print"

    def test_missing_rule_id(self) -> None:
        data = {
            "type": "forbid_pattern",
            "pattern": "x",
            "file_glob": "*",
            "message": "m",
            "severity": "error",
        }
        _, error = validate_contract(data, "user")
        assert error is not None
        assert "rule_id" in error

    def test_invalid_type(self) -> None:
        data = {
            "rule_id": "test",
            "type": "invalid",
            "file_glob": "*",
            "message": "m",
            "severity": "error",
        }
        _, error = validate_contract(data, "user")
        assert error is not None
        assert "type" in error

    def test_invalid_regex(self) -> None:
        data = {
            "rule_id": "test",
            "type": "forbid_pattern",
            "pattern": "(*",
            "file_glob": "*",
            "message": "m",
            "severity": "error",
        }
        _, error = validate_contract(data, "user")
        assert error is not None
        assert "regex" in error.lower()

    def test_missing_pattern_for_pattern_type(self) -> None:
        data = {
            "rule_id": "test",
            "type": "forbid_pattern",
            "file_glob": "*",
            "message": "m",
            "severity": "error",
        }
        _, error = validate_contract(data, "user")
        assert error is not None
        assert "pattern" in error.lower()


class TestLoadContractsFromDir:
    def test_empty_dir(self, tmp_path: Path) -> None:
        result = load_contracts_from_dir(tmp_path, "project")
        assert result.contracts == []

    def test_nonexistent_dir(self, tmp_path: Path) -> None:
        result = load_contracts_from_dir(tmp_path / "nope", "project")
        assert result.contracts == []

    def test_load_valid_contract(self, tmp_path: Path) -> None:
        contract_file = tmp_path / "test.yaml"
        contract_file.write_text(
            yaml.dump(
                {
                    "rule_id": "test-rule",
                    "type": "forbid_pattern",
                    "pattern": "TODO",
                    "file_glob": "**/*.py",
                    "message": "No TODOs",
                    "severity": "warning",
                }
            )
        )
        result = load_contracts_from_dir(tmp_path, "project")
        assert len(result.contracts) == 1
        assert result.contracts[0].rule_id == "test-rule"

    def test_skip_invalid_contract(self, tmp_path: Path) -> None:
        contract_file = tmp_path / "bad.yaml"
        contract_file.write_text(yaml.dump({"rule_id": "bad"}))  # Missing fields
        result = load_contracts_from_dir(tmp_path, "project")
        assert result.contracts == []
        assert len(result.warnings) == 1


class TestLoadContracts:
    def test_project_precedence(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Create project contract
        project_dir = tmp_path / ".claude" / "contracts"
        project_dir.mkdir(parents=True)
        (project_dir / "rule.yaml").write_text(
            yaml.dump(
                {
                    "rule_id": "shared-rule",
                    "type": "forbid_pattern",
                    "pattern": "project",
                    "file_glob": "*",
                    "message": "From project",
                    "severity": "error",
                }
            )
        )

        # Create user contract with same ID
        user_dir = tmp_path / "home" / ".phaser" / "contracts"
        user_dir.mkdir(parents=True)
        (user_dir / "rule.yaml").write_text(
            yaml.dump(
                {
                    "rule_id": "shared-rule",
                    "type": "forbid_pattern",
                    "pattern": "user",
                    "file_glob": "*",
                    "message": "From user",
                    "severity": "error",
                }
            )
        )

        # Mock home directory
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        result = load_contracts(project_root=tmp_path)
        assert len(result.contracts) == 1
        assert result.contracts[0].pattern == "project"  # Project wins


class TestContractMethods:
    def test_matches_file(self) -> None:
        contract = Contract(
            rule_id="test",
            type="forbid_pattern",
            pattern="x",
            file_glob="**/*.py",
            message="m",
            severity="error",
        )
        assert contract.matches_file("src/app.py")
        assert not contract.matches_file("src/app.js")

    def test_compiled_pattern_cached(self) -> None:
        contract = Contract(
            rule_id="test",
            type="forbid_pattern",
            pattern=r"\d+",
            file_glob="*",
            message="m",
            severity="error",
        )
        p1 = contract.compiled_pattern
        p2 = contract.compiled_pattern
        assert p1 is p2  # Same object
