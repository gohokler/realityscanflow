import json
import subprocess
import time
from pathlib import Path

# --- constants ---

CONFIG_FILE = Path(__file__).parent / "config.json"
PRESETS_DIR = Path(__file__).parent / "presets"
METADATA_DIR = Path(__file__).parent / "metadata"
OUTPUT_DIR = "_output"
PROJECT_EXT = ".rsproj"
REPORT_SUFFIX = "_report.html"
PROCESSED_SUFFIX = "_processed"
RS_REPORTS_SUBDIR = "Reports"
RS_OVERVIEW_TEMPLATE = "Overview.html"


# --- config ---

def load_config() -> dict | None:
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: {CONFIG_FILE} not found. Make sure it exists in the project folder.")
        return None
    except json.JSONDecodeError:
        print(f"ERROR: {CONFIG_FILE} is broken. Check for missing commas or quotes.")
        return None


# --- presets ---

def load_preset(name: str) -> dict | None:
    try:
        with open(f"{PRESETS_DIR}/{name}.json") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: preset '{name}' not found in {PRESETS_DIR}/ folder.")
        return None
    except json.JSONDecodeError:
        print(f"ERROR: preset '{name}' is broken. Check for missing parts.")
        return None


def show_presets() -> None:
    preset_files = sorted(Path(PRESETS_DIR).glob("*.json"))
    if not preset_files:
        print(f"No presets found in {PRESETS_DIR}/ folder.")
        return

    print("\nAvailable presets:\n")
    for path in preset_files:
        try:
            with open(path) as f:
                data = json.load(f)
            name = data.get("name", path.stem)
            desc = data.get("description", "(no description)")
            print(f"  {name:<15} {desc}")
        except (json.JSONDecodeError, FileNotFoundError):
            print(f"  {path.stem:<15} (broken file — check JSON syntax)")


# --- folder detection ---

def has_files(input_path: str | Path) -> bool:
    return any(f.is_file() for f in Path(input_path).iterdir())


def is_already_processed(folder: str | Path) -> bool:
    # checks if the scan already has a .rsproj in _output
    project_name = Path(folder).name
    return (Path(folder) / OUTPUT_DIR / f"{project_name}{PROJECT_EXT}").exists()


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
    output_project = output_dir / f"{project_name}{PROJECT_EXT}"
    output_report = output_dir / f"{project_name}{REPORT_SUFFIX}"

    # project mode — save result alongside original with preset name suffix
    if project_path:
        p = Path(project_path)
        output_project = p.parent / f"{p.stem}_{preset['name']}{PROCESSED_SUFFIX}{PROJECT_EXT}"
        output_report = p.parent / f"{p.stem}_{preset['name']}{REPORT_SUFFIX}"

    rs_exe = config["rs_executable"]
    overview_template = Path(rs_exe).parent / RS_REPORTS_SUBDIR / RS_OVERVIEW_TEMPLATE

    built_steps: list[str] = []
    for step in preset["steps"]:
        step = step.replace("{input_folder}", str(folder))
        step = step.replace("{input_project}", str(project_path) if project_path else "")
        step = step.replace("{output_project}", str(output_project))
        step = step.replace("{output_report}", str(output_report))
        step = step.replace("{overview_template}", str(overview_template))
        step = step.replace("{scan_name}", project_name)
        # global settings placeholders
        step = step.replace("{global_settings}", str(METADATA_DIR / "global_settings.rsconfig"))
        built_steps.extend(step.split(" "))

    headless = ["-headless"] if config.get("headless", False) else []
    return [rs_exe] + headless + built_steps, output_report


# --- runner ---

def run_command(command: list[str]) -> bool:
    try:
        result = subprocess.run(command)
        if result.returncode != 0:
            print("ERROR: RealityScan failed.")
            return False
        return True
    except FileNotFoundError:
        print(f"ERROR: RealityScan executable not found. Check rs_executable in config.json.")
        return False


def run_processing(items: list[dict], preset: dict, config: dict) -> None:
    # processes a list of scan folders or projects one by one
    success_count = 0
    skipped_count = 0
    start_total = time.time()

    for i, item in enumerate(items, 1):
        folder: Path = item["folder"]
        project_path = item["project_path"]
        display: str = item["display"]

        print(f"\n[{i}/{len(items)}] Processing: {display}")

        # skip already processed — only in subfolder mode
        if not project_path and is_already_processed(folder):
            print(f"  SKIP: {folder.name} — already processed.")
            skipped_count += 1
            continue

        start = time.time()
        command, report_path = build_command(preset, config, folder, project_path=project_path)
        success = run_command(command)
        elapsed = time.time() - start

        if not success:
            print(f"  ERROR: Failed on {display} — skipping.")
            continue

        if report_path.exists():
            success_count += 1
            if elapsed < 60:
                print(f"  [{folder.name}] done in {elapsed:.0f}s")
            else:
                minutes = int(elapsed // 60)
                seconds = int(elapsed % 60)
                print(f"  [{folder.name}] done in {minutes}m {seconds}s")

    total_elapsed = time.time() - start_total
    minutes = int(total_elapsed // 60)
    seconds = int(total_elapsed % 60)
    total = len(items) - skipped_count

    print(f"\nDone. {success_count}/{total} processed in {minutes}m {seconds}s")
    if skipped_count > 0:
        print(f"Skipped: {skipped_count} (already processed)")