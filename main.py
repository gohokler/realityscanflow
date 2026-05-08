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
    parser.add_argument('--input', required=True, help='Path to folder with photos')
    parser.add_argument('--preset', required=True, help='Preset name (e.g. low, medium)')
    parser.add_argument('--batch', action='store_true', help='Process all subfolders one by one')
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


def list_presets():
    # returns all available preset names
    return [p.stem for p in Path('presets').glob('*.json')]


def validate_preset(preset):
    # checks that preset has all required fields
    for field in ["name", "steps"]:
        if field not in preset:
            print(f"ERROR: preset is missing required field: '{field}'")
            return False
    return True


def confirm_run(args, folders_count=None):
    # shows run summary and asks user to confirm
    mode = f"batch ({folders_count} folders)" if args.batch else "single"
    print(f"\n  Input:   {args.input}")
    print(f"  Preset:  {args.preset}")
    print(f"  Mode:    {mode}")
    answer = input("\nContinue? [Y/n]: ").strip().lower()
    return answer in ('', 'y', 'yes')


def build_command(preset, config, input_folder):
    # builds the full RC command from preset + config + input path
    input_path = Path(input_folder)
    project_name = input_path.name

    output_dir = input_path / '_output'
    output_dir.mkdir(parents=True, exist_ok=True)
    output_project = output_dir / f'{project_name}.rsproj'
    output_report = output_dir / f'{project_name}_report.html'

    rc_exe = config['rc_executable']
    overview_template = Path(rc_exe).parent / 'Reports' / 'Overview.html'

    built_steps = []
    for step in preset['steps']:
        step = step.replace('{input_folder}', str(input_path))
        step = step.replace('{output_project}', str(output_project))
        step = step.replace('{output_report}', str(output_report))
        step = step.replace('{overview_template}', str(overview_template))
        built_steps.extend(step.split(' '))

    return [rc_exe] + (['-headless'] if config.get('headless', False) else []) + built_steps


def run_command(command):
    # runs the RC command and checks if it succeeded
    result = subprocess.run(command)
    if result.returncode != 0:
        print("ERROR: RealityScan failed.")
        return False
    return True


def is_already_processed(folder):
    # checks if the scan was already processed by looking for .rsproj in _output
    project_name = Path(folder).name
    return (Path(folder) / '_output' / f'{project_name}.rsproj').exists()


def parse_report(report_path):
    # reads the RC HTML report and extracts key data into a dict
    if not Path(report_path).exists():
        print("WARNING: report not found, skipping summary.")
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


def print_summary(scan_name, data, elapsed):
    # prints a short summary to terminal
    aligned = data.get('Count of registered images', 'N/A')
    print(f"  [{scan_name}] done in {elapsed:.0f}s. Aligned: {aligned} photos")


def process_single(preset, config, input_folder):
    # processes a single scan folder
    input_path = Path(input_folder)

    if is_already_processed(input_path):
        print(f"SKIP: {input_path.name} — already processed. Delete _output/ to reprocess.")
        return

    start = time.time()
    command = build_command(preset, config, input_path)
    success = run_command(command)
    elapsed = time.time() - start

    if not success:
        print("Processing failed.")
        return

    report_path = input_path / '_output' / f'{input_path.name}_report.html'
    data = parse_report(report_path)
    if data:
        print_summary(input_path.name, data, elapsed)


def run_batch(preset, config, input_path):
    # finds all subfolders and processes them one by one
    folders = [f for f in Path(input_path).iterdir() if f.is_dir()]

    if not folders:
        print("ERROR: No subfolders found in batch folder.")
        return

    print(f"Found {len(folders)} folders to process.")

    success_count = 0
    skipped_count = 0
    start_total = time.time()

    for i, folder in enumerate(folders, 1):
        print(f"\n[{i}/{len(folders)}] Processing: {folder.name}")

        if is_already_processed(folder):
            print(f"  SKIP: {folder.name} — already processed.")
            skipped_count += 1
            continue

        start = time.time()
        command = build_command(preset, config, folder)
        success = run_command(command)
        elapsed = time.time() - start

        if not success:
            print(f"  ERROR: Failed on {folder.name} — skipping.")
            continue

        report_path = folder / '_output' / f'{folder.name}_report.html'
        report_exists = report_path.exists()

        if report_exists:
            success_count += 1
            data = parse_report(report_path)
            if data:
                print_summary(folder.name, data, elapsed)

    total_elapsed = time.time() - start_total
    minutes = int(total_elapsed // 60)
    seconds = int(total_elapsed % 60)
    total = len(folders) - skipped_count

    print(f"\nBatch complete. {success_count}/{total} processed in {minutes}m {seconds}s")
    if skipped_count > 0:
        print(f"Skipped: {skipped_count} (already processed)")


def main():
    args = parse_args()
    print("RealityScanFlow - starting...")

    config = load_config()
    if config is None:
        return

    preset = load_preset(args.preset)
    if preset is None:
        return
    if not validate_preset(preset):
        return

    folders_count = len([f for f in Path(args.input).iterdir() if f.is_dir()]) if args.batch else None
    if not confirm_run(args, folders_count):
        print("Cancelled.")
        return

    if args.batch:
        run_batch(preset, config, args.input)
    else:
        process_single(preset, config, args.input)
        print("Done!")


if __name__ == "__main__":
    main()