import json
from pathlib import Path

def validate_preset(preset):
    required_fields = ["name", "steps"]
    for field in required_fields:
        if field not in preset:
            print(f"ERROR: preset is missing required field: '{field}'")
            return False
    return True

def list_presets():
    preset_files = Path('presets').glob('*.json')
    return [p.stem for p in preset_files]

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

def load_preset(name):
    try:
        with open(f'presets/{name}.json') as p:
            return json.load(p)
    except FileNotFoundError:
        print("ERROR: presets not found. Make sure they exists in the project folder.")
        return None
    except json.JSONDecodeError:
        print(f"ERROR: preset '{name}' not found in presets/ folder.")
        return None


def main():
    print("RealityScanFlow - starting...")
    
    config = load_config()
    if config is None:
        return

    preset = load_preset('medium')
    print(validate_preset(preset))

if __name__ == "__main__":
    main()