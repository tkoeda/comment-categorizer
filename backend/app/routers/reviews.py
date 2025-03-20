import os
import time

from constants import DATA_DIR, GPT_PRICING, INDEX_DIR, REVIEW_FOLDER_PATHS
from core.database import get_db
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from models.models import Industry, IndustryIndex, Review
from rag_pipeline.combine_clean import clean_excel_file, combine_excel
from rag_pipeline.data_loader import fetch_new_reviews_from_excel
from rag_pipeline.indexer import DummyRetriever, FaissRetriever
from rag_pipeline.openai_llm import OpenAILLM
from rag_pipeline.process_reviews import process_reviews_in_batches_async
from rich.console import Console
from rich.table import Table
from services.industry_service import get_industry
from services.review_service import (
    create_review,
    delete_review_cascade_up,
    get_review,
)
from sqlalchemy.orm import Session
from utils.calc_utils import calculate_average_time
from utils.console_utils import print_status_tracker
from utils.io_utils import (
    get_unique_filename,
    save_results_to_excel,
)

REVIEWS_DIR = os.path.join(DATA_DIR, "reviews")
NEW_RAW_DIR = os.path.join(REVIEWS_DIR, "new", "raw")
NEW_COMBINED_DIR = os.path.join(REVIEWS_DIR, "new", "combined")
NEW_CLEANED_DIR = os.path.join(REVIEWS_DIR, "new", "cleaned")
PAST_RAW_DIR = os.path.join(REVIEWS_DIR, "past", "raw")
PAST_COMBINED_DIR = os.path.join(REVIEWS_DIR, "past", "combined")
PAST_CLEANED_DIR = os.path.join(REVIEWS_DIR, "past", "cleaned")
FINAL_DIR = os.path.join(REVIEWS_DIR, "final")


console = Console()

router = APIRouter()


@router.get("/list")
async def list_files(
    industry_id: int = None,
    review_type: str = None,
    db: Session = Depends(get_db),
):
    """
    List available files for new reviews and past reviews.
    Returns JSON lists for raw, combined, cleaned, and past reviews.
    """
    response = {
        "new": {"cleaned": [], "combined": []},
        "past": {"cleaned": [], "combined": []},
        "final": [],
    }
    if industry_id:
        industry = db.query(Industry).filter(Industry.id == industry_id).first()
        if not industry:
            raise HTTPException(status_code=404, detail="Industry not found")

        if review_type and review_type not in ["new", "past"]:
            raise HTTPException(status_code=400, detail="Invalid review type")

        reviews_query = db.query(Review).filter(Review.industry_id == industry_id)

        if review_type:
            reviews_query = reviews_query.filter(Review.review_type == review_type)
        # Execute the query to get the reviews for this industry and type
        reviews = reviews_query.all()
        # Organize files by review type and stage
        for review in reviews:
            file_item = {
                "id": review.id,
                "display_name": review.display_name,
                "file_path": review.file_path,
                "stage": review.stage,
                "review_type": review.review_type,
                "created_at": review.created_at.isoformat(),
            }

            review_type = review.review_type  # 'new' or 'past'
            if review_type == "final":
                response["final"].append(file_item)
            else:
                stage = review.stage  # 'cleaned', 'combined', etc.

                # Add to specific stage list
                if stage not in response[review_type]:
                    response[review_type][stage] = []

                response[review_type][stage].append(file_item)
    return response


