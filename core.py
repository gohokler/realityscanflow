import json
import subprocess
import time
from pathlib import Path
from bs4 import BeautifulSoup

# ── constants ─────────────────────────────────────────────────────────────────

CONFIG_FILE = "config.json"
PRESETS_DIR = "presets"
OUTPUT_DIR = "_output"
PROJECT_EXT = ".rsproj"
REPORT_SUFFIX = "_report.html"
PROCESSED_SUFFIX = "_processed"
RC_REPORTS_SUBDIR = "Reports"
RC_OVERVIEW_TEMPLATE = "Overview.html"

# ── config ────────────────────────────────────────────────────────────────────

def load_config() -> dict | None:
    # reads config.json and returns settings
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: {CONFIG_FILE} not found. Make sure it exists in the project folder.")
        return None
    except json.JSONDecodeError:
        print(f"ERROR: {CONFIG_FILE} is broken. Check for missing commas or quotes.")
        return None


# ── presets ───────────────────────────────────────────────────────────────────

def load_preset(name: str) -> dict | None:
    # loads a preset JSON by name from presets/ folder
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
    # prints all available presets with name and description
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


# ── folder detection ──────────────────────────────────────────────────────────

def is_photo_folder(input_path: str | Path) -> bool:
    # returns True if folder contains any files directly inside
    return any(f.is_file() for f in Path(input_path).iterdir())


def is_already_processed(folder: str | Path) -> bool:
    # checks if the scan already has a .rsproj in _output
    project_name = Path(folder).name
    return (Path(folder) / OUTPUT_DIR / f"{project_name}{PROJECT_EXT}").exists()


def find_photo_folders(input_path: str | Path) -> list[dict]:
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
                "display": f"{folder.name}/{OUTPUT_DIR}/{rsproj.name}",
            })
    return items


# ── command builder ───────────────────────────────────────────────────────────

def build_command(
    preset: dict,
    config: dict,
    folder: str | Path,
    project_path: str | Path | None = None,
) -> tuple[list[str], Path]:
    # builds the full RC command list and returns it with the report path
    folder = Path(folder)
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

    rc_exe = config["rc_executable"]
    overview_template = Path(rc_exe).parent / RC_REPORTS_SUBDIR / RC_OVERVIEW_TEMPLATE

    built_steps: list[str] = []
    for step in preset["steps"]:
        step = step.replace("{input_folder}", str(folder))
        step = step.replace("{input_project}", str(project_path) if project_path else "")
        step = step.replace("{output_project}", str(output_project))
        step = step.replace("{output_report}", str(output_report))
        step = step.replace("{overview_template}", str(overview_template))
        built_steps.extend(step.split(" "))

    headless = ["-headless"] if config.get("headless", False) else []
    return [rc_exe] + headless + built_steps, output_report


# ── runner ────────────────────────────────────────────────────────────────────

def run_command(command: list[str]) -> bool:
    # launches RC and returns True if it exited cleanly
    result = subprocess.run(command)
    if result.returncode != 0:
        print("ERROR: RealityScan failed.")
        return False
    return True


def parse_report(report_path: str | Path) -> dict | None:
    # parses the RC HTML report into a key-value dict
    if not Path(report_path).exists():
        return None
    with open(report_path, encoding="utf-8-sig", errors="ignore") as f:
        soup = BeautifulSoup(f, "html.parser")
    data = {}
    for row in soup.find_all("tr"):
        th = row.find("th")
        td = row.find("td")
        if th and td:
            data[th.text.strip()] = td.text.strip()
    return data


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

        # skip already processed — only in photo-folder mode
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
            parse_report(report_path)  # parsed, not displayed yet — reserved for v1.1
            print(f"  [{folder.name}] done in {elapsed:.0f}s")

    total_elapsed = time.time() - start_total
    minutes = int(total_elapsed // 60)
    seconds = int(total_elapsed % 60)
    total = len(items) - skipped_count

    print(f"\nDone. {success_count}/{total} processed in {minutes}m {seconds}s")
    if skipped_count > 0:
        print(f"Skipped: {skipped_count} (already processed)")