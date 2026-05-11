import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from core import (
    is_photo_folder,
    is_already_processed,
    find_photo_folders,
    build_command,
    parse_report,
)


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_preset() -> dict:
    return {
        "name": "low",
        "description": "Test preset",
        "steps": [
            "-addFolder {input_folder}",
            "-align",
            "-save {output_project}",
            "-exportReport {output_report} {overview_template}",
            "-quit",
        ],
    }


@pytest.fixture
def sample_config() -> dict:
    return {
        "rc_executable": "C:/RC/RealityScan.exe",
        "headless": False,
    }


# ── is_photo_folder ───────────────────────────────────────────────────────────

def test_is_photo_folder_with_images(tmp_path: Path) -> None:
    # should return True when folder contains image files
    (tmp_path / "photo.jpg").touch()
    assert is_photo_folder(tmp_path) is True


def test_is_photo_folder_without_images(tmp_path: Path) -> None:
    # should return False when folder has no image files
    (tmp_path / "notes.txt").touch()
    assert is_photo_folder(tmp_path) is False


def test_is_photo_folder_empty(tmp_path: Path) -> None:
    # should return False for an empty folder
    assert is_photo_folder(tmp_path) is False


# ── is_already_processed ──────────────────────────────────────────────────────

def test_is_already_processed_true(tmp_path: Path) -> None:
    # should return True when .rsproj exists in _output
    output = tmp_path / "_output"
    output.mkdir()
    (output / f"{tmp_path.name}.rsproj").touch()
    assert is_already_processed(tmp_path) is True


def test_is_already_processed_false(tmp_path: Path) -> None:
    # should return False when no _output or no .rsproj
    assert is_already_processed(tmp_path) is False


# ── find_photo_folders ────────────────────────────────────────────────────────

def test_find_photo_folders_returns_subfolders(tmp_path: Path) -> None:
    # should find all subfolders as processable items
    (tmp_path / "scan_01").mkdir()
    (tmp_path / "scan_02").mkdir()
    (tmp_path / "notes.txt").touch()

    result = find_photo_folders(tmp_path)
    names = [item["display"] for item in result]

    assert len(result) == 2
    assert "scan_01" in names
    assert "scan_02" in names


# ── build_command ─────────────────────────────────────────────────────────────

def test_build_command_replaces_placeholders(
    tmp_path: Path, sample_preset: dict, sample_config: dict
) -> None:
    # placeholders in steps should be replaced with real paths
    command, report_path = build_command(sample_preset, sample_config, tmp_path)

    joined = " ".join(command)
    assert str(tmp_path) in joined
    assert "-align" in command
    assert "-quit" in command


def test_build_command_adds_headless(
    tmp_path: Path, sample_preset: dict, sample_config: dict
) -> None:
    # -headless should appear when config headless=True
    sample_config["headless"] = True
    command, _ = build_command(sample_preset, sample_config, tmp_path)
    assert "-headless" in command


def test_build_command_no_headless_by_default(
    tmp_path: Path, sample_preset: dict, sample_config: dict
) -> None:
    # -headless should NOT appear when headless=False
    command, _ = build_command(sample_preset, sample_config, tmp_path)
    assert "-headless" not in command


# ── parse_report ──────────────────────────────────────────────────────────────

def test_parse_report_returns_none_if_missing(tmp_path: Path) -> None:
    # should return None when report file doesn't exist
    result = parse_report(tmp_path / "nonexistent.html")
    assert result is None


def test_parse_report_extracts_data(tmp_path: Path) -> None:
    # should extract th/td pairs from HTML into a dict
    report = tmp_path / "report.html"
    report.write_text("""
    <html><body>
    <table>
      <tr><th>Number of inputs</th><td>14</td></tr>
      <tr><th>Count of registered images</th><td>14 / 14</td></tr>
    </table>
    </body></html>
    """, encoding="utf-8")

    result = parse_report(report)
    assert result is not None
    assert result["Number of inputs"] == "14"
    assert result["Count of registered images"] == "14 / 14"