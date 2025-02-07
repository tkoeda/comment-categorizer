import argparse
import os
import unicodedata

import pandas as pd


def normalize_text(text):
    """
    Normalize the text using NFKC normalization.
    This converts full-width characters (such as the ideographic space \u3000)
    to their standard (half-width) equivalents.
    """
    return unicodedata.normalize('NFKC', text)

def clean_japanese_text(text):
    """
    Clean Japanese text by normalizing and removing extra whitespace.
    You can extend this function to perform additional tokenization or filtering.
    """
    # Normalize text (this converts \u3000 to a regular space)
    normalized = normalize_text(text)
    # Remove extra whitespace by splitting and re-joining the text
    cleaned = " ".join(normalized.split())
    return cleaned

def clean_excel_file(input_path, output_path):
    """
    Reads the Excel file at input_path, applies cleaning to the "コメント" column on every sheet,
    and writes the cleaned data to output_path.
    """
    # Read the entire Excel file (all sheets)
    xls = pd.ExcelFile(input_path)
    with pd.ExcelWriter(output_path) as writer:
        for sheet in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet)
            if "コメント" in df.columns:
                df["コメント"] = df["コメント"].apply(lambda x: clean_japanese_text(str(x)) if pd.notna(x) else x)
            df.to_excel(writer, sheet_name=sheet, index=False)
    print(f"Cleaned Excel file saved to: {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Clean Japanese text in an Excel file.")
    parser.add_argument("--input", required=True, help="Path to the input Excel file (e.g., data/raw_reviews.xlsx)")
    parser.add_argument("--output", required=True, help="Path to save the cleaned Excel file (e.g., data/cleaned_reviews.xlsx)")
    args = parser.parse_args()
    
    input = os.path.abspath(args.input)
    output = os.path.abspath(args.output)
    
    clean_excel_file(input, output)

if __name__ == "__main__":
    main()
