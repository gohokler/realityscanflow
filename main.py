import json
import subprocess
import argparse
from pathlib import Path


def load_config():
    try:
        with open('config.json') as c:
            return json.load(c)
    except FileNotFoundError:
        print("ERROR: config.json not found. Make sure it exists in the project folder.")
        return None
    except json.JSONDecodeError:
        print("ERROR: config.json is broken. Check for missing parts.")
        return None


def parse_args():
    parser = argparse.ArgumentParser(description='RealityScanFlow — batch processor for RealityScan')
    parser.add_argument('--input', required=True, help='Path to folder with photos')
    parser.add_argument('--preset', required=True, help='Preset name (e.g. medium, low)')
    return parser.parse_args()


def load_preset(name):
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
    preset_files = Path('presets').glob('*.json')
    return [p.stem for p in preset_files]


def validate_preset(preset):
    required_fields = ["name", "steps"]
    for field in required_fields:
        if field not in preset:
            print(f"ERROR: preset is missing required field: '{field}'")
            return False
    return True


def build_command(preset, config, input_folder):
    input_path = Path(input_folder)
    project_name = input_path.name
    output_project = input_path / '_output' / f'{project_name}.rsproj'

    rc_exe = config['rc_executable']

    built_steps = []
    for step in preset['steps']:
        step = step.replace('{input_folder}', str(input_path))
        step = step.replace('{output_project}', str(output_project))
        built_steps.extend(step.split(' ', 1))

    return [rc_exe] + built_steps


def run_command(command):
    result = subprocess.run(command, capture_output=True)
    if result.returncode != 0:
        print("ERROR: RealityScan failed.")
        print(result.stderr.decode())
        return False
    return True


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

    command = build_command(preset, config, args.input)
    success = run_command(command)
    if not success:
        print("Processing failed.")
        return

    print("Done!")


if __name__ == "__main__":
    main()