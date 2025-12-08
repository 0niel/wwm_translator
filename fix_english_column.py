#!/usr/bin/env python3
"""
Fix English column in ru.csv by re-extracting from original game files.

This script:
1. Re-extracts en.csv from game files (after Steam verify integrity)
2. Rebuilds ru.csv with correct English column
3. Preserves all Russian translations from en_translations.json

Usage:
    python fix_english_column.py
"""

import csv
import json
import shutil
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Import extractor from the project
from src.extractor import extract_game_locale
from src.config import init_config

console = Console()


def backup_file(file_path: Path) -> Path | None:
    """Create backup of a file."""
    if not file_path.exists():
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = file_path.with_suffix(f".backup_{timestamp}{file_path.suffix}")
    shutil.copy2(file_path, backup_path)
    return backup_path


def load_source_csv(csv_path: Path) -> dict[str, str]:
    """Load ID -> OriginalText mapping from source CSV (en.csv format)."""
    data = {}
    
    with open(csv_path, encoding="utf-8", newline="") as f:
        reader = csv.reader(f, delimiter=";")
        header = next(reader, None)
        
        if not header:
            return data
        
        try:
            id_idx = header.index("ID")
            text_idx = header.index("OriginalText")
        except ValueError:
            console.print("[red]Error: Required columns not found in source CSV[/red]")
            return data
        
        for row in reader:
            if len(row) > max(id_idx, text_idx):
                data[row[id_idx]] = row[text_idx]
    
    return data


def load_translations(json_path: Path) -> dict[str, str]:
    """Load translations from JSON file."""
    if not json_path.exists():
        return {}
    
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)


