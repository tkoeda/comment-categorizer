# combine_clean.py
import pandas as pd
import glob
import logging
from rich.console import Console
from fugashi import Tagger

console = Console()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def combine_excel(input_glob, output_file):
    excel_files = glob.glob(input_glob)
    if not excel_files:
        logger.warning(f"No Excel files found in {input_glob}")
        return None

    dfs = []
    last_sheet = None
    last_df = None
    for file in excel_files:
        try:
            xls = pd.ExcelFile(file)
        except Exception as e:
            logger.error(f"Failed to read file {file}: {e}")
            continue

        # Loop through all sheets and extract the "id" (if exists) and "コメント" column.
        for sheet in xls.sheet_names:
            try:
                header_df = pd.read_excel(xls, sheet_name=sheet, nrows=0)
                usecols = ["id", "コメント"] if "id" in header_df.columns else ["コメント"]
                df = pd.read_excel(xls, sheet_name=sheet, usecols=usecols)
                dfs.append(df)
                last_sheet = sheet
                last_df = df
            except Exception as e:
                logger.error(f"Error reading sheet '{sheet}' in {file}: {e}")
                continue

    if not dfs:
        logger.warning("No data extracted from any sheets.")
        return None

    merged_df = pd.concat(dfs).drop_duplicates().reset_index(drop=True)
    if "id" not in merged_df.columns:
        merged_df.insert(0, "id", merged_df.index + 1)

    # For display purposes:
    if last_sheet is not None and last_df is not None:
        console.print(f"[bold blue]Last Sheet Processed:[/bold blue] {last_sheet}")
        console.print(f"[green]Number of rows (last file):[/green] {last_df.shape[0]}")
        console.print(f"[green]Column names (last file):[/green] {last_df.columns.tolist()}")
    # Use output_dir as the base directory.
    try:
        merged_df.to_excel(output_file, index=False)
        logger.info(f"Merge complete. Saved as '{output_file}'.")
    except Exception as e:
        logger.error(f"Error saving merged file: {e}")


def normalize_text(text):
    """Normalize text using NFKC normalization."""
    import unicodedata

    return unicodedata.normalize("NFKC", text)


def clean_japanese_text(text, allowed_pos=None, stopwords=None):
    """
    Clean Japanese text using normalization, tokenization, and filtering.
    """
    if allowed_pos is None:
        allowed_pos = {"名詞", "形容詞", "動詞", "副詞", "助詞"}
    if stopwords is None:
        stopwords = set()

    normalized = normalize_text(text)

    tagger = Tagger()
    tokens = tagger(normalized)
    filtered_tokens = [
        token.surface for token in tokens if token.feature.pos1 in allowed_pos and token.surface not in stopwords
    ]
    return " ".join(filtered_tokens)


def get_removed(original, cleaned):
    """
    Return the characters that were removed from the original text.
    """
    import difflib

    diff = difflib.ndiff(list(original), list(cleaned))
    removed_chars = [token[2:] for token in diff if token.startswith("- ")]
    return "".join(removed_chars)


def clean_excel_file(input_path, output_path):
    """
    Reads the Excel file at input_path, applies cleaning to the "コメント" column on every sheet,
    and writes the cleaned data to output_path.
    """
    xls = pd.ExcelFile(input_path)
    with pd.ExcelWriter(output_path) as writer:
        for sheet in xls.sheet_names:
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
                if "id" not in df.columns:
                    df.insert(0, "id", range(1, len(df) + 1))
                else:
                    # Optionally, reassign the id to ensure uniqueness.
                    df["id"] = range(1, len(df) + 1)
                # Keep only the cleaned comment and removed text columns, plus id.
                df = df[["id", "コメント_cleaned", "Removed"]]
                df.rename(columns={"コメント_cleaned": "コメント"}, inplace=True)
            df.to_excel(writer, sheet_name=sheet, index=False)
    console.print(f"[bold green]Cleaned Excel file saved to:[/bold green] {output_path}")
