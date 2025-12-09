#!/usr/bin/env python3
import csv
import shutil
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

from src.config import init_config

console = Console()


def backup_file(file_path: Path) -> Path | None:
    if not file_path.exists():
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = file_path.with_suffix(f".backup_{timestamp}{file_path.suffix}")
    shutil.copy2(file_path, backup_path)
    return backup_path


def load_source_csv(csv_path: Path) -> dict[str, str]:
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


def load_existing_ru_csv(csv_path: Path) -> list[dict]:
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
) -> tuple[int, int]:
    existing_rows = load_existing_ru_csv(ru_csv_path)
    if not existing_rows:
        console.print("[yellow]Warning: ru.csv is empty or doesn't exist[/yellow]")
        return 0, 0

    updated_english = 0
    new_rows = []

    for row in existing_rows:
        entry_id = row.get("ID", "")

        if entry_id in new_english:
            old_english = row.get("English", "")
            new_text = new_english[entry_id]
            if old_english != new_text:
                row["English"] = new_text
                updated_english += 1

        # Do NOT touch Russian/Original/Status columns
        new_rows.append(row)

    with open(ru_csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["ID", "Original", "English", "Russian", "Status"],
            delimiter=";",
        )
        writer.writeheader()
        writer.writerows(new_rows)

    return len(new_rows), updated_english


def main():
    console.print("\n[bold cyan]═══ WWM English Column Fixer ═══[/bold cyan]\n")
    
    # Load config
    try:
        config, _ = init_config("config.yaml")
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        return 1
    
    source_dir = config.paths.source_dir
    translated_dir = config.paths.translated_dir

    en_csv = source_dir / "csv" / "en.csv"
    ru_csv = translated_dir / "ru.csv"
    
    console.print("[bold]Step 1: Checking files...[/bold]")
    
    table = Table()
    table.add_column("File", style="cyan")
    table.add_column("Status", style="green")
    
    table.add_row("Current en.csv", "✓" if en_csv.exists() else "✗ NOT FOUND")
    table.add_row("ru.csv", "✓" if ru_csv.exists() else "✗ NOT FOUND")
    
    console.print(table)
    console.print()
    
    if not en_csv.exists():
        console.print("[red]Error: en.csv not found in data/source/csv[/red]")
        console.print("Place extracted en.csv into data/source/csv and rerun.")
        return 1
    
    console.print("[bold]Step 2: Creating backups...[/bold]")
    
    if en_csv.exists():
        backup = backup_file(en_csv)
        console.print(f"  Backed up en.csv → {backup.name if backup else 'N/A'}")
    
    if ru_csv.exists():
        backup = backup_file(ru_csv)
        console.print(f"  Backed up ru.csv → {backup.name if backup else 'N/A'}")
    
    console.print()
    
    # Re-extract en.csv
    console.print("[bold]Step 3: Loading data...[/bold]")
    
    new_english = load_source_csv(en_csv)
    console.print(f"  New English entries: {len(new_english):,}")
    
    console.print()
    
    # Rebuild ru.csv
    console.print("[bold]Step 4: Rebuilding ru.csv (English only)...[/bold]")
    
    total, updated = rebuild_ru_csv(
        ru_csv,
        new_english,
    )
    
    console.print()
    
    # Results
    result_table = Table(title="Results")
    result_table.add_column("Metric", style="cyan")
    result_table.add_column("Value", style="green")
    
    result_table.add_row("Total rows", f"{total:,}")
    result_table.add_row("English updated", f"{updated:,}")
    
    console.print(result_table)
    console.print()
    
    console.print("[bold green]✓ Done! English column has been fixed.[/bold green]")
    console.print("\nYour translation progress is preserved.")
    console.print("You can continue translating with: [cyan]python main.py translate[/cyan]")
    
    return 0


if __name__ == "__main__":
    exit(main())