def load_existing_ru_csv(csv_path: Path) -> list[dict]:
    """Load existing ru.csv data."""
    if not csv_path.exists():
        return []
    
    rows = []
    # Use errors='replace' to handle corrupted UTF-8 data
    with open(csv_path, encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            rows.append(row)
    
    return rows


def rebuild_ru_csv(
    ru_csv_path: Path,
    new_english: dict[str, str],
    translations: dict[str, str],
    original_chinese: dict[str, str],
) -> tuple[int, int, int]:
    """
    Rebuild ru.csv with correct English column.
    
    Returns: (total_rows, updated_english, preserved_translations)
    """
    # Load existing data
    existing_rows = load_existing_ru_csv(ru_csv_path)
    
    if not existing_rows:
        console.print("[yellow]Warning: ru.csv is empty or doesn't exist[/yellow]")
        return 0, 0, 0
    
    updated_english = 0
    preserved_translations = 0
    
    new_rows = []
    
    for row in existing_rows:
        entry_id = row.get("ID", "")
        
        # Get correct English text
        if entry_id in new_english:
            old_english = row.get("English", "")
            new_english_text = new_english[entry_id]
            
            if old_english != new_english_text:
                row["English"] = new_english_text
                updated_english += 1
        
        # Preserve Russian translation from JSON if exists
        if entry_id in translations:
            row["Russian"] = translations[entry_id]
            preserved_translations += 1
        
        # Update Original if available
        if entry_id in original_chinese:
            row["Original"] = original_chinese[entry_id]
        
        new_rows.append(row)
    
    # Write back
    with open(ru_csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, 
            fieldnames=["ID", "Original", "English", "Russian", "Status"],
            delimiter=";"
        )
        writer.writeheader()
        writer.writerows(new_rows)
    
    return len(new_rows), updated_english, preserved_translations


def main():
    console.print("\n[bold cyan]═══ WWM English Column Fixer ═══[/bold cyan]\n")
    
    # Load config
    try:
        config, _ = init_config("config.yaml")
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        return 1
    
    # Paths
    game_locale_dir = config.paths.game_locale_dir
    source_dir = config.paths.source_dir
    translated_dir = config.paths.translated_dir
    progress_dir = config.paths.progress_dir
    
    en_csv = source_dir / "csv" / "en.csv"
    zh_csv = source_dir / "csv" / "zh_cn.csv"
    ru_csv = translated_dir / "ru.csv"
    translations_json = progress_dir / "en_translations.json"
    
    # Check game files
    locale_file = game_locale_dir / "translate_words_map_en"
    
    console.print("[bold]Step 1: Checking files...[/bold]")
    
    table = Table()
    table.add_column("File", style="cyan")
    table.add_column("Status", style="green")
    
    table.add_row("Game locale dir", "✓" if game_locale_dir.exists() else "✗ NOT FOUND")
    table.add_row("EN locale file", "✓" if locale_file.exists() else "✗ NOT FOUND")
    table.add_row("Current en.csv", "✓" if en_csv.exists() else "—")
    table.add_row("zh_cn.csv", "✓" if zh_csv.exists() else "✗")
    table.add_row("ru.csv", "✓" if ru_csv.exists() else "✗")
    table.add_row("translations.json", "✓" if translations_json.exists() else "✗")
    
    console.print(table)
    console.print()
    
    if not locale_file.exists():
        console.print("[red]Error: Game locale file not found![/red]")
        console.print(f"Expected: {locale_file}")
        console.print("\n[yellow]Please verify game files integrity in Steam first![/yellow]")
        return 1
    
    if not translations_json.exists():
        console.print("[red]Error: Translations JSON not found![/red]")
        console.print("Your translation progress would be lost.")
        return 1
    
    # Backup existing files
    console.print("[bold]Step 2: Creating backups...[/bold]")
    
    if en_csv.exists():
        backup = backup_file(en_csv)
        console.print(f"  Backed up en.csv → {backup.name if backup else 'N/A'}")
    
    if ru_csv.exists():
        backup = backup_file(ru_csv)
        console.print(f"  Backed up ru.csv → {backup.name if backup else 'N/A'}")
    
    console.print()
    
    # Re-extract en.csv
    console.print("[bold]Step 3: Re-extracting en.csv from game files...[/bold]")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Extracting...", total=None)
        
        result = extract_game_locale(
            locale_file,
            source_dir,
            log_callback=lambda msg: None,
        )
        
        progress.update(task, completed=True)
    
    if not result.success:
        console.print(f"[red]Extraction failed: {result.message}[/red]")
        return 1
    
    console.print(f"  [green]✓ Extracted {result.texts_extracted:,} texts[/green]")
    console.print()
    
    # Load new English data
    console.print("[bold]Step 4: Loading data...[/bold]")
    
    new_english = load_source_csv(en_csv)
    console.print(f"  New English entries: {len(new_english):,}")
    
    translations = load_translations(translations_json)
    console.print(f"  Saved translations: {len(translations):,}")
    
    original_chinese = load_source_csv(zh_csv) if zh_csv.exists() else {}
    console.print(f"  Chinese context: {len(original_chinese):,}")
    
    console.print()
    
    # Rebuild ru.csv
    console.print("[bold]Step 5: Rebuilding ru.csv...[/bold]")
    
    total, updated, preserved = rebuild_ru_csv(
        ru_csv,
        new_english,
        translations,
        original_chinese,
    )
    
    console.print()
    
    # Results
    result_table = Table(title="Results")
    result_table.add_column("Metric", style="cyan")
    result_table.add_column("Value", style="green")
    
    result_table.add_row("Total rows", f"{total:,}")
    result_table.add_row("English updated", f"{updated:,}")
    result_table.add_row("Translations preserved", f"{preserved:,}")
    
    console.print(result_table)
    console.print()
    
    console.print("[bold green]✓ Done! English column has been fixed.[/bold green]")
    console.print("\nYour translation progress is preserved.")
    console.print("You can continue translating with: [cyan]python main.py translate[/cyan]")
    
    return 0


if __name__ == "__main__":
    exit(main())

