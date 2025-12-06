#!/usr/bin/env python3
"""
WWM Translator - Where Winds Meet Neural Translation Tool

CLI interface for extracting and translating game localization files.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click
from rich.table import Table

from src.config import AppConfig, EnvConfig, init_config
from src.extractor import extract_game_locale
from src.models import ErrorMarkers
from src.utils import (
    confirm,
    console,
    format_size,
    print_banner,
    print_error,
    print_success,
    print_warning,
    setup_logging,
)


logger = logging.getLogger("wwm_translator")


@click.group()
@click.option("--config", "-c", default="config.yaml", help="Config file path")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.pass_context
def cli(ctx: click.Context, config: str, verbose: bool) -> None:
    """WWM Translator - Neural translation for Where Winds Meet"""
    ctx.ensure_object(dict)

    try:
        app_config, env_config = init_config(config)
        ctx.obj["config"] = app_config
        ctx.obj["env"] = env_config

        level = "DEBUG" if verbose else app_config.logging.level
        setup_logging(
            level=level,
            log_file=app_config.logging.file,
            log_to_console=app_config.logging.console,
        )

    except FileNotFoundError as e:
        print_error(str(e))
        sys.exit(1)


@cli.command()
@click.option("--language", "-l", help="Language to extract (zh_cn, en, etc.)")
@click.option("--all", "-a", "all_langs", is_flag=True, help="Extract all languages")
@click.pass_context
def extract(ctx: click.Context, language: str | None, all_langs: bool) -> None:
    """Extract texts from game binary files to CSV"""
    print_banner()

    config: AppConfig = ctx.obj["config"]
    locale_dir = config.paths.game_locale_dir

    if not locale_dir.exists():
        print_error(f"Game locale directory not found: {locale_dir}")
        return

    # Find available languages
    languages = [
        (f.name.replace("translate_words_map_", ""), f)
        for f in locale_dir.iterdir()
        if f.name.startswith("translate_words_map_") and f.is_file()
    ]

    if not languages:
        print_error("No locale files found")
        return

    # Display available
    console.print("[bold]Available languages:[/bold]")
    for code, path in languages:
        size = format_size(path.stat().st_size)
        console.print(f"  - {code}: {path.name} ({size})")
    console.print()

    # Select languages to extract
    if all_langs:
        to_extract = languages
    elif language:
        to_extract = [(c, p) for c, p in languages if c == language]
        if not to_extract:
            print_error(f"Language '{language}' not found")
            console.print(f"Available: {', '.join(c for c, _ in languages)}")
            return
    else:
        # Default: configured languages
        configured = {config.languages.original, config.languages.source}
        to_extract = [(c, p) for c, p in languages if c in configured]

    # Extract
    output_dir = config.paths.source_dir

    for lang_code, locale_file in to_extract:
        console.print(f"[bold cyan]Extracting {lang_code}...[/bold cyan]")

        result = extract_game_locale(
            locale_file,
            output_dir,
            log_callback=lambda msg: logger.debug(msg),
        )

        if result.success:
            csv_file = output_dir / "csv" / f"{lang_code}.csv"
            csv_size = format_size(csv_file.stat().st_size) if csv_file.exists() else "?"
            print_success(
                f"{lang_code}: {result.files_extracted} files, "
                f"{result.texts_extracted:,} texts ({csv_size})"
            )
        else:
            print_error(f"{lang_code}: {result.message}")

    console.print()
    print_success("Extraction complete!")


@cli.command()
@click.option("--resume/--no-resume", default=True, help="Resume previous translation")
@click.option("--batch-size", "-b", type=int, help="Override batch size")
@click.option("--verbose", "-V", is_flag=True, help="Show detailed batch info")
@click.pass_context
def translate(ctx: click.Context, resume: bool, batch_size: int | None, verbose: bool) -> None:
    """Translate extracted texts using LLM"""
    print_banner()

    from src.batch_processor import BatchProcessor
    from src.llm_client import LLMClient, PromptBuilder

    config: AppConfig = ctx.obj["config"]
    env_config: EnvConfig = ctx.obj["env"]

    if batch_size:
        config.batch.size = batch_size

    # Check files
    source_csv = config.get_source_csv()
    original_csv = config.get_original_csv()
    output_csv = config.get_output_csv()

    if not source_csv.exists():
        print_error(f"Source file not found: {source_csv}")
        console.print("Run 'extract' command first")
        return

    # Show config
    table = Table(title="Translation Configuration")
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Source", f"{config.languages.source} ({source_csv.name})")
    table.add_row(
        "Context",
        f"{config.languages.original} ({original_csv.name if original_csv.exists() else 'N/A'})",
    )
    table.add_row("Target", config.languages.target)
    table.add_row("LLM", f"{config.llm.provider}/{config.llm.model}")
    table.add_row("Batch size", str(config.batch.size))
    table.add_row("Resume", str(resume))

    console.print(table)
    console.print()

    # Check API key
    api_key = env_config.get_api_key(config.llm.provider)
    if not api_key:
        print_error(f"API key not set for {config.llm.provider}")
        console.print("Set it in .env file")
        return

    # Initialize
    console.print("[bold]Initializing...[/bold]")

    try:
        llm_client = LLMClient(config.llm, env_config)
        prompt_builder = PromptBuilder(config.paths.rules_dir).load()

        def on_progress(progress):
            pass

        def log_output(msg: str):
            # Use print for immediate output, handle encoding errors
            try:
                print(msg, flush=True)
            except UnicodeEncodeError:
                # Replace non-ASCII chars for Windows console
                safe_msg = msg.encode("ascii", errors="replace").decode("ascii")
                print(safe_msg, flush=True)

        processor = BatchProcessor(
            config=config,
            env_config=env_config,
            llm_client=llm_client,
            prompt_builder=prompt_builder,
            progress_callback=on_progress,
            log_callback=log_output,
            verbose=verbose,
        )

        print_success("Components ready")
        console.print()

        # Run
        console.print("[bold cyan]Starting translation...[/bold cyan]")
        console.print()

        progress = processor.process_sync(
            source_csv=source_csv,
            original_csv=original_csv,
            output_csv=output_csv,
            resume=resume,
        )

        # Results
        console.print()
        result_table = Table(title="Results")
        result_table.add_column("Metric", style="cyan")
        result_table.add_column("Value", style="green")

        result_table.add_row("Total", str(progress.total_entries))
        result_table.add_row("Translated", str(progress.translated_entries))
        result_table.add_row("Skipped", str(progress.skipped_entries))
        result_table.add_row("Errors", str(progress.error_entries))
        result_table.add_row("Progress", f"{progress.progress_percent:.1f}%")

        console.print(result_table)
        console.print()
        print_success(f"Results saved to: {output_csv}")

    except Exception as e:
        print_error(str(e))
        logger.exception("Translation failed")


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show translation progress status"""
    config: AppConfig = ctx.obj["config"]
    print_banner()

    # Directories
    console.print("[bold]Directories:[/bold]")
    console.print(f"  Game locale: {config.paths.game_locale_dir}")
    console.print(f"  Work dir: {config.paths.work_dir}")
    console.print()

    # Extraction status
    console.print("[bold]Extraction:[/bold]")
    csv_dir = config.paths.source_dir / "csv"

    if csv_dir.exists():
        for csv_file in sorted(csv_dir.glob("*.csv")):
            size = format_size(csv_file.stat().st_size)
            lines = sum(1 for _ in open(csv_file, encoding="utf-8")) - 1
            print_success(f"{csv_file.name}: {lines:,} entries ({size})")
    else:
        print_warning("Not extracted yet")

    console.print()

    # Translation progress
    console.print("[bold]Translation:[/bold]")
    progress_dir = config.paths.progress_dir

    if progress_dir.exists():
        import json

        for pf in progress_dir.glob("*_progress.json"):
            try:
                data = json.loads(pf.read_text(encoding="utf-8"))
                total = data.get("total_entries", 0)
                done = data.get("translated_entries", 0)
                pct = (done / total * 100) if total else 0
                console.print(f"  {pf.stem}: {pct:.1f}% ({done:,}/{total:,})")
            except Exception as e:
                print_error(f"{pf}: {e}")
    else:
        print_warning("No active translations")

    console.print()

    # Config summary
    console.print("[bold]Configuration:[/bold]")
    console.print(f"  Source: {config.languages.source}")
    console.print(f"  Context: {config.languages.original}")
    console.print(f"  Target: {config.languages.target}")
    console.print(f"  LLM: {config.llm.provider}/{config.llm.model}")
    console.print(f"  Batch: {config.batch.size}")


