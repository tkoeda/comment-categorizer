import argparse
import difflib
import os
import unicodedata
import glob

import pandas as pd
from fugashi import Tagger
from tqdm import tqdm
from rich.console import Console

console = Console()

tagger = Tagger()


def normalize_text(text):
    """Normalize text using NFKC normalization."""
    return unicodedata.normalize("NFKC", text)


def clean_japanese_text(text, allowed_pos=None, stopwords=None):
    """
    Clean Japanese text using normalization, tokenization, and filtering.
    """
    if allowed_pos is None:
        allowed_pos = {"名詞", "形容詞", "動詞"}
    if stopwords is None:
        stopwords = set()

    normalized = normalize_text(text)
    tokens = tagger(normalized)
    filtered_tokens = [
        token.surface for token in tokens if token.feature.pos1 in allowed_pos and token.surface not in stopwords
    ]
    return " ".join(filtered_tokens)


def get_removed(original, cleaned):
    """
    Return the characters that were removed from the original text.
    """
    diff = difflib.ndiff(list(original), list(cleaned))
    removed_chars = [token[2:] for token in diff if token.startswith("- ")]
    return "".join(removed_chars)


def clean_excel_file(input_path, output_path):
    """
    Reads the Excel file at input_path, applies cleaning to the "コメント" column
    on every sheet, and writes the cleaned data to output_path.
    """
    xls = pd.ExcelFile(input_path)
    with pd.ExcelWriter(output_path) as writer:
        for sheet in tqdm(xls.sheet_names, desc=f"Processing sheets in {os.path.basename(input_path)}"):
            df = pd.read_excel(xls, sheet_name=sheet)

            console.print(f"[bold blue]Sheet:[/bold blue] {sheet}")
            console.print(f"[green]Number of rows:[/green] {df.shape[0]}")
            console.print(f"[green]Column names:[/green] {df.columns.tolist()}")

            if any(col == "コメント" for col in df.columns):
                df["コメント_cleaned"] = df["コメント"].apply(
                    lambda x: clean_japanese_text(str(x)) if pd.notna(x) else x
                )
                df["Removed"] = df.apply(
                    lambda row: get_removed(str(row["コメント"]), row["コメント_cleaned"])
                    if pd.notna(row["コメント"])
                    else "",
                    axis=1,
                )
                if "id" in df.columns:
                    df = df[["id", "コメント_cleaned", "Removed"]]
                    df.rename(columns={"コメント_cleaned": "コメント"}, inplace=True)
                else:
                    df = df[["コメント_cleaned", "Removed"]]
                    df.rename(columns={"コメント_cleaned": "コメント"}, inplace=True)
            df.to_excel(writer, sheet_name=sheet, index=False)

    console.print(f"[bold green]Cleaned Excel file saved to:[/bold green] {output_path}")


def process_all_files(input_dir, output_dir, type):
    """
    Process all Excel files in the input directory and save cleaned files
    to the output directory.
    """
    os.makedirs(output_dir, exist_ok=True)
    # Find all Excel files in the input directory
    input_files = glob.glob(os.path.join(input_dir))
    if not input_files:
        console.print(f"[red]No Excel files found in directory:[/red] {input_dir}")
        return
        return

    for input_file in input_files:
        # base_filename = os.path.basename(input_file)
        output_file = os.path.join(output_dir, f"{type}_processed.xlsx")
        console.print(f"[yellow]Processing {input_file}...[/yellow]")
        clean_excel_file(input_file, output_file)


def main():
    parser = argparse.ArgumentParser(
        description="Clean Japanese text in all Excel files in a directory and show what was removed."
    )
    parser.add_argument("--type", required=True, help="Type of file to combine (e.g., 'past' or 'new')")
    args = parser.parse_args()

    input_dir = os.path.join("data", f"{args.type}_intermediate", "*.xlsx")
    output_dir = os.path.join("data", f"{args.type}_processed")

    process_all_files(input_dir, output_dir, args.type)


if __name__ == "__main__":
    main()
