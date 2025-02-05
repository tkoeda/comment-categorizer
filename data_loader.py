import logging

import pandas as pd
from langchain.docstore.document import Document

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def fetch_historical_reviews_from_excel(
    excel_path="data/past.xlsx", default_industry=None
):
    """
    Reads historical reviews from an Excel file.
    Expects a sheet with at least the column:
      - コメント

    Since the Excel file does not include an industry column, the industry is taken from the
    `default_industry` parameter. If not provided, "unknown" is used.

    Returns a list of LangChain Document objects.
    """
    xls = pd.ExcelFile(excel_path)
    documents = []
    for sheet in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet)
        if "コメント" in df.columns:
            for _, row in df.iterrows():
                review_text = row["コメント"]
                if pd.isna(review_text):
                    logger.warning(
                        "Skipping row in sheet '%s' due to missing comment.", sheet
                    )
                    continue  # Skip rows with NaN values
                industry = (
                    default_industry if default_industry is not None else "unknown"
                )
                doc = Document(
                    page_content=str(review_text),  # Ensuring it's a string
                    metadata={"industry": industry},
                )
                documents.append(doc)
                logger.debug("Added historical doc: %s", doc)
    return documents


def fetch_new_reviews_from_excel(excel_path="data/news.xlsx", default_industry=None):
    """
    Reads new reviews from an Excel file, including rows with missing comments.
    Expects a sheet with at least the column:
      - コメント

    Returns a list of dictionaries with keys: "NO", "text", and "industry".
    """
    xls = pd.ExcelFile(excel_path)
    new_reviews = []

    for sheet in xls.sheet_names:
        logger.debug("Processing sheet: %s", sheet)
        df = pd.read_excel(xls, sheet_name=sheet)

        # Ensure "NO" exists, default to None if missing
        if "NO" not in df.columns:
            df["NO"] = None

        # Ensure "コメント" exists, default to empty string if missing
        if "コメント" not in df.columns:
            df["コメント"] = ""

        for _, row in df.iterrows():
            review_text = row["コメント"]
            review_id = row["NO"]
            industry = default_industry if default_industry is not None else "unknown"

            # Include rows even if `review_text` is empty or NaN
            new_reviews.append(
                {
                    "NO": review_id,
                    "text": str(review_text)
                    if pd.notna(review_text)
                    else "",  # Ensure it's a string
                    "industry": industry,
                }
            )

    logger.info("Total new reviews extracted: %d", len(new_reviews))
    return new_reviews
