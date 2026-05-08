import json
import subprocess
import argparse
import time
from pathlib import Path
from bs4 import BeautifulSoup


def load_config():
    # reads config.json and returns settings
    try:
        with open('config.json') as c:
            return json.load(c)
    except FileNotFoundError:
        print("ERROR: config.json not found. Make sure it exists in the project folder.")
        return None
    except json.JSONDecodeError:
        print("ERROR: config.json is broken. Check for missing commas or quotes.")
        return None


def parse_args():
    # defines what user can pass via CLI
    parser = argparse.ArgumentParser(description='RealityScanFlow — batch processor for RealityScan')
    parser.add_argument('--input', help='Path to folder with photos or projects')
    parser.add_argument('--preset', help='Preset name (e.g. low, medium, mesh_only)')
    parser.add_argument('--project-mode', action='store_true', help='Load existing .rsproj files instead of photo folders')
    parser.add_argument('--list-presets', action='store_true', help='Show all available presets and exit')
    return parser.parse_args()


def load_preset(name):
    # loads a preset JSON by name from presets/ folder
    try:
        with open(f'presets/{name}.json') as p:
            return json.load(p)
    except FileNotFoundError:
        print(f"ERROR: preset '{name}' not found in presets/ folder.")
        return None
    except json.JSONDecodeError:
        print(f"ERROR: preset '{name}' is broken. Check for missing parts.")
        return None


def show_presets():
    # prints all available presets with name and description
    preset_files = sorted(Path('presets').glob('*.json'))
    if not preset_files:
        print("No presets found in presets/ folder.")
        return

    print("\nAvailable presets:\n")
    for path in preset_files:
        try:
            with open(path) as p:
                data = json.load(p)
            name = data.get('name', path.stem)
            desc = data.get('description', '(no description)')
            print(f"  {name:<15} {desc}")
        except (json.JSONDecodeError, FileNotFoundError):
            print(f"  {path.stem:<15} (broken file — check JSON syntax)")


def confirm_run(input_path, preset_name, items_count, mode_label):
    # shows run summary and asks user to confirm
    mode = f"{mode_label} ({items_count})" if items_count > 1 else "single"
    print(f"\n  Input:   {input_path}")
    print(f"  Preset:  {preset_name}")
    print(f"  Mode:    {mode}")
    answer = input("\nContinue? [Y/n]: ").strip().lower()
    return answer in ('', 'y', 'yes')


def select_items(items, label):
    # shows numbered list and lets user pick which to process
    print(f"\nAvailable folders:")
    for i, item in enumerate(items, 1):
        print(f"  {i}. {item['display']}")

    print("\nEnter numbers to process (e.g. 1 2 3) or 'all':")
    answer = input("> ").strip().lower()

    if answer == 'all':
        return items

    selected = []
    for part in answer.split():
        try:
            idx = int(part) - 1
            if 0 <= idx < len(items):
                selected.append(items[idx])
        except ValueError:
            pass

    return selected


def find_photo_folders(input_path):
    # returns list of folders to process when input is a parent dir
    p = Path(input_path)
    folders = [f for f in p.iterdir() if f.is_dir()]
    return [{'folder': f, 'project_path': None, 'display': f.name} for f in folders]


def find_projects(input_path):
    # finds all .rsproj files in _output subfolders
    items = []
    for folder in sorted(Path(input_path).iterdir()):
        if not folder.is_dir():
            continue
        output_dir = folder / '_output'
        if not output_dir.exists():
            continue
        for rsproj in output_dir.glob('*.rsproj'):
            items.append({
                'folder': folder,
                'project_path': rsproj,
                'display': f"{folder.name}/_output/{rsproj.name}"
            })
    return items


