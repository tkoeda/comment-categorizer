import logging
from dataclasses import dataclass

import pandas as pd

logging.basicConfig(level=logging.ERROR)
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
        if "コメント_cleaned" in df.columns:
            for _, row in df.iterrows():
                review_text = row["コメント_cleaned"]
                if pd.isna(review_text):
                    # logger.warning(
                    #     "Skipping row in sheet '%s' due to missing comment.", sheet
                    # )
                    continue
                industry = (
                    default_industry if default_industry is not None else "unknown"
                )

                categories = []
                if "カテゴリー" in df.columns:
                    category_data = row["カテゴリー"]
                    if pd.notna(category_data):
                        categories = [
                            cat.strip() for cat in str(category_data).split(",")
                        ]

                doc = Document(
                    page_content=str(review_text),
                    metadata={"industry": industry, "categories": categories},
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

        if "id" not in df.columns:
            df["id"] = None

        if "コメント" not in df.columns:
            df["コメント"] = ""

        for _, row in df.iterrows():
            review_text = row["コメント_cleaned"]
            review_id = row["id"]
            industry = (
                default_industry if default_industry is not None else "unknown"
            )

            new_reviews.append(
                {
                    "id": review_id,
                    "text": str(review_text) if pd.notna(review_text) else "",
                    "industry": industry,
                }
            )

    return new_reviews