@router.post("/combine_and_clean")
async def combine_and_clean_endpoint(
    industry_id: int = Form(...),
    review_type: str = Form(...),
    display_name: str = Form(None),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """
    Combined endpoint that both combines and cleans multiple uploaded Excel files (raw reviews).
    The process includes:
    1. Saving files to data/reviews/raw/{type}
    2. Combining files into a single file in data/reviews/combined/{type}
    3. Cleaning the combined file and saving to data/reviews/cleaned/{type}
    4. Moving raw files to archive

    Returns paths to both combined and cleaned files.
    """

    if review_type not in ["new", "past"]:
        raise HTTPException(status_code=400, detail="Type must be 'new' or 'past'.")

    industry = get_industry(db, industry_id)

    if not industry:
        raise HTTPException(status_code=404, detail="Industry not found.")

    # Set up directories
    if review_type == "new":
        raw_dir = os.path.join(REVIEW_FOLDER_PATHS["new"]["raw"], industry.name)
        combined_dir = os.path.join(
            REVIEW_FOLDER_PATHS["new"]["combined"], industry.name
        )
        cleaned_dir = os.path.join(
            REVIEW_FOLDER_PATHS["new"]["cleaned"], industry.name
        )
    elif review_type == "past":
        raw_dir = os.path.join(REVIEW_FOLDER_PATHS["past"]["raw"], industry.name)
        combined_dir = os.path.join(
            REVIEW_FOLDER_PATHS["past"]["combined"], industry.name
        )
        cleaned_dir = os.path.join(
            REVIEW_FOLDER_PATHS["past"]["cleaned"], industry.name
        )

    # Create directories if they don't exist
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(combined_dir, exist_ok=True)
    os.makedirs(cleaned_dir, exist_ok=True)

    # Check if files were uploaded
    if len(files) <= 0:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    # Save uploaded files to raw directory
    for file in files:
        file_path = os.path.join(raw_dir, file.filename)
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

    # Generate timestamp and formatted date for filenames
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    readable_date = time.strftime("%B %d, %Y")

    # Generate output filename for combined file
    combined_file = get_unique_filename(
        base_dir=combined_dir,
        review_type=review_type,
        stage="combined",
        industry_name=industry.name,
        timestamp=timestamp,
    )

    # Combine Excel files
    input_glob = os.path.join(raw_dir, "*.xlsx")
    combine_excel(input_glob, combined_file)

    if not os.path.exists(combined_file):
        raise HTTPException(
            status_code=500, detail="Combination failed, output file not found."
        )

    # Clean up raw files after combining
    for filename in os.listdir(raw_dir):
        if filename.endswith(".xlsx"):
            src_path = os.path.join(raw_dir, filename)
            os.remove(src_path)

    # Create a display name for the combined file if not provided
    if not display_name:
        display_name = f"{industry.name.title()} {review_type.title()} Reviews - {readable_date}"

    # Save combined file metadata to database
    combined_review = create_review(
        db,
        industry_id=industry_id,
        review_type=review_type,
        display_name=f"{display_name} - Combined",
        stage="combined",
        file_path=combined_file,
    )

    # Create cleaned file path
    base_filename = os.path.basename(combined_file)
    base, ext = os.path.splitext(base_filename)
    cleaned_filename = f"{base}_cleaned{ext}"
    cleaned_file = os.path.join(cleaned_dir, cleaned_filename)

    # Clean the combined file
    clean_excel_file(combined_file, cleaned_file)

    if not os.path.exists(cleaned_file):
        raise HTTPException(
            status_code=500, detail="Cleaning failed, output file not found."
        )

    # Save cleaned file metadata to database
    cleaned_review = create_review(
        db,
        industry_id=industry_id,
        review_type=review_type,
        display_name=f"{display_name} - Cleaned",
        stage="cleaned",
        file_path=cleaned_file,
        parent_id=combined_review.id,
    )

    return JSONResponse(
        content={
            "message": "Reviews combined and cleaned successfully",
            "combined_file": combined_file,
            "cleaned_file": cleaned_file,
            "combined_review_id": combined_review.id,
            "cleaned_review_id": cleaned_review.id,
        }
    )


async def classify_and_merge(
    industry: Industry,
    new_reviews,
    retriever,  # Now accepting retriever object directly
    new_combined_path: str,
    new_cleaned_path: str,
    use_past_reviews: bool = False,
) -> str:
    """
    Runs the classification pipeline and computes diagnostics (token counts, cost, etc.),
    merges the classification results with the original and cleaned files via save_results_to_excel(),
    and returns the final Excel file path.

    Args:
        industry: Industry object for the reviews
        new_reviews: List of new reviews to classify
        retriever: FaissRetriever or DummyRetriever instance (already initialized)
        new_combined_path: Path to the combined new reviews file
        new_cleaned_path: Path to the cleaned new reviews file
        use_past_reviews: Flag indicating whether past reviews are being used
    """
    total_start = time.time()

    # Initialize the LLM
    llm = OpenAILLM(model="gpt-4o-mini", temperature=0.5)

    # Process reviews in batches using the provided retriever
    result = await process_reviews_in_batches_async(
        new_reviews,
        retriever,
        llm,
        industry,
        reviews_per_batch=20,
        max_concurrent_batches=20,
        max_attempts=3,
    )

    results = result.results
    retrieval_durations = result.retrieval_durations
    status_tracker = result.status_tracker
    avg_length = result.avg_length

    print_status_tracker(status_tracker)

    # Calculate token usage and costs
    total_prompt_tokens = llm.total_prompt_tokens
    total_completion_tokens = llm.total_completion_tokens
    total_tokens = llm.total_tokens
    total_api_calls = llm.api_calls

    # Track section times
    section_times = {}

    # Only record retrieval timing if we're using a FaissRetriever (not DummyRetriever)
    if use_past_reviews and not isinstance(retriever, DummyRetriever):
        section_times["retrieval_processing"] = calculate_average_time(
            retrieval_durations
        )
        retriever_type = "FAISS"
        embeddings_model = getattr(retriever, "embeddings_model_name", "default")
    else:
        section_times["retrieval_processing"] = "N/A"
        retriever_type = "None"
        embeddings_model = None

    # Calculate API call timing
    avg_api_call_duration_ms = calculate_average_time(llm.api_call_durations)
    section_times["avg_api_call_duration"] = avg_api_call_duration_ms / 1000

    # Calculate costs
    if "gpt-4o-mini" in llm.model:
        gpt_model = "gpt-4o-mini"
    else:
        gpt_model = llm.model.split("-")[0]

    model_pricing = GPT_PRICING.get(gpt_model, {"prompt": 0.0, "completion": 0.0})

    if llm.model.startswith("gpt-4o-mini"):
        total_prompt_cost = (total_prompt_tokens / 1_000_000) * model_pricing[
            "prompt"
        ]
        total_completion_cost = (
            total_completion_tokens / 1_000_000
        ) * model_pricing["completion"]
    else:
        total_prompt_cost = 0.0
        total_completion_cost = 0.0

    total_cost = total_prompt_cost + total_completion_cost

    # Calculate total processing time
    total_end = time.time()
    total_time = total_end - total_start
    section_times["total_processing"] = total_time

    # Compile token usage information
    token_info = {
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "prompt_cost": total_prompt_cost,
        "completion_cost": total_completion_cost,
        "total_cost": total_cost,
        "total_reviews": len(results),
        "retriever_type": retriever_type,
        "past_reviews_path": "Using FAISS index"
        if use_past_reviews
        else "Not using past reviews",
        "new_reviews_path": new_combined_path,
    }

    # Print diagnostic information to console
    def print_diagnostics():
        cost_table = Table(
            title="Token and Cost Details", title_style="bold magenta"
        )
        cost_table.add_column("Total Prompt Tokens", justify="right")
        cost_table.add_column("Total Completion Tokens", justify="right")
        cost_table.add_column("Total Prompt Cost ($)", justify="right")
        cost_table.add_column("Total Completion Cost ($)", justify="right")
        cost_table.add_column("Total Cost ($)", justify="right")
        cost_table.add_row(
            f"{total_prompt_tokens}",
            f"{total_completion_tokens}",
            f"${total_prompt_cost:.6f}",
            f"${total_completion_cost:.6f}",
            f"${total_cost:.6f}",
        )
        console.print(cost_table)

        if total_api_calls > 0:
            console.print(
                f"[bold yellow]Average Total Tokens: {total_tokens / total_api_calls:.2f} tokens[/bold yellow]"
            )
        else:
            console.print("[bold yellow]No API calls made.[/bold yellow]")

        console.print(
            f"[bold yellow]Average Review Length: {avg_length:.2f} words[/bold yellow]"
        )
        console.print(
            f"[bold magenta]Total Runtime: {total_time:.2f} seconds[/bold magenta]"
        )

    print_diagnostics()

    # Save results to Excel file
    start_save = time.time()
    output_excel_path = save_results_to_excel(
        results,
        token_info,
        section_times,
        model=llm.model,
        industry_name=industry.name,
        embeddings_model=embeddings_model,
        new_combined_path=new_combined_path,
        new_cleaned_path=new_cleaned_path,
    )
    section_times["saving_results"] = time.time() - start_save

    return output_excel_path


@router.post("/process_reviews")
async def process_reviews_saved_endpoint(
    industry_id: int = Form(...),
    use_past_reviews: bool = Form(False),
    new_cleaned_id: int = Form(...),
    display_name: str = Form(None),
    db: Session = Depends(get_db),
):
    """
    Process reviews using previously saved files rather than a new upload.
    The user selects the combined (combined) file and the cleaned (cleaned) file.
    The classification pipeline is run using the selected files and the past reviews file,
    then the results are merged and the final Excel file is returned for download.
    """
    industry = get_industry(db, industry_id)

    new_cleaned_review = get_review(db, new_cleaned_id)
    if not new_cleaned_review:
        raise HTTPException(
            status_code=400, detail="Selected new cleaned file not found."
        )
    new_combined_review = new_cleaned_review.parent
    new_combined_filepath = new_combined_review.file_path

    if not os.path.exists(new_combined_filepath):
        raise HTTPException(
            status_code=400, detail="New combined file path not found."
        )
    new_reviews = fetch_new_reviews_from_excel(
        excel_path=new_cleaned_review.file_path, default_industry=industry.name
    )

    retriever = DummyRetriever()
    if use_past_reviews:
        index_info = (
            db.query(IndustryIndex)
            .filter(IndustryIndex.industry_id == industry_id)
            .first()
        )
        if index_info and os.path.exists(index_info.index_path):
            try:
                retriever = FaissRetriever(
                    industry=industry,
                    db=db,
                )
            except Exception as e:
                print(f"Error initializing retriever: {str(e)}")
                retriever = DummyRetriever()
        else:
            print("No index found for industry. Skipping FAISS retrieval.")
            retriever = DummyRetriever()

    output_excel_path = await classify_and_merge(
        industry=industry,
        new_reviews=new_reviews,
        retriever=retriever,
        new_combined_path=new_combined_filepath,
        new_cleaned_path=new_cleaned_review.file_path,
        use_past_reviews=use_past_reviews,
    )

    if not display_name:
        display_name = new_cleaned_review.display_name.replace("Cleaned", "Final")

    create_review(
        db,
        industry_id=industry_id,
        review_type="final",
        display_name=display_name,
        stage="final",
        file_path=output_excel_path,
        parent_id=new_cleaned_review.id,
    )

    return FileResponse(
        output_excel_path,
        filename="categorized_reviews.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/index_status/{industry_id}")
async def get_index_status(
    industry_id: int,
    db: Session = Depends(get_db),
):
    """
    Get the status of the FAISS index for an industry.

    Returns information about whether the index exists, how many reviews it contains,
    and when it was last updated.
    """
    industry = get_industry(db, industry_id)
    if not industry:
        raise HTTPException(status_code=404, detail="Industry not found")

    # Check if industry has an index record
    index_info = (
        db.query(IndustryIndex)
        .filter(IndustryIndex.industry_id == industry_id)
        .first()
    )

    if not index_info:
        return {
            "exists": False,
            "count": 0,
            "lastUpdated": None,
        }

    # Verify index file actually exists
    index_exists = os.path.exists(index_info.index_path)

    return {
        "exists": index_exists,
        "count": index_info.reviews_included if index_exists else 0,
        "lastUpdated": index_info.updated_at.isoformat() if index_exists else None,
    }


@router.post("/update_past_reviews_index")
async def update_past_reviews_index_endpoint(
    industry_id: int = Form(...),
    past_cleaned_id: int = Form(...),
    mode: str = Form("add"),  # "add" or "replace"
    db: Session = Depends(get_db),
):
    """
    Add new past reviews to the industry's FAISS index or replace the existing index.

    Args:
        industry_id: ID of the industry
        past_cleaned_id: ID of the past cleaned review to add
        mode: "add" to add to existing index, "replace" to create a new index
    """
    # Validate inputs
    if mode not in ["add", "replace"]:
        raise HTTPException(
            status_code=400, detail="Mode must be 'add' or 'replace'"
        )

    industry = get_industry(db, industry_id)
    if not industry:
        raise HTTPException(status_code=404, detail="Industry not found")

    past_review = get_review(db, past_cleaned_id)
    if not past_review:
        raise HTTPException(status_code=404, detail="Past review not found")

    if past_review.review_type != "past" or past_review.stage != "cleaned":
        raise HTTPException(
            status_code=400, detail="Selected review must be a cleaned past review"
        )

    try:
        # Check if index already exists
        index_info = (
            db.query(IndustryIndex)
            .filter(IndustryIndex.industry_id == industry_id)
            .first()
        )

        replace = mode == "replace"
        embeddings_model = "pkshatech/GLuCoSE-base-ja-v2"  # Default model

        # If index exists and we're doing an add operation
        if index_info and os.path.exists(index_info.index_path) and not replace:
            # Initialize the retriever with existing index
            try:
                retriever = FaissRetriever(
                    industry=industry,  # Pass the industry object
                    db=db,
                    embeddings_model=index_info.embeddings_model,
                )

                # Update the index with new reviews
                retriever.update_index(
                    new_past_excel_path=past_review.file_path, db=db, replace=False
                )
            except Exception as e:
                print(f"Error updating index: {str(e)}")
                raise HTTPException(
                    status_code=500, detail=f"Failed to update index: {str(e)}"
                )

        else:
            # Either no index exists or we're replacing
            # If index exists but we're replacing, delete the old record
            if index_info:
                # Delete physical index file if it exists
                if os.path.exists(index_info.index_path):
                    try:
                        os.remove(index_info.index_path)
                    except OSError as e:
                        print(f"Warning: Could not delete old index file: {e}")

                # Delete cached data file if it exists
                if os.path.exists(index_info.cached_data_path):
                    try:
                        os.remove(index_info.cached_data_path)
                    except OSError as e:
                        print(f"Warning: Could not delete old cached data: {e}")

                db.delete(index_info)
                db.commit()

            # Create index directory if it doesn't exist
            os.makedirs(INDEX_DIR, exist_ok=True)

            # Initialize retriever and generate new index
            try:
                retriever = FaissRetriever(
                    industry=industry,  # Pass the industry object
                    db=db,
                    past_excel_path=past_review.file_path,
                    embeddings_model=embeddings_model,
                )
            except Exception as e:
                print(f"Error creating index: {str(e)}")
                raise HTTPException(
                    status_code=500, detail=f"Failed to create index: {str(e)}"
                )
        # Get updated index info
        index_info = (
            db.query(IndustryIndex)
            .filter(IndustryIndex.industry_id == industry_id)
            .first()
        )

        delete_review_cascade_up(db, past_cleaned_id)

        return {
            "message": f"Index {'replaced' if replace else 'updated'} successfully",
            "reviews_included": index_info.reviews_included,
            "last_updated": index_info.updated_at.isoformat(),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to {'replace' if mode == 'replace' else 'update'} index: {str(e)}",
        )


@router.delete("/{review_id}")
async def delete_review(
    review_id: int,
    db: Session = Depends(get_db),
):
    """
    Delete a review and cascade deletion upward to its ancestors.
    Returns success status and message.
    """
    success = delete_review_cascade_up(db, review_id)

    if not success:
        raise HTTPException(
            status_code=404, detail=f"Review with ID {review_id} not found"
        )

    return {
        "success": True,
        "message": f"Review with ID {review_id} and its ancestors deleted successfully",
    }


@router.get("/download/{review_id}")
async def download_file(
    review_id: int,
    db: Session = Depends(get_db),
):
    """
    Download a review file by its ID
    """
    print("download")
    print("reviewId", review_id)
    # Find the review in the database
    review = db.query(Review).filter(Review.id == review_id).first()

    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    # Check if file exists
    if not os.path.exists(review.file_path):
        raise HTTPException(status_code=404, detail="File not found on server")

    # Return file response with proper content type for Excel
    return FileResponse(
        review.file_path,
        filename=review.display_name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