def is_input_a_photo_folder(input_path):
    # heuristic: if input has image files directly inside, treat as single scan
    p = Path(input_path)
    formats = {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp'}
    for f in p.iterdir():
        if f.is_file() and f.suffix.lower() in formats:
            return True
    return False


def is_already_processed(folder):
    # checks if the scan was already processed by looking for .rsproj in _output
    project_name = Path(folder).name
    return (Path(folder) / '_output' / f'{project_name}.rsproj').exists()


def build_command(preset, config, folder, project_path=None):
    # builds the full RC command from preset + config + paths
    folder = Path(folder)
    project_name = folder.name

    output_dir = folder / '_output'
    output_dir.mkdir(parents=True, exist_ok=True)
    output_project = output_dir / f'{project_name}.rsproj'
    output_report = output_dir / f'{project_name}_report.html'

    # for project mode — output saved alongside original with preset suffix
    if project_path:
        p = Path(project_path)
        output_project = p.parent / f'{p.stem}_{preset["name"]}_processed.rsproj'
        output_report = p.parent / f'{p.stem}_{preset["name"]}_report.html'

    rc_exe = config['rc_executable']
    overview_template = Path(rc_exe).parent / 'Reports' / 'Overview.html'

    built_steps = []
    for step in preset['steps']:
        step = step.replace('{input_folder}', str(folder))
        step = step.replace('{input_project}', str(project_path) if project_path else '')
        step = step.replace('{output_project}', str(output_project))
        step = step.replace('{output_report}', str(output_report))
        step = step.replace('{overview_template}', str(overview_template))
        built_steps.extend(step.split(' '))

    return [rc_exe] + (['-headless'] if config.get('headless', False) else []) + built_steps, output_report


def run_command(command):
    # runs the RC command and checks if it succeeded
    result = subprocess.run(command)
    if result.returncode != 0:
        print("ERROR: RealityScan failed.")
        return False
    return True


def parse_report(report_path):
    # reads the RC HTML report and extracts key data into a dict
    if not Path(report_path).exists():
        return None

    with open(report_path, encoding='utf-8-sig', errors='ignore') as f:
        soup = BeautifulSoup(f, 'html.parser')

    data = {}
    for row in soup.find_all('tr'):
        th = row.find('th')
        td = row.find('td')
        if th and td:
            data[th.text.strip()] = td.text.strip()

    return data


def run_processing(items, preset, config):
    # universal runner — works for both photo folders and existing projects
    success_count = 0
    skipped_count = 0
    start_total = time.time()

    for i, item in enumerate(items, 1):
        folder = item['folder']
        project_path = item['project_path']
        display = item['display']

        print(f"\n[{i}/{len(items)}] Processing: {display}")

        # skip only for photo-folder mode — project mode is intentional reprocessing
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
            parse_report(report_path)  # parsed but not displayed for now
            print(f"  [{folder.name}] done in {elapsed:.0f}s")

    total_elapsed = time.time() - start_total
    minutes = int(total_elapsed // 60)
    seconds = int(total_elapsed % 60)
    total = len(items) - skipped_count

    print(f"\nDone. {success_count}/{total} processed in {minutes}m {seconds}s")
    if skipped_count > 0:
        print(f"Skipped: {skipped_count} (already processed)")


def main():
    args = parse_args()

    # standalone command — list presets and exit
    if args.list_presets:
        show_presets()
        return

    # both --input and --preset are required for actual processing
    if not args.input or not args.preset:
        print("ERROR: --input and --preset are required for processing.")
        print("Use --list-presets to see available presets.")
        return

    print("RealityScanFlow - starting...")

    config = load_config()
    if config is None:
        return

    preset = load_preset(args.preset)
    if preset is None:
        return

    # decide what to process
    if args.project_mode:
        items = find_projects(args.input)
        if not items:
            print("ERROR: No .rsproj files found in _output subfolders.")
            return
        mode_label = "project batch"
    else:
        if is_input_a_photo_folder(args.input):
            # single photo folder — process directly
            items = [{'folder': Path(args.input), 'project_path': None, 'display': Path(args.input).name}]
            mode_label = "single"
        else:
            # parent folder with subfolders
            items = find_photo_folders(args.input)
            if not items:
                print("ERROR: No subfolders found and no images in the input folder.")
                return
            mode_label = "batch"

    # let user select if more than one item
    if len(items) == 1:
        print(f"\nFound folder: {items[0]['display']}")
    else:
        items = select_items(items, mode_label)
        if not items:
            print("No items selected.")
            return

    if not confirm_run(args.input, args.preset, len(items), mode_label):
        print("Cancelled.")
        return

    run_processing(items, preset, config)


if __name__ == "__main__":
    main()