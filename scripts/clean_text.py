#!/usr/bin/env python
import argparse
import difflib
import os
import unicodedata

import pandas as pd
from fugashi import Tagger
from tqdm import tqdm

tagger = Tagger()


def normalize_text(text):
    """Normalize text using NFKC normalization."""
    return unicodedata.normalize("NFKC", text)


def clean_japanese_text(text, allowed_pos=None, stopwords=None):
    """
    Clean Japanese text using normalization, tokenization, and filtering.

    Parameters:
    - text: The original Japanese text.
    - allowed_pos: A set of allowed part-of-speech tags (default: nouns, adjectives, verbs).
    - stopwords: A set of tokens to remove (optional).

    Returns:
    - A cleaned string containing only tokens that meet the criteria.
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
    This function uses difflib.ndiff to compare the original and cleaned texts.
    """
    diff = difflib.ndiff(list(original), list(cleaned))
    removed_chars = [token[2:] for token in diff if token.startswith("- ")]
    return "".join(removed_chars)


def clean_excel_file(input_path, output_path):
    """
    Reads the Excel file at input_path, applies cleaning to the "コメント" column on every sheet,
    and writes the cleaned data to output_path with only the columns "NO", "コメント" (cleaned),
    and a new column "Removed" that shows what was removed from the original text.
    """
    xls = pd.ExcelFile(input_path)
    with pd.ExcelWriter(output_path) as writer:
        for sheet in tqdm(xls.sheet_names, desc="Processing sheets"):
            df = pd.read_excel(xls, sheet_name=sheet)

            # Process only if there is a column exactly named "コメント"
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
                if "NO" in df.columns:
                    df = df[["NO", "コメント_cleaned", "Removed"]]
                    df.rename(columns={"コメント_cleaned": "コメント"}, inplace=True)
                else:
                    df = df[["コメント_cleaned", "Removed"]]
                    df.rename(columns={"コメント_cleaned": "コメント"}, inplace=True)
            # If no column exactly matching "コメント" exists, leave the sheet unchanged.
            df.to_excel(writer, sheet_name=sheet, index=False)
    print(f"Cleaned Excel file saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Clean Japanese text in an Excel file and show what was removed.")
    parser.add_argument("--input", required=True, help="Path to the input Excel file (e.g., data/raw_reviews.xlsx)")
    parser.add_argument(
        "--output", required=True, help="Path to save the cleaned Excel file (e.g., data/cleaned_reviews.xlsx)"
    )
    args = parser.parse_args()

    input_path = os.path.abspath(args.input)
    output_path = os.path.abspath(args.output)

    clean_excel_file(input_path, output_path)


if __name__ == "__main__":
    main()