@cli.command()
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def reset(ctx: click.Context, force: bool) -> None:
    """Reset translation progress"""
    config: AppConfig = ctx.obj["config"]

    if not force:
        if not confirm("Reset all translation progress?"):
            console.print("Cancelled")
            return

    progress_dir = config.paths.progress_dir

    # Delete all files in progress directory
    deleted = 0
    if progress_dir.exists():
        for file in progress_dir.glob("*"):
            try:
                file.unlink()
                deleted += 1
            except Exception as e:
                print_error(f"Failed to delete {file}: {e}")

    if deleted > 0:
        print_success(f"Progress reset ({deleted} files deleted)")
    else:
        print_warning("No progress to reset")


@cli.command()
@click.option("--install", "-i", is_flag=True, help="Install to game folder")
@click.option("--with-diff", "-d", is_flag=True, help="Also patch diff files")
@click.pass_context
def autopatch(ctx: click.Context, install: bool, with_diff: bool) -> None:
    """Auto-patch game files with translations (preserves original file structure)"""
    import csv
    import shutil

    from src.extractor import BinaryExtractor
    from src.hashmap_format import HashMapDatFile

    print_banner()
    config: AppConfig = ctx.obj["config"]

    patch_lang = config.languages.patch_lang  # e.g. "de"
    source_lang = config.languages.source  # e.g. "en"
    target_lang = config.languages.target  # e.g. "ru"
    game_locale_dir = config.paths.game_locale_dir

    console.print("[bold]Autopatch Configuration:[/bold]")
    console.print(f"  Source language: {source_lang}")
    console.print(f"  Target language: {target_lang}")
    console.print(f"  Patching into: {patch_lang} (game will show {target_lang} when {patch_lang} selected)")
    console.print()

    source_dat_dir = config.paths.source_dir / "dat" / source_lang
    translated_csv = config.get_output_csv()
    source_csv = config.get_source_csv()

    if not source_dat_dir.exists():
        print_error(f"Source .dat files not found: {source_dat_dir}")
        console.print("Run 'extract' command first")
        return

    if not translated_csv.exists():
        print_error(f"Translations not found: {translated_csv}")
        console.print("Run 'translate' command first")
        return

    # Load English originals from source CSV (fallback for untranslated)
    console.print("[bold]Loading source texts...[/bold]")
    english_texts: dict[str, str] = {}
    if source_csv.exists():
        with open(source_csv, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                if row.get("OriginalText"):
                    # Unescape newlines
                    text = row["OriginalText"].replace("\\n", "\n").replace("\\r", "\r")
                    english_texts[row["ID"]] = text
        console.print(f"  Loaded {len(english_texts):,} English source texts")

    # Load translations (ID -> Russian text) - only translated ones
    console.print("[bold]Loading translations...[/bold]")
    translations: dict[str, str] = {}
    untranslated_count = 0
    with open(translated_csv, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            text_id = row["ID"]
            if row.get("Status") == "translated" and row.get("Russian"):
                # Use Russian translation
                text = row["Russian"].replace("\\n", "\n").replace("\\r", "\r")
                translations[text_id] = text
            elif text_id in english_texts:
                # Use English original for pending/error/skipped/empty
                translations[text_id] = english_texts[text_id]
                untranslated_count += 1

    console.print(f"  Loaded {len(translations) - untranslated_count:,} Russian translations")
    console.print(f"  Using {untranslated_count:,} English fallbacks for untranslated strings")
    console.print()

    def patch_dat_files(source_dir: Path, output_name: str) -> Path | None:
        """Patch .dat files preserving original structure."""
        console.print(f"[bold]Patching: {source_dir.name} -> {output_name}[/bold]")

        packed_dir = config.paths.translated_dir / f"packed_{output_name}"
        packed_dir.mkdir(parents=True, exist_ok=True)

        # Clean previous
        for f in packed_dir.glob("*.dat"):
            f.unlink()

        files_count = 0
        texts_patched = 0

        for dat_file in sorted(source_dir.glob("*.dat")):
            data = dat_file.read_bytes()
            parser = HashMapDatFile()

            if parser.read(data) and parser.entries:
                # Apply translations
                file_patched = 0
                for entry in parser.entries:
                    if entry.id_hex in translations:
                        entry.text = translations[entry.id_hex]
                        file_patched += 1

                if file_patched > 0:
                    new_data = parser.write()
                    texts_patched += file_patched
                else:
                    new_data = data
            else:
                # Can't parse or empty - copy as-is
                new_data = data

            (packed_dir / dat_file.name).write_bytes(new_data)
            files_count += 1

        console.print(f"  Patched: {files_count} files ({texts_patched:,} texts replaced)")

        # Create archive
        output_file = config.paths.translated_dir / f"translate_words_map_{output_name}"
        binary_extractor = BinaryExtractor()
        archive_result = binary_extractor.pack(packed_dir, output_file)

        if not archive_result.success:
            print_error(f"Archive failed: {archive_result.message}")
            return None

        size = format_size(output_file.stat().st_size)
        console.print(f"  Archive: {output_file.name} ({size})")
        console.print()

        return output_file

    # Patch main file
    main_output = patch_dat_files(source_dat_dir, patch_lang)

    # Patch diff file if requested
    diff_output = None
    if with_diff:
        diff_dat_dir = config.paths.source_dir / "dat" / f"{source_lang}_diff"
        if diff_dat_dir.exists():
            # Load English texts from diff CSV for fallback
            diff_source_csv = config.paths.source_dir / "csv" / f"{source_lang}_diff.csv"
            if diff_source_csv.exists():
                console.print("[bold]Loading diff source texts...[/bold]")
                with open(diff_source_csv, encoding="utf-8", newline="") as f:
                    reader = csv.DictReader(f, delimiter=";")
                    diff_english_count = 0
                    for row in reader:
                        if row.get("OriginalText"):
                            text = row["OriginalText"].replace("\\n", "\n").replace("\\r", "\r")
                            text_id = row["ID"]
                            # Add to english_texts if not already present
                            if text_id not in english_texts:
                                english_texts[text_id] = text
                                diff_english_count += 1
                            # Also add to translations if not translated
                            if text_id not in translations:
                                translations[text_id] = text
                    console.print(f"  Loaded {diff_english_count:,} diff English texts")
                console.print()
            
            diff_output = patch_dat_files(diff_dat_dir, f"{patch_lang}_diff")
        else:
            print_warning(f"Diff .dat files not found: {diff_dat_dir}")
            console.print("  Run 'python main.py extract-diff' first")

    # Install to game folder
    if install and main_output:
        console.print("[bold]Installing to game...[/bold]")
        try:
            dest = game_locale_dir / main_output.name
            shutil.copy2(main_output, dest)
            print_success(f"Installed: {dest}")

            if diff_output and diff_output.exists():
                dest_diff = game_locale_dir / diff_output.name
                shutil.copy2(diff_output, dest_diff)
                print_success(f"Installed: {dest_diff}")

        except Exception as e:
            print_error(f"Install failed: {e}")
    elif main_output:
        console.print("[bold]To install manually:[/bold]")
        console.print(f"  Copy files from '{config.paths.translated_dir}' to:")
        console.print(f"  '{game_locale_dir}'")
        console.print()
        console.print("Or run: python main.py autopatch --install")

    console.print()
    print_success("Autopatch complete!")
    console.print()
    console.print(f"[bold yellow]In game: Select '{patch_lang.upper()}' language to see {target_lang.upper()} translations[/bold yellow]")


@cli.command("extract-diff")
@click.pass_context
def extract_diff(ctx: click.Context) -> None:
    """Extract diff files (updates/patches) for translation"""
    from src.extractor import BinaryExtractor, TextExtractor

    print_banner()
    config: AppConfig = ctx.obj["config"]

    game_locale_dir = config.paths.game_locale_dir
    if not game_locale_dir.exists():
        print_error(f"Game locale dir not found: {game_locale_dir}")
        return

    # Show all locale files
    console.print("[bold]Locale files in game:[/bold]")
    console.print()

    for f in sorted(game_locale_dir.iterdir()):
        size = format_size(f.stat().st_size)
        is_diff = "_diff" in f.name
        marker = "[yellow]*[/yellow]" if is_diff else " "
        console.print(f"  {marker} {f.name}: {size}")

    console.print()
    console.print("[yellow]*[/yellow] = diff file (updates/patches)")
    console.print()

    # Extract source language diff
    source_lang = config.languages.source
    diff_file = game_locale_dir / f"translate_words_map_{source_lang}_diff"
    
    if not diff_file.exists():
        print_warning(f"No diff file found: {diff_file.name}")
        return

    console.print(f"[bold]Extracting: {diff_file.name}...[/bold]")
    
    output_dir = config.paths.source_dir / "dat" / f"{source_lang}_diff"
    output_dir.mkdir(parents=True, exist_ok=True)

    extractor = BinaryExtractor(log_callback=lambda msg: logger.debug(msg))
    result = extractor.extract(diff_file, output_dir)

    if not result.success:
        print_error(f"Extraction failed: {result.message}")
        return

    print_success(f"Extracted {result.files_extracted} .dat files")

    # Extract texts
    text_extractor = TextExtractor()
    csv_file = config.paths.source_dir / "csv" / f"{source_lang}_diff.csv"
    text_result = text_extractor.extract(output_dir, csv_file)
    
    if text_result.success:
        print_success(f"Extracted {text_result.texts_extracted:,} texts to {csv_file.name}")
        console.print()
        console.print("[bold]Next steps:[/bold]")
        console.print("  1. Translate diff texts (they will be included automatically)")
        console.print("  2. Run: python main.py autopatch --install --with-diff")
    else:
        print_warning(f"No translatable texts in diff")


@cli.command()
@click.option("--fix", "-f", is_flag=True, help="Mark invalid translations for re-translation")
@click.option("--check-broken/--no-check-broken", default=True, help="Also check for broken/corrupted strings")
@click.pass_context
def validate(ctx: click.Context, fix: bool, check_broken: bool) -> None:
    """Validate translations - check symbols, broken strings, and other issues"""
    import csv
    import re

    from src.issue_fixer import BrokenStringDetector

    print_banner()
    config: AppConfig = ctx.obj["config"]

    source_csv = config.get_source_csv()
    translated_csv = config.get_output_csv()

    if not source_csv.exists():
        print_error(f"Source CSV not found: {source_csv}")
        return

    if not translated_csv.exists():
        print_error(f"Translations not found: {translated_csv}")
        return

    console.print("[bold]Validating translations...[/bold]")
    console.print()

    # Universal pattern to find any special sequences
    special_pattern = re.compile(
        r'\{[^}]*\}'       # {0}, {name}, {count:d}, etc.
        r'|<[^>]*>'        # <color>, </b>, <img src="x">, etc.
        r'|\[[^\]]*\]'     # [item], [npc_name], etc.
        r'|%[a-zA-Z]'      # %s, %d, %f, etc.
        r'|\\[nrt]'        # \n, \r, \t
        r'|&[a-zA-Z]+;'    # &nbsp;, &amp;, etc.
    )

    def extract_specials(text: str) -> list[str]:
        """Extract all special sequences from text."""
        return special_pattern.findall(text)

    # Load source texts
    source_texts: dict[str, str] = {}
    with open(source_csv, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            source_texts[row["ID"]] = row["OriginalText"]

    # Initialize broken string detector
    broken_detector = BrokenStringDetector() if check_broken else None

    # Validate translations
    symbol_issues: list[dict] = []
    broken_issues: list[dict] = []
    valid_count = 0
    total_count = 0
    rows_to_fix: set[str] = set()

    # Track issue types
    issue_type_counts: dict[str, int] = {}

    with open(translated_csv, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            if row.get("Status") != "translated" or not row.get("Russian"):
                continue

            total_count += 1
            text_id = row["ID"]
            original = source_texts.get(text_id, row.get("English", ""))
            translated = row["Russian"]
            has_issue = False

            # Check for error markers (incomplete LLM responses)
            if ErrorMarkers.contains_error(translated):
                symbol_issues.append({
                    "id": text_id,
                    "type": "error_marker",
                    "mismatches": ["Contains error marker - incomplete LLM response"],
                    "original": original[:150],
                    "translated": translated[:150],
                })
                rows_to_fix.add(text_id)
                issue_type_counts["error_marker"] = issue_type_counts.get("error_marker", 0) + 1
                has_issue = True
            else:
                # Check for broken strings (critical only)
                if broken_detector:
                    broken = broken_detector.get_critical_issues(original, translated)
                    if broken:
                        broken_issues.append({
                            "id": text_id,
                            "type": broken[0].issue_type,
                            "issues": broken,
                            "original": original[:150],
                            "translated": translated[:150],
                        })
                        rows_to_fix.add(text_id)
                        for b in broken:
                            issue_type_counts[b.issue_type] = issue_type_counts.get(b.issue_type, 0) + 1
                        has_issue = True

                # Extract special sequences
                orig_specials = extract_specials(original)
                trans_specials = extract_specials(translated)

                # Compare counts of each unique special
                orig_counts: dict[str, int] = {}
                for s in orig_specials:
                    orig_counts[s] = orig_counts.get(s, 0) + 1

                trans_counts: dict[str, int] = {}
                for s in trans_specials:
                    trans_counts[s] = trans_counts.get(s, 0) + 1

                # Find mismatches
                all_specials = set(orig_counts.keys()) | set(trans_counts.keys())
                mismatches = []

                for special in all_specials:
                    orig_n = orig_counts.get(special, 0)
                    trans_n = trans_counts.get(special, 0)
                    if orig_n != trans_n:
                        mismatches.append(f"'{special}': {orig_n} -> {trans_n}")

                if mismatches:
                    symbol_issues.append({
                        "id": text_id,
                        "type": "symbol_mismatch",
                        "mismatches": mismatches,
                        "original": original[:150],
                        "translated": translated[:150],
                    })
                    rows_to_fix.add(text_id)
                    issue_type_counts["symbol_mismatch"] = issue_type_counts.get("symbol_mismatch", 0) + 1
                    has_issue = True

            if not has_issue:
                valid_count += 1

    all_issues = symbol_issues + broken_issues

    # Report
    console.print("[bold]Results:[/bold]")
    console.print(f"  Total checked: {total_count:,}")
    console.print(f"  Valid: {valid_count:,}")
    console.print(f"  Issues found: {len(all_issues):,}")
    console.print()

    if issue_type_counts:
        console.print("[bold]Issue breakdown:[/bold]")
        type_names = {
            "error_marker": "Error markers ([MISSING], [PARSE ERROR])",
            "symbol_mismatch": "Symbol count mismatch",
            "json_artifact": "JSON artifacts",
            "encoding_error": "Encoding errors",
            "empty_translation": "Empty translations",
            "truncated": "Truncated translations",
            "untranslated": "Untranslated text",
            "repetition": "Repeated content",
        }
        for t, count in sorted(issue_type_counts.items(), key=lambda x: -x[1]):
            name = type_names.get(t, t)
            console.print(f"  {name}: {count:,}")
        console.print()

    if all_issues:
        # Save issues to file
        issues_file = config.paths.translated_dir / "validation_issues.csv"
        with open(issues_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["ID", "Type", "Mismatches", "Original", "Translated"])

            for issue in symbol_issues:
                writer.writerow([
                    issue["id"],
                    issue["type"],
                    " | ".join(issue["mismatches"]),
                    issue["original"],
                    issue["translated"],
                ])
            
            for issue in broken_issues:
                writer.writerow([
                    issue["id"],
                    issue["type"],
                    " | ".join(str(i) for i in issue["issues"]),
                    issue["original"],
                    issue["translated"],
                ])

        print_warning(f"Issues saved to: {issues_file}")

        # Show sample issues
        if symbol_issues:
            console.print()
            console.print("[bold]Sample symbol issues:[/bold]")
            for issue in symbol_issues[:3]:
                console.print(f"  [yellow]{issue['id']}[/yellow]")
                for m in issue["mismatches"][:2]:
                    console.print(f"    {m}")

        if broken_issues:
            console.print()
            console.print("[bold]Sample broken strings:[/bold]")
            for issue in broken_issues[:3]:
                console.print(f"  [red]{issue['id']}[/red] - {issue['type']}")
                console.print(f"    {issue['translated'][:60]}...")

        # Fix mode: mark for re-translation
        if fix and rows_to_fix:
            console.print()
            console.print("[bold]Marking invalid translations for re-translation...[/bold]")

            # Update CSV
            rows = []
            with open(translated_csv, encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f, delimiter=";")
                fieldnames = reader.fieldnames
                rows = list(reader)

            fixed = 0
            for row in rows:
                if row["ID"] in rows_to_fix:
                    row["Status"] = "needs_retranslation"
                    fixed += 1

            with open(translated_csv, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
                writer.writeheader()
                writer.writerows(rows)

            # Also remove from progress tracker (JSON files)
            import json
            progress_dir = config.paths.progress_dir
            translations_file = progress_dir / f"{source_csv.stem}_translations.json"
            
            if translations_file.exists():
                try:
                    tracker_data = json.loads(translations_file.read_text(encoding="utf-8"))
                    removed = 0
                    for entry_id in rows_to_fix:
                        if entry_id in tracker_data:
                            del tracker_data[entry_id]
                            removed += 1
                    
                    translations_file.write_text(
                        json.dumps(tracker_data, ensure_ascii=False, indent=2),
                        encoding="utf-8"
                    )
                    console.print(f"  Removed {removed:,} from progress tracker")
                except Exception as e:
                    print_warning(f"Could not update progress tracker: {e}")

            print_success(f"Marked {fixed:,} translations for re-translation")
            console.print("Run 'translate' again to re-translate them")
    else:
        print_success("All translations are valid!")


@cli.command("fix-issues")
@click.option("--batch-size", "-b", type=int, default=5, help="Issues per LLM batch")
@click.option("--limit", "-l", type=int, help="Limit number of issues to process")
@click.option("--dry-run", "-d", is_flag=True, help="Show what would be fixed without applying")
@click.pass_context
def fix_issues(ctx: click.Context, batch_size: int, limit: int | None, dry_run: bool) -> None:
    """Fix validation issues using LLM"""
    print_banner()

    from src.issue_fixer import IssueFixer
    from src.llm_client import LLMClient

    config: AppConfig = ctx.obj["config"]
    env_config: EnvConfig = ctx.obj["env"]

    issues_file = config.paths.translated_dir / "validation_issues.csv"
    translated_csv = config.get_output_csv()

    if not issues_file.exists():
        print_error(f"Issues file not found: {issues_file}")
        console.print("Run 'validate' command first")
        return

    if not translated_csv.exists():
        print_error(f"Translations not found: {translated_csv}")
        return

    # Load issues
    console.print("[bold]Loading validation issues...[/bold]")
    
    try:
        llm_client = LLMClient(config.llm, env_config)
        fixer = IssueFixer(
            llm_client=llm_client,
            batch_size=batch_size,
            log_callback=lambda msg: console.print(msg),
        )
        
        issues = fixer.load_issues(issues_file)
        console.print(f"  Found {len(issues):,} issues")
        
        if limit:
            issues = issues[:limit]
            console.print(f"  Processing first {limit}")
        
        console.print()
        
        # Analyze issue types
        by_type: dict[str, int] = {}
        for issue in issues:
            t = issue.issue_type
            by_type[t] = by_type.get(t, 0) + 1
        
        console.print("[bold]Issue breakdown:[/bold]")
        type_names = {
            "numbered_brackets": "Numbered brackets [1], [2]... (auto-fix)",
            "newline_mismatch": "Newline \\n mismatches",
            "tag_translated": "Game tags translated",
            "placeholder_translated": "Placeholder brackets translated",
            "other": "Other issues",
        }
        for t, count in sorted(by_type.items(), key=lambda x: -x[1]):
            console.print(f"  {type_names.get(t, t)}: {count:,}")
        console.print()
        
        # Fix issues
        console.print("[bold cyan]Fixing issues...[/bold cyan]")
        console.print()
        
        fixes = fixer.fix_issues(issues)
        
        console.print()
        console.print(f"[bold]Total fixes: {len(fixes):,}[/bold]")
        
        if not fixes:
            print_warning("No fixes to apply")
            return
        
        if dry_run:
            console.print()
            console.print("[yellow]DRY RUN - not applying changes[/yellow]")
            console.print()
            console.print("[bold]Sample fixes:[/bold]")
            for id_, fixed in list(fixes.items())[:5]:
                console.print(f"  {id_}: {fixed[:80]}...")
            return
        
        # Apply fixes
        console.print()
        console.print("[bold]Applying fixes...[/bold]")
        updated = fixer.apply_fixes(fixes, translated_csv)
        
        print_success(f"Updated {updated:,} translations in {translated_csv.name}")
        console.print()
        console.print("[bold]Next steps:[/bold]")
        console.print("  1. Run 'validate' again to check remaining issues")
        console.print("  2. Repeat 'fix-issues' if needed")

    except Exception as e:
        print_error(str(e))
        logger.exception("Fix issues failed")


@cli.command("test-llm")
@click.pass_context
def test_llm(ctx: click.Context) -> None:
    """Test LLM connection"""
    print_banner()

    from src.llm_client import LLMClient

    config: AppConfig = ctx.obj["config"]
    env_config: EnvConfig = ctx.obj["env"]

    console.print(f"[bold]Testing {config.llm.provider}/{config.llm.model}...[/bold]")
    console.print()

    try:
        client = LLMClient(config.llm, env_config)

        test_texts = [
            {
                "id": "test",
                "english": "Welcome, young warrior!",
                "original": "(Chinese: Huan ying, shao xia)",
            }
        ]

        system_prompt = (
            "You are translating a martial arts game. "
            'Translate to Russian. Return JSON: ["translation"]'
        )

        result = client.translate_batch_sync(test_texts, system_prompt)

        print_success("LLM connected!")
        console.print(f"  Input EN: {test_texts[0]['english']}")
        console.print(f"  Output RU: {result[0]}")

    except Exception as e:
        # Handle unicode errors in error message
        error_msg = str(e).encode("ascii", errors="replace").decode("ascii")
        print_error(error_msg)


@cli.command("export-web")
@click.option("--limit", "-l", type=int, help="Limit number of entries to export")
@click.pass_context
def export_web(ctx: click.Context, limit: int | None) -> None:
    """Export translations to JSON for GitHub Pages"""
    import csv
    import json

    print_banner()
    config: AppConfig = ctx.obj["config"]

    source_csv = config.get_source_csv()
    original_csv = config.get_original_csv()
    translated_csv = config.get_output_csv()
    docs_dir = Path("docs/data")

    if not translated_csv.exists():
        print_error(f"Translations not found: {translated_csv}")
        return

    docs_dir.mkdir(parents=True, exist_ok=True)

    console.print("[bold]Exporting translations for web...[/bold]")
    console.print()

    # Load source texts (English)
    source_texts: dict[str, str] = {}
    if source_csv.exists():
        with open(source_csv, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                source_texts[row["ID"]] = row["OriginalText"]

    # Load original texts (Chinese)
    original_texts: dict[str, str] = {}
    if original_csv.exists():
        with open(original_csv, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                original_texts[row["ID"]] = row["OriginalText"]

    # Load and export translations
    translations = []
    stats = {
        "total": 0,
        "translated": 0,
        "skipped": 0,
        "pending": 0,
        "issues": 0,
    }

    with open(translated_csv, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            stats["total"] += 1
            
            status = row.get("Status", "")
            if status == "translated":
                stats["translated"] += 1
            elif status == "skipped":
                stats["skipped"] += 1
            elif status == "needs_retranslation":
                stats["issues"] += 1
            else:
                stats["pending"] += 1

            # Export all entries (translated, issues, pending)
            if status != "skipped":
                entry = {
                    "id": row["ID"],
                    "en": source_texts.get(row["ID"], row.get("English", "")),
                    "ru": row.get("Russian", ""),
                    "status": status if status else "pending",
                }
                if zh := original_texts.get(row["ID"]):
                    entry["zh"] = zh
                
                translations.append(entry)
                
                if limit and len(translations) >= limit:
                    break

    # Save translations JSON
    translations_file = docs_dir / "translations.json"
    with open(translations_file, "w", encoding="utf-8") as f:
        json.dump(translations, f, ensure_ascii=False, separators=(",", ":"))

    console.print(f"  Exported {len(translations):,} translations")

    # Save stats JSON
    stats["progress"] = round(stats["translated"] / stats["total"] * 100, 1) if stats["total"] else 0
    stats_file = docs_dir / "stats.json"
    with open(stats_file, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    console.print(f"  Stats: {stats['progress']}% translated")
    console.print()

    print_success(f"Exported to {docs_dir}/")
    console.print()
    console.print("[bold]Files created:[/bold]")
    console.print(f"  - translations.json ({format_size(translations_file.stat().st_size)})")
    console.print(f"  - stats.json")
    console.print()
    console.print("Now commit and push to GitHub, then enable GitHub Pages on /docs folder")


if __name__ == "__main__":
    cli()
