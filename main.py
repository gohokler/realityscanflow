import argparse
import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.text import Text
from rich import box
from rich.status import Status

from core import (
    load_config,
    load_preset,
    load_help,
    list_all_presets,
    has_files,
    find_subfolders,
    find_projects,
    is_already_processed,
    build_command,
    run_command,
    format_elapsed,
)

console = Console()


# --- UI components ---

def show_header() -> None:
    # small header shown before processing
    console.print()
    console.print("[bold cyan]RealityScanFlow[/bold cyan] [dim]— batch processor for RealityScan[/dim]")
    console.print()


def show_welcome() -> None:
    # full welcome board shown when rsflow is called without arguments
    title = Text("RealityScanFlow", style="bold cyan", justify="center")
    subtitle = Text("Batch processor for RealityScan", style="dim", justify="center")

    body = Text()
    body.append("\n")
    body.append("  Quick start:\n", style="bold")
    body.append("    rsflow --list-presets         ", style="cyan")
    body.append("show all available presets\n", style="dim")
    body.append("    rsflow --guide                ", style="cyan")
    body.append("show full guide with examples\n", style="dim")
    body.append("    rsflow --input \".\" --preset raw_scan   ", style="cyan")
    body.append("process current folder\n", style="dim")
    body.append("\n")
    body.append("  Tip: ", style="bold yellow")
    body.append("check ", style="dim")
    body.append("config.json", style="cyan")
    body.append(" before first run — make sure ", style="dim")
    body.append("rs_executable", style="cyan")
    body.append(" path is correct\n", style="dim")

    console.print()
    console.print(Panel(
        Text.assemble(title, "\n", subtitle, body),
        border_style="cyan",
        box=box.ROUNDED,
        padding=(1, 2),
    ))
    console.print()


def show_guide() -> None:
    # detailed guide loaded from help.json
    data = load_help()
    if data is None:
        console.print("[red]ERROR:[/red] help.json not found or broken.")
        return

    console.print()
    console.print(Panel(
        Text(data["title"], style="bold cyan", justify="center"),
        border_style="cyan",
        box=box.ROUNDED,
    ))
    console.print(f"\n[dim]{data['intro']}[/dim]\n")

    console.print("[bold]Setup:[/bold]")
    for step in data["setup"]:
        console.print(f"  {step}")
    console.print()

    console.print("[bold]Commands:[/bold]")
    table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    table.add_column(style="cyan", no_wrap=False)
    table.add_column(style="dim")
    for entry in data["commands"]:
        table.add_row(entry["cmd"], entry["desc"])
    console.print(table)
    console.print()

    console.print("[bold]Tips:[/bold]")
    for tip in data["tips"]:
        console.print(f"  • [dim]{tip}[/dim]")
    console.print()


def show_presets() -> None:
    presets = list_all_presets()
    if not presets:
        console.print("[yellow]No presets found in presets/ folder.[/yellow]")
        return

    table = Table(title="Available presets", box=box.SIMPLE, title_style="bold cyan")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Description", style="dim")
    for p in presets:
        style = "red" if p["broken"] else None
        table.add_row(p["name"], p["description"], style=style)
    console.print()
    console.print(table)
    console.print()


# --- input/output helpers ---

def select_items(items: list[dict], label: str) -> list[dict]:
    console.print(f"\n[bold]Available {label}:[/bold]\n")
    for i, item in enumerate(items, 1):
        console.print(f"  [cyan]{i}.[/cyan] {item['display']}")

    answer = Prompt.ask("\n[bold]Enter numbers to process[/bold] [dim](e.g. 1 2 3) or[/dim] [cyan]all[/cyan]").strip().lower()

    if answer == "all":
        return items

    selected = []
    for part in answer.split():
        try:
            idx = int(part) - 1
            if 0 <= idx < len(items):
                selected.append(items[idx])
            else:
                console.print(f"  [yellow]WARNING:[/yellow] '{part}' is out of range — skipped.")
        except ValueError:
            console.print(f"  [yellow]WARNING:[/yellow] '{part}' is not a valid number — skipped.")
    return selected


def confirm_run(input_path: str, preset_name: str, items: list[dict]) -> bool:
    mode = f"batch ({len(items)})" if len(items) > 1 else "single"

    table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
    table.add_column(style="dim", no_wrap=True)
    table.add_column()
    table.add_row("Input:", input_path)
    table.add_row("Preset:", f"[cyan]{preset_name}[/cyan]")
    table.add_row("Mode:", mode)
    items_text = "\n".join(f"• {item['display']}" for item in items)
    table.add_row("Items:", items_text)

    console.print()
    console.print(table)
    return Confirm.ask("\n[bold]Continue?[/bold]", default=True)


