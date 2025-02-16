import logging
from dataclasses import dataclass

import pandas as pd
from tqdm import tqdm

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


@dataclass
class Document:
    page_content: str
    metadata: dict


def fetch_historical_reviews_from_excel(excel_path, default_industry=None):
    """
    Reads historical reviews from an Excel file.
    Expects a sheet with at least the column:
      - コメント

    Since the Excel file does not include an industry column, the industry is taken from the
    `default_industry` parameter. If not provided, "unknown" is used.

    Returns a list of custom Document objects.
    """
    xls = pd.ExcelFile(excel_path)
    documents = []
    for sheet in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet)
        if "コメント" in df.columns:
            for _, row in df.iterrows():
                review_text = row["コメント"]
                if pd.isna(review_text):
                    logger.warning("Skipping row in sheet '%s' due to missing comment.", sheet)
                    continue
                industry = default_industry if default_industry is not None else "unknown"
                doc = Document(
                    page_content=str(review_text),
                    metadata={"industry": industry},
                )
                documents.append(doc)
    return documents


def fetch_new_reviews_from_excel(excel_path, default_industry=None):
    """
    Reads new reviews from an Excel file, including rows with missing comments.
    Expects a sheet with at least the column:
      - コメント

    Returns a list of dictionaries with keys: "NO", "text", and "industry".
    """
    xls = pd.ExcelFile(excel_path)
    new_reviews = []

    for sheet in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet)

        if "NO" not in df.columns:
            df["NO"] = None

        if "コメント" not in df.columns:
            df["コメント"] = ""

        for _, row in tqdm(df.iterrows(), total=len(df), desc=f"Processing rows in {sheet}", leave=False):
            review_text = row["コメント"]
            review_id = row["NO"]
            industry = default_industry if default_industry is not None else "unknown"

            new_reviews.append(
                {
                    "NO": review_id,
                    "text": str(review_text) if pd.notna(review_text) else "",
                    "industry": industry,
                }
            )

    return new_reviews
