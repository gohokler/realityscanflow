import json
import subprocess
import argparse
from pathlib import Path


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

    return [rc_exe] + built_steps


def run_command(command):
    # runs the RC command and checks if it succeeded
    result = subprocess.run(command)
    if result.returncode != 0:
        print("ERROR: RealityScan failed.")
        return False
    return True


def run_batch(preset, config, input_path):
    # finds all subfolders and processes them one by one
    folders = [f for f in Path(input_path).iterdir() if f.is_dir()]

    if not folders:
        print("ERROR: No subfolders found in batch folder.")
        return

    print(f"Found {len(folders)} folders to process.")

    for i, folder in enumerate(folders, 1):
        print(f"\n[{i}/{len(folders)}] Processing: {folder.name}")
        command = build_command(preset, config, folder)
        success = run_command(command)
        if not success:
            print(f"ERROR: Failed on {folder.name} — skipping.")
            continue
        print(f"Done: {folder.name}")

    print("\nBatch complete.")


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

    if args.batch:
        run_batch(preset, config, args.input)
    else:
        command = build_command(preset, config, args.input)
        success = run_command(command)
        if not success:
            print("Processing failed.")
            return
        print("Done!")


if __name__ == "__main__":
    main()