import json
import subprocess
from pathlib import Path

# --- constants ---

CONFIG_FILE = Path(__file__).parent / "config.json"
PRESETS_DIR = Path(__file__).parent / "presets"
HELP_FILE = Path(__file__).parent / "guide.json"
OUTPUT_DIR = "_output"
PROJECT_EXT = ".rsproj"
REPORT_SUFFIX = "_report.html"
PROCESSED_SUFFIX = "_processed"
RS_REPORTS_SUBDIR = "Reports"
RS_OVERVIEW_TEMPLATE = "Overview.html"


# --- config & presets ---

def load_config() -> dict | None:
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def load_preset(name: str) -> dict | None:
    try:
        with open(PRESETS_DIR / f"{name}.json") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def load_help() -> dict | None:
    try:
        with open(HELP_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def list_all_presets() -> list[dict]:
    # returns list of all preset metadata: name + description
    items = []
    for path in sorted(PRESETS_DIR.glob("*.json")):
        try:
            with open(path) as f:
                data = json.load(f)
            items.append({
                "name": data.get("name", path.stem),
                "description": data.get("description", "(no description)"),
                "broken": False,
            })
        except (json.JSONDecodeError, FileNotFoundError):
            items.append({"name": path.stem, "description": "broken file", "broken": True})
    return items


# --- folder detection ---

def has_files(input_path: str | Path) -> bool:
    return any(f.is_file() for f in Path(input_path).iterdir())


def is_already_processed(folder: str | Path, preset_name: str) -> bool:
    # checks if this specific preset was already run on this folder
    project_name = Path(folder).name
    return (Path(folder) / OUTPUT_DIR / f"{project_name}_{preset_name}{PROJECT_EXT}").exists()


def find_subfolders(input_path: str | Path) -> list[dict]:
    # returns all subfolders as processable items
    folders = [f for f in Path(input_path).iterdir() if f.is_dir()]
    return [{"folder": f, "project_path": None, "display": f.name} for f in folders]


def find_projects(input_path: str | Path) -> list[dict]:
    # finds all .rsproj files in _output subfolders
    items = []
    for folder in sorted(Path(input_path).iterdir()):
        if not folder.is_dir():
            continue
        output_dir = folder / OUTPUT_DIR
        if not output_dir.exists():
            continue
        for rsproj in output_dir.glob(f"*{PROJECT_EXT}"):
            items.append({
                "folder": folder,
                "project_path": rsproj,
                "display": rsproj.name,
            })
    return items


# --- command builder ---

def build_command(
    preset: dict,
    config: dict,
    folder: str | Path,
    project_path: str | Path | None = None,
) -> tuple[list[str], Path]:
    folder = Path(folder).resolve()
    project_name = folder.name

    output_dir = folder / OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    output_project = output_dir / f"{project_name}_{preset['name']}{PROJECT_EXT}"
    output_report = output_dir / f"{project_name}{REPORT_SUFFIX}"

    # project mode — save result alongside original with preset name suffix
    if project_path:
        p = Path(project_path)
        output_project = p.parent / f"{p.stem}_{preset['name']}{PROCESSED_SUFFIX}{PROJECT_EXT}"
        output_report = p.parent / f"{p.stem}_{preset['name']}{REPORT_SUFFIX}"

    rs_exe = config["rs_executable"]
    overview_template = Path(rs_exe).parent / RS_REPORTS_SUBDIR / RS_OVERVIEW_TEMPLATE
    global_settings_path = Path(__file__).parent / config.get("global_settings", "metadata/global_settings.rsconfig")

    built_steps: list[str] = []
    for step in preset["steps"]:
        step = step.replace("{input_folder}", str(folder))
        step = step.replace("{input_project}", str(project_path) if project_path else "")
        step = step.replace("{output_project}", str(output_project))
        step = step.replace("{output_report}", str(output_report))
        step = step.replace("{overview_template}", str(overview_template))
        step = step.replace("{scan_name}", project_name)
        step = step.replace("{global_settings}", str(global_settings_path))
        built_steps.extend(step.split(" "))

    headless = ["-headless"] if config.get("headless", False) else []
    return [rs_exe] + headless + built_steps, output_report


# --- runner ---

def run_command(command: list[str]) -> tuple[bool, str | None]:
    # returns (success, error_message). UI decides what to print.
    try:
        result = subprocess.run(command)
        if result.returncode != 0:
            return False, "RealityScan failed."
        return True, None
    except FileNotFoundError:
        return False, "RealityScan executable not found. Check rs_executable in config.json."


def format_elapsed(elapsed: float) -> str:
    if elapsed < 60:
        return f"{elapsed:.0f}s"
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)
    return f"{minutes}m {seconds}s"