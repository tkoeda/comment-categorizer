import os
import time

from app.auth.dependencies import get_current_user
from app.constants import (
    DATA_DIR,
    REVIEW_FOLDER_PATHS,
)
from app.core.database import get_db
from app.crud.reviews import (
    create_review,
    delete_review_cascade_up,
    get_review,
)
from app.industries.service import get_industry
from app.models.index import Index
from app.models.industries import Industry
from app.models.reviews import Review
from app.models.users import User
from app.rag_pipeline.combine_clean import clean_excel_file, combine_excel
from app.rag_pipeline.data_loader import fetch_new_reviews_from_excel
from app.rag_pipeline.indexer import DummyRetriever, FaissRetriever
from app.schemas.schemas import (
    CombineAndCleanResponse,
    FileListResponse,
    ProcessReviewsSavedRequest,
)
from app.utils.io_utils import (
    get_unique_filename,
)
from app.utils.reviews import classify_and_merge
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from rich.console import Console
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

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


@router.get("/list", response_model=FileListResponse)
async def list_files(
    industry_id: int = None,
    review_type: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
        stmt = select(Industry).filter(Industry.id == industry_id)
        result = await db.execute(stmt)
        industry = result.scalar_one_or_none()
        if not industry:
            raise HTTPException(status_code=404, detail="Industry not found")

        if review_type and review_type not in ["new", "past"]:
            raise HTTPException(status_code=400, detail="Invalid review type")

        stmt_reviews = select(Review).filter(
            Review.industry_id == industry_id, Review.user_id == current_user.id
        )
        if review_type:
            stmt_reviews = stmt_reviews.filter(Review.review_type == review_type)
        reviews_result = await db.execute(stmt_reviews)
        reviews = reviews_result.scalars().all()
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


@router.post("/combine_and_clean", response_model=CombineAndCleanResponse)
async def combine_and_clean_endpoint(
    industry_id: int = Form(...),
    review_type: str = Form(...),
    display_name: str = Form(""),
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
    temp_files = []
    combined_review = None
    combined_file = None
    cleaned_file = None
    db_transaction_started = False

    try:
        if review_type not in ["new", "past"]:
            raise HTTPException(
                status_code=400, detail="Type must be 'new' or 'past'."
            )

        industry = await get_industry(db, industry_id)

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
        if not files:
            raise HTTPException(status_code=400, detail="No files uploaded.")

        # Save uploaded files to raw directory
        for file in files:
            try:
                file_path = os.path.join(raw_dir, file.filename)
                with open(file_path, "wb") as f:
                    content = await file.read()
                    f.write(content)
                temp_files.append(file_path)
            except Exception:
                raise HTTPException(
                    status_code=500, detail="Failed to save uploaded files"
                )

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

        # Create a display name for the combined file if not provided
        if not display_name:
            display_name = f"{industry.name.title()} {review_type.title()} Reviews - {readable_date}"

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

        # Check if the session is already in a transaction
        # and only start a new one if needed
        if not db.in_transaction():
            await db.begin()
            db_transaction_started = True

        # Save combined file metadata to database
        combined_review = await create_review(
            db,
            industry_id=industry_id,
            review_type=review_type,
            display_name=f"{display_name} - Combined",
            stage="combined",
            file_path=combined_file,
            user_id=current_user.id,
        )

        # Save cleaned file metadata to database
        cleaned_review = await create_review(
            db,
            industry_id=industry_id,
            review_type=review_type,
            display_name=f"{display_name} - Cleaned",
            stage="cleaned",
            file_path=cleaned_file,
            parent_id=combined_review.id,
            user_id=current_user.id,
        )

        # Commit the transaction if we started it
        if db_transaction_started:
            await db.commit()
            db_transaction_started = False

        # Clean up temporary files
        for filename in os.listdir(raw_dir):
            if filename.endswith(".xlsx"):
                src_path = os.path.join(raw_dir, filename)
                if (
                    src_path in temp_files
                ):  # Only remove files we created in this session
                    os.remove(src_path)

        return CombineAndCleanResponse(
            message="Reviews combined and cleaned successfully",
            combined_file=combined_file,
            cleaned_file=cleaned_file,
            combined_review_id=combined_review.id,
            cleaned_review_id=cleaned_review.id,
        )

    except Exception as e:
        # Rollback the transaction if we started it and an error occurred
        if db_transaction_started:
            await db.rollback()

        # Clean up temporary files
        for file_path in temp_files:
            if os.path.exists(file_path):
                os.remove(file_path)

        # Delete combined file if it was created
        if combined_file and os.path.exists(combined_file):
            os.remove(combined_file)

        # Delete cleaned file if it was created
        if cleaned_file and os.path.exists(cleaned_file):
            os.remove(cleaned_file)

        # Re-raise as HTTP exception for the API
        if isinstance(e, HTTPException):
            raise e
        else:
            raise HTTPException(status_code=500, detail=f"Process failed: {str(e)}")


@router.post("/process_reviews")
async def process_reviews_saved_endpoint(
    request: ProcessReviewsSavedRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Process reviews using previously saved files rather than a new upload.
    The user selects the combined (combined) file and the cleaned (cleaned) file.
    The classification pipeline is run using the selected files and the past reviews file,
    then the results are merged and the final Excel file is returned for download.
    """
    industry_id = request.industry_id
    use_past_reviews = request.use_past_reviews
    new_cleaned_id = request.new_cleaned_id
    display_name = request.display_name
    user_api_key = current_user.openai_api_key
    if not user_api_key:
        raise HTTPException(
            status_code=400,
            detail="No OpenAI API key found. Please add your API key in your account settings.",
        )

    industry = await get_industry(db, industry_id)

    new_cleaned_review = await get_review(
        db, id=new_cleaned_id, user_id=current_user.id
    )
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
        stmt = select(Index).filter(Index.industry_id == industry_id)
        result = await db.execute(stmt)
        index_info = result.scalar_one_or_none()
        if index_info and os.path.exists(index_info.index_path):
            try:
                retriever = await FaissRetriever.create(
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
        user_api_key=user_api_key,
    )

    if not display_name:
        display_name = new_cleaned_review.display_name.replace("Cleaned", "Final")

    await create_review(
        db,
        industry_id=industry_id,
        review_type="final",
        display_name=display_name,
        stage="final",
        file_path=output_excel_path,
        parent_id=new_cleaned_review.id,
        user_id=current_user.id,
    )

    return FileResponse(
        output_excel_path,
        filename="categorized_reviews.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.delete("/{review_id}")
async def delete_review(
    review_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a review and cascade deletion upward to its ancestors.
    Returns success status and message.
    """
    success = await delete_review_cascade_up(db, review_id, user_id=current_user.id)

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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Download a review file by its ID
    """
    # Find the review in the database
    stmt = select(Review).filter(Review.id == review_id)
    result = await db.execute(stmt)
    review = result.scalar_one_or_none()

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