# --- processing loop (UI lives here) ---

def run_processing(items: list[dict], preset: dict, config: dict) -> None:
    success_count = 0
    skipped_count = 0
    start_total = time.time()

    for i, item in enumerate(items, 1):
        folder = item["folder"]
        project_path = item["project_path"]
        display = item["display"]

        console.print(f"\n[bold cyan]\\[{i}/{len(items)}][/bold cyan] Processing: {display}")

        # skip or reprocess already processed
        if not project_path and is_already_processed(folder, preset["name"]):
            console.print(f"  [yellow]![/yellow] {folder.name} already processed with '[cyan]{preset['name']}[/cyan]'.")
            if not Confirm.ask("  Reprocess?", default=False):
                skipped_count += 1
                continue

        start = time.time()
        command, report_path = build_command(preset, config, folder, project_path=project_path)
        with console.status(
            f"[bold cyan]Processing:[/bold cyan] {display}",
            spinner="aesthetic",
        ):
            success, error = run_command(command)
        elapsed = time.time() - start

        if not success:
            console.print(f"  [red]ERROR:[/red] {error} — skipping [{display}].")
            continue

        if report_path.exists():
            success_count += 1
            console.print(f"  [green]✓[/green] [{folder.name}] done in [bold]{format_elapsed(elapsed)}[/bold]")

    total_elapsed = time.time() - start_total
    total = len(items) - skipped_count

    console.print()
    console.print(f"[bold green]Done.[/bold green] {success_count}/{total} processed in [bold]{format_elapsed(total_elapsed)}[/bold]")
    if skipped_count > 0:
        console.print(f"[dim]Skipped: {skipped_count} (already processed)[/dim]")


# --- CLI entry ---

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="RealityScanFlow — batch processor for RealityScan",
        add_help=False,
    )
    parser.add_argument("--input", help="Path to folder with subfolders, photos or projects")
    parser.add_argument("--preset", help="Preset name (e.g. raw_scan, preview)")
    parser.add_argument("--project-mode", action="store_true", help="Load existing .rsproj files")
    parser.add_argument("--list-presets", action="store_true", help="Show all available presets")
    parser.add_argument("--guide", action="store_true", help="Show full guide with examples")
    parser.add_argument("-h", "--help", action="store_true", help="Show this help")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # standalone informational commands
    if args.help or (not any([args.input, args.preset, args.list_presets, args.guide, args.project_mode])):
        show_welcome()
        return

    if args.guide:
        show_guide()
        return

    if args.list_presets:
        show_presets()
        return

    if not args.input or not args.preset:
        console.print("[red]ERROR:[/red] [bold]--input[/bold] and [bold]--preset[/bold] are required.")
        console.print("[dim]Use[/dim] [cyan]rsflow --guide[/cyan] [dim]for examples.[/dim]")
        return

    show_header()

    input_path = str(Path(args.input).resolve())

    config = load_config()
    if config is None:
        console.print(f"[red]ERROR:[/red] config.json not found or broken. Check the project folder.")
        return

    preset = load_preset(args.preset)
    if preset is None:
        console.print(f"[red]ERROR:[/red] preset '[cyan]{args.preset}[/cyan]' not found or broken.")
        console.print("[dim]Use[/dim] [cyan]rsflow --list-presets[/cyan] [dim]to see available presets.[/dim]")
        return

    # determine what to process
    if args.project_mode:
        items = find_projects(input_path)
        if not items:
            console.print("[red]ERROR:[/red] No .rsproj files found in _output subfolders.")
            return
        mode_label = "projects"
    else:
        if has_files(input_path):
            items = [{"folder": Path(input_path), "project_path": None, "display": Path(input_path).name}]
            mode_label = "folders"
        else:
            items = find_subfolders(input_path)
            if not items:
                console.print("[red]ERROR:[/red] No subfolders or images found in the input folder.")
                return
            mode_label = "folders"

    if len(items) == 1:
        console.print(f"\n[bold]Found:[/bold] {items[0]['display']}")
    else:
        items = select_items(items, mode_label)
        if not items:
            console.print("[yellow]No items selected.[/yellow]")
            return

    if not confirm_run(input_path, args.preset, items):
        console.print("[dim]Cancelled.[/dim]")
        return

    run_processing(items, preset, config)


if __name__ == "__main__":
    main()