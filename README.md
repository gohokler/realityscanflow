# RealityScanFlow

Batch processor for RealityScan. Point at a folder, pick a preset, let it run overnight.

Built for Technical Artists who work with large scan sets and don't want to click through the UI for every project.

---

## What it does

- Auto-detects single scan or batch of subfolders
- Runs any preset pipeline on all selected scans
- Skips already processed scans (per preset), asks to reprocess if needed
- Saves each project with preset name suffix — `scan_01_raw_scan.rsproj`
- Generates HTML overview report after each scan
- Supports continuing existing projects via `--project-mode`

---

## Requirements

- Windows 10/11
- RealityScan 2.x
- Python 3.10+

---

## Installation

**1. Clone or download the repository**

```
git clone https://github.com/yourusername/realityscanflow.git
cd realityscanflow
```

Or download ZIP and extract anywhere without spaces in the path.

**2. Create virtual environment and install dependencies**

```
python -m venv .venv
.venv\Scripts\activate
pip install rich beautifulsoup4
```

**3. Configure**

Copy `config.example.json` to `config.json` and set your RealityScan path:

```json
{
    "rs_executable": "C:\\Program Files\\Epic Games\\RealityScan\\RealityScan.exe",
    "global_settings": "metadata/global_settings.rsconfig",
    "headless": false
}
```

**4. Export your RealityScan settings**

Open RealityScan → Application menu → Export Global Settings → save as `metadata/global_settings.rsconfig`

This file controls alignment, mesh, texture and simplify parameters for all presets.

---

## Usage

**Run from the tool folder:**

```
.venv\Scripts\python.exe main.py --input "C:\scans\batch" --preset raw_scan
```

**Or add to PATH for global access:**

Add the `realityscanflow` folder to your system PATH. Then from any directory:

```
rsflow --input "." --preset raw_scan
rsflow --input "C:\scans\batch" --preset preview
rsflow --input "." --preset proj_mesh --project-mode
```

---

## Commands

```
rsflow                                      show welcome screen
rsflow --guide                              show full guide with examples
rsflow --list-presets                       show all available presets
rsflow --input "path" --preset name        process a folder
rsflow --input "." --preset name           process current directory
rsflow --input "path" --preset name --project-mode    continue existing .rsproj files
```

---

## Presets

| Preset | Description |
|---|---|
| `align` | Align only + report. Check quality before overnight batch |
| `preview` | Quick preview mesh. Fast visual check |
| `raw_scan` | Align + full mesh + cleanup |
| `highpoly` | Maximum quality mesh for retopology |
| `raw_textured` | Full pipeline: align + mesh + texture |
| `ai_mask` | AI background masking + align + mesh |
| `proj_mesh` | Load existing project, calculate mesh (`--project-mode`) |
| `proj_texture` | Load existing project, calculate texture (`--project-mode`) |

Add your own preset by dropping a `.json` file into `presets/` — no code changes needed.

---

## Folder structure

```
realityscanflow/
├── main.py              entry point
├── core.py              processing logic
├── config.json          your local settings (not in repo)
├── config.example.json  template for config
├── guide.json           guide content for --guide command
├── rsflow.bat           Windows launcher
├── presets/             preset JSON files
└── metadata/            global_settings.rsconfig goes here
```

---

## Known limitations

- Folder paths with spaces will break RealityScan CLI — avoid them
- `headless: true` runs RealityScan without UI — useful for overnight batch but harder to debug
- `global_settings.rsconfig` is machine-specific — export it fresh from your RealityScan installation

---

## Roadmap

- Rich CLI progress bars
- Parallel workers (`--workers` flag)
- Align quality check — skip mesh if < 80% cameras aligned
- Session report JSON
- Scan health analysis