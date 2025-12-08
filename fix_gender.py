#!/usr/bin/env python3
"""
CLI tool to fix grammatical gender in Russian translations.

Usage:
    python fix_gender.py                    # Process ru.csv, show preview
    python fix_gender.py --apply            # Apply fixes to ru.csv
    python fix_gender.py --output fixed.csv # Save to different file
    python fix_gender.py --confidence 0.7   # Higher confidence threshold
"""

import argparse
import csv
import json
import shutil
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

from src.gender_fixer import GenderFixer, GenderFix, Gender

console = Console()


def backup_file(file_path: Path) -> Path | None:
    """Create backup of a file."""
    if not file_path.exists():
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = file_path.with_suffix(f".gender_backup_{timestamp}.csv")
    shutil.copy2(file_path, backup_path)
    return backup_path


def count_csv_rows(csv_path: Path) -> int:
    """Count rows in CSV file."""
    with open(csv_path, encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f) - 1  # Subtract header


def process_with_progress(
    input_csv: Path,
    output_csv: Path | None,
    min_confidence: float,
    apply: bool,
) -> list[GenderFix]:
    """Process CSV with progress bar."""
    
    total_rows = count_csv_rows(input_csv)
    fixer = GenderFixer(min_confidence=min_confidence)
    fixes: list[GenderFix] = []
    rows = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Processing...", total=total_rows)
        
        with open(input_csv, encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.DictReader(f, delimiter=";")
            fieldnames = reader.fieldnames
            
            for row in reader:
                fix = fixer.fix_entry(
                    entry_id=row.get("ID", ""),
                    russian=row.get("Russian", ""),
                    english=row.get("English", ""),
                    chinese=row.get("Original", ""),
                )
                
                if fix:
                    fixes.append(fix)
                    if apply:
                        row["Russian"] = fix.fixed
                
                rows.append(row)
                progress.advance(task)
    
    # Write if applying
    if apply and fixes:
        out_path = output_csv or input_csv
        with open(out_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
            writer.writeheader()
            writer.writerows(rows)
    
    # Store stats
    process_with_progress.stats = fixer.get_stats()
    
    return fixes


def main():
    parser = argparse.ArgumentParser(
        description="Fix grammatical gender in Russian translations"
    )
    parser.add_argument(
        "--input", "-i",
        default="data/translated/ru.csv",
        help="Input CSV file (default: data/translated/ru.csv)"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output CSV file (default: same as input)"
    )
    parser.add_argument(
        "--apply", "-a",
        action="store_true",
        help="Apply fixes (otherwise dry run)"
    )
    parser.add_argument(
        "--confidence", "-c",
        type=float,
        default=0.5,
        help="Minimum confidence threshold (0.0-1.0, default: 0.5)"
    )
    parser.add_argument(
        "--show-all", "-s",
        action="store_true",
        help="Show all fixes in preview"
    )
    parser.add_argument(
        "--export-json", "-j",
        default=None,
        help="Export fixes to JSON file for review"
    )
    
    args = parser.parse_args()
    
    console.print("\n[bold cyan]═══ Gender Fixer ═══[/bold cyan]\n")
    
    input_csv = Path(args.input)
    output_csv = Path(args.output) if args.output else None
    
    if not input_csv.exists():
        console.print(f"[red]Error: Input file not found: {input_csv}[/red]")
        return 1
    
    # Show config
    config_table = Table(title="Configuration")
    config_table.add_column("Parameter", style="cyan")
    config_table.add_column("Value", style="green")
    
    config_table.add_row("Input", str(input_csv))
    config_table.add_row("Output", str(output_csv or input_csv))
    config_table.add_row("Mode", "Apply" if args.apply else "Dry Run (preview)")
    config_table.add_row("Min Confidence", f"{args.confidence:.0%}")
    
    console.print(config_table)
    console.print()
    
    # Backup if applying
    if args.apply:
        console.print("[bold]Creating backup...[/bold]")
        backup = backup_file(input_csv)
        if backup:
            console.print(f"  Backup: {backup.name}")
        console.print()
    
    # Process
    console.print("[bold]Processing translations...[/bold]")
    fixes = process_with_progress(
        input_csv,
        output_csv,
        args.confidence,
        args.apply,
    )
    console.print()
    
    # Stats
    stats = process_with_progress.stats
    
    stats_table = Table(title="Statistics")
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Value", style="green")
    
    stats_table.add_row("Processed", f"{stats['processed']:,}")
    stats_table.add_row("Fixed", f"{stats['fixed']:,}")
    stats_table.add_row("Verbs changed", f"{stats['verbs_changed']:,}")
    stats_table.add_row("Adjectives changed", f"{stats['adjectives_changed']:,}")
    stats_table.add_row("Skipped (no gender)", f"{stats['skipped_no_gender']:,}")
    stats_table.add_row("Skipped (low confidence)", f"{stats['skipped_low_confidence']:,}")
    
    console.print(stats_table)
    console.print()
    
    # Preview fixes
    if fixes:
        preview_count = len(fixes) if args.show_all else min(20, len(fixes))
        
        console.print(f"[bold]Sample fixes ({preview_count} of {len(fixes)}):[/bold]\n")
        
        for i, fix in enumerate(fixes[:preview_count]):
            gender_str = "♂" if fix.detected_gender == Gender.MALE else "♀"
            conf_str = f"{fix.confidence:.0%}"
            
            console.print(f"[dim]{fix.entry_id}[/dim] [{gender_str} {conf_str}]")
            console.print(f"  [red]- {fix.original}[/red]")
            console.print(f"  [green]+ {fix.fixed}[/green]")
            console.print(f"  [dim]Changes: {fix.changes}[/dim]")
            console.print()
        
        if len(fixes) > preview_count:
            console.print(f"[dim]... and {len(fixes) - preview_count} more fixes[/dim]\n")
    else:
        console.print("[yellow]No fixes needed![/yellow]\n")
    
    # Export to JSON if requested
    if args.export_json and fixes:
        export_data = [
            {
                "id": f.entry_id,
                "original": f.original,
                "fixed": f.fixed,
                "changes": f.changes,
                "gender": f.detected_gender.name,
                "confidence": f.confidence,
            }
            for f in fixes
        ]
        
        export_path = Path(args.export_json)
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        console.print(f"[green]Exported {len(fixes)} fixes to {export_path}[/green]\n")
    
    # Summary
    if args.apply and fixes:
        console.print(f"[bold green]✓ Applied {len(fixes)} gender fixes![/bold green]")
    elif fixes:
        console.print("[yellow]This was a dry run. Use --apply to apply fixes.[/yellow]")
    
    return 0


if __name__ == "__main__":
    exit(main())

