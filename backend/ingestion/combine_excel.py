import argparse
import pandas as pd
import glob
import os
import logging
from rich.console import Console

console = Console()
# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def combine_excel(input_glob, output_dir, type):
    excel_files = glob.glob(input_glob)
    if not excel_files:
        logger.warning(f"No Excel files found in {input_glob}")
        return

    dfs = []
    for file in excel_files:
        try:
            xls = pd.ExcelFile(file)
        except Exception as e:
            logger.error(f"Failed to read file {file}: {e}")
            continue

        # Loop through all sheet names and extract the "NO"(if exists) and "コメント" column
        for sheet in xls.sheet_names:
            try:
                header_df = pd.read_excel(xls, sheet_name=sheet, nrows=0)

                if "id" in header_df.columns:
                    usecols = ["id", "コメント"]
                else:
                    usecols = ["コメント"]
                df = pd.read_excel(xls, sheet_name=sheet, usecols=usecols)
                dfs.append(df)
            except Exception as e:
                logger.error(f"Error reading sheet '{sheet}' in {file}: {e}")
                continue

    if not dfs:
        logger.warning("No data extracted from any sheets.")
        return

    # Merge all dataframes, keeping only unique 'コメント' values
    merged_df = pd.concat(dfs).drop_duplicates().reset_index(drop=True)

    if "id" not in merged_df.columns:
        merged_df.insert(0, "id", merged_df.index + 1)
    console.print(f"[bold blue]Sheet:[/bold blue] {sheet}")
    console.print(f"[green]Number of rows:[/green] {df.shape[0]}")
    console.print(f"[green]Column names:[/green] {df.columns.tolist()}")

    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"{type}_intermediate.xlsx")

    try:
        merged_df.to_excel(output_file, index=False)
        logger.info(f"Merge complete. Saved as '{output_file}'.")
    except Exception as e:
        logger.error(f"Error saving merged file: {e}")


def main():
    parser = argparse.ArgumentParser(description="Combine all Excel files in a directory into a single file.")
    parser.add_argument("--type", required=True, help="Type of file to combine (e.g., 'past' or 'new')")
    args = parser.parse_args()
    if args.type not in ["past", "new"]:
        raise ValueError("Invalid type. Must be 'past' or 'new'.")

    input_glob = os.path.join("data", f"{args.type}_raw", "*.xlsx")
    output_dir = os.path.join("data", f"{args.type}_intermediate")
    combine_excel(input_glob, output_dir, args.type)


if __name__ == "__main__":
    main()
