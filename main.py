import argparse
from pathlib import Path

from core import (
    load_config,
    load_preset,
    show_presets,
    is_photo_folder,
    find_photo_folders,
    find_projects,
    run_processing,
)


def parse_args() -> argparse.Namespace:
    # defines what user can pass via CLI
    parser = argparse.ArgumentParser(
        description="RealityScanFlow — batch processor for RealityScan"
    )
    parser.add_argument("--input", help="Path to folder with photos or projects")
    parser.add_argument("--preset", help="Preset name (e.g. low, medium, mesh_only)")
    parser.add_argument(
        "--project-mode",
        action="store_true",
        help="Load existing .rsproj files instead of photo folders",
    )
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="Show all available presets and exit",
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


def confirm_run(input_path: str, preset_name: str, items_count: int, mode_label: str) -> bool:
    # shows a summary of what will run and asks for confirmation
    mode = f"batch ({items_count})" if items_count > 1 else "single"
    print(f"\n  Input:   {input_path}")
    print(f"  Preset:  {preset_name}")
    print(f"  Mode:    {mode}")
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

    config = load_config()
    if config is None:
        return

    preset = load_preset(args.preset)
    if preset is None:
        return

    # determine what to process based on mode
    if args.project_mode:
        items = find_projects(args.input)
        if not items:
            print("ERROR: No .rsproj files found in _output subfolders.")
            return
        mode_label = "projects"
    else:
        if is_photo_folder(args.input):
            # input points directly to a scan folder
            items = [{"folder": Path(args.input), "project_path": None, "display": Path(args.input).name}]
            mode_label = "folders"
        else:
            # input is a parent folder containing multiple scans
            items = find_photo_folders(args.input)
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

    if not confirm_run(args.input, args.preset, len(items), mode_label):
        print("Cancelled.")
        return

    run_processing(items, preset, config)


if __name__ == "__main__":
    main()