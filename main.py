import argparse
from pathlib import Path

from core import (
    load_config,
    load_preset,
    show_presets,
    has_files,
    find_subfolders,
    find_projects,
    run_processing,
)


def parse_args() -> argparse.Namespace:
    # defines what user can pass via CLI
    parser = argparse.ArgumentParser(
        description="RealityScanFlow — batch processor for RealityScan"
    )
    parser.add_argument("--input", help="Path to folder with subfolders, photos or projects")
    parser.add_argument("--preset", help="Preset name (e.g. raw_scan, preview)")
    parser.add_argument(
        "--project-mode",
        action="store_true",
        help="Load existing .rsproj files",
    )
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="Show all available presets",
    )
    return parser.parse_args()


def select_items(items: list[dict], label: str) -> list[dict]:
    # shows numbered list and lets user pick which items to process
    print(f"\nAvailable {label}:\n")
    for i, item in enumerate(items, 1):
        print(f"  {i}. {item['display']}")

    print("\nEnter numbers to process (e.g. 1 2 3) or 'all':")
    answer = input("> ").strip().lower()

    if answer == "all":
        return items

    selected = []
    for part in answer.split():
        try:
            idx = int(part) - 1
            if 0 <= idx < len(items):
                selected.append(items[idx])
            else:
                print(f"  WARNING: '{part}' is out of range — skipped.")
        except ValueError:
            print(f"  WARNING: '{part}' is not a valid number — skipped.")

    return selected


def confirm_run(input_path: str, preset_name: str, items: list[dict]) -> bool:
    mode = f"batch ({len(items)})" if len(items) > 1 else "single"
    print(f"\n  Input:   {input_path}")
    print(f"  Preset:  {preset_name}")
    print(f"  Mode:    {mode}")
    for item in items:
        print(f"           • {item['display']}")
    answer = input("\nContinue? [Y/n]: ").strip().lower()
    return answer in ("", "y", "yes")


def main() -> None:
    args = parse_args()

    # standalone command — show presets and exit
    if args.list_presets:
        show_presets()
        return

    # --input and --preset are required for processing
    if not args.input or not args.preset:
        print("ERROR: --input and --preset are required.")
        print("Use --list-presets to see available presets.")
        return

    print("RealityScanFlow - starting...")

    # resolve input path once — handles "." and relative paths
    input_path = str(Path(args.input).resolve())

    config = load_config()
    if config is None:
        return

    preset = load_preset(args.preset)
    if preset is None:
        return

    # determine what to process based on mode
    if args.project_mode:
        items = find_projects(input_path)
        if not items:
            print("ERROR: No .rsproj files found in _output subfolders.")
            return
        mode_label = "projects"
    else:
        if has_files(input_path):
            # input points directly to a scan folder
            items = [{"folder": Path(input_path), "project_path": None, "display": Path(input_path).name}]
            mode_label = "folders"
        else:
            # input is a parent folder containing multiple scans
            items = find_subfolders(input_path)
            if not items:
                print("ERROR: No subfolders or images found in the input folder.")
                return
            mode_label = "folders"

    # show what was found — let user select if more than one
    if len(items) == 1:
        print(f"\nFound: {items[0]['display']}")
    else:
        items = select_items(items, mode_label)
        if not items:
            print("No items selected.")
            return

    if not confirm_run(input_path, args.preset, items):
        print("Cancelled.")
        return

    run_processing(items, preset, config)


if __name__ == "__main__":
    main()