import json

def load_config():
    try:
        with open('config.json') as f:
            return json.load(f)
    except FileNotFoundError:
        print("ERROR: config.json not found. Make sure it exists in the project folder.")
        return None
    except json.JSONDecodeError:
        print("ERROR: config.json is broken. Check for missing parts.")
        return None

def main():
    print("RealityScanFlow - starting...")
    
    config = load_config()
    if config is None:
        return
    
    print(config)

if __name__ == "__main__":
    main()