import base64
import os
import time

from app.auth.dependencies import get_current_user
from app.constants import (
    DATA_DIR,
    REVIEW_FOLDER_PATHS,
)
from app.core.database import get_db
from app.crud.industries import get_industry
from app.crud.reviews import (
    create_review,
    delete_review_cascade_up,
    get_review,
)
from app.models.index import Index
from app.models.industries import Industry
from app.models.reviews import Review
from app.models.users import User
from app.rag_pipeline.combine_clean import clean_excel_file, combine_excel
from app.rag_pipeline.data_loader import fetch_new_reviews_from_excel
from app.rag_pipeline.indexer import DummyRetriever, FaissRetriever
from app.schemas.reviews import (
    CombineAndCleanResponse,
    FileListResponse,
    ProcessReviewsSavedRequest,
)
from app.utils.common.io_utils import (
    get_unique_filename,
)
from app.utils.routers.reviews import classify_and_merge, clean_up_files
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from rich.console import Console
from sqlalchemy.exc import SQLAlchemyError
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
    try:
        if industry_id:
            industry = await get_industry(db, industry_id)
            if not industry:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Industry not found",
                )

            if review_type and review_type not in ["new", "past"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid review type",
                )

            stmt_reviews = select(Review).filter(
                Review.industry_id == industry_id, Review.user_id == current_user.id
            )
            if review_type:
                stmt_reviews = stmt_reviews.filter(Review.review_type == review_type)
            reviews_result = await db.execute(stmt_reviews)
            reviews = reviews_result.scalars().all()
            for review in reviews:
                file_item = {
                    "id": review.id,
                    "display_name": review.display_name,
                    "file_path": review.file_path,
                    "stage": review.stage,
                    "review_type": review.review_type,
                    "created_at": review.created_at.isoformat(),
                }

                review_type = review.review_type
                if review_type == "final":
                    response["final"].append(file_item)
                else:
                    stage = review.stage

                    if stage not in response[review_type]:
                        response[review_type][stage] = []

                    response[review_type][stage].append(file_item)
        return response
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}",
        )


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
    if review_type not in ["new", "past"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Type must be 'new' or 'past'.",
        )

    industry = await get_industry(db, industry_id)

    if not industry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Industry not found."
        )

    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No files uploaded."
        )
    temp_files = []
    combined_file = None
    cleaned_file = None

    try:
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

        os.makedirs(raw_dir, exist_ok=True)
        os.makedirs(combined_dir, exist_ok=True)
        os.makedirs(cleaned_dir, exist_ok=True)

        for file in files:
            try:
                file_path = os.path.join(raw_dir, file.filename)
                with open(file_path, "wb") as f:
                    content = await file.read()
                    f.write(content)
                temp_files.append(file_path)
            except IOError:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to save file: {file.filename}",
                )

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        readable_date = time.strftime("%B %d, %Y")

        combined_file = get_unique_filename(
            base_dir=combined_dir,
            review_type=review_type,
            stage="combined",
            industry_name=industry.name,
            timestamp=timestamp,
        )

        input_glob = os.path.join(raw_dir, "*.xlsx")
        try:
            combine_excel(input_glob, combined_file)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to combine Excel files: {str(e)}",
            )

        if not os.path.exists(combined_file):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Combination failed, output file not found.",
            )

        if not display_name:
            display_name = f"{industry.name.title()} {review_type.title()} Reviews - {readable_date}"

        base_filename = os.path.basename(combined_file)
        base, ext = os.path.splitext(base_filename)
        cleaned_filename = f"{base}_cleaned{ext}"
        cleaned_file = os.path.join(cleaned_dir, cleaned_filename)

        try:
            clean_excel_file(combined_file, cleaned_file)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to clean Excel file: {str(e)}",
            )

        if not os.path.exists(cleaned_file):
            raise HTTPException(
                status_code=500, detail="Cleaning failed, output file not found."
            )

        try:
            combined_review = await create_review(
                db,
                industry_id=industry_id,
                review_type=review_type,
                display_name=f"{display_name} - Combined",
                stage="combined",
                file_path=combined_file,
                user_id=current_user.id,
            )

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

        except SQLAlchemyError:
            raise
        for filename in os.listdir(raw_dir):
            if filename.endswith(".xlsx"):
                src_path = os.path.join(raw_dir, filename)
                if src_path in temp_files:
                    os.remove(src_path)

        return CombineAndCleanResponse(
            message="Reviews combined and cleaned successfully",
            combined_file=combined_file,
            cleaned_file=cleaned_file,
            combined_review_id=combined_review.id,
            cleaned_review_id=cleaned_review.id,
        )
    except Exception as e:
        clean_up_files(temp_files, combined_file, cleaned_file)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Process failed: {str(e)}",
        )


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
    if not current_user.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No OpenAI API key found. Please add your API key in your account settings.",
        )

    industry = await get_industry(db, request.industry_id)

    if not industry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Industry not found."
        )
    new_cleaned_review = await get_review(
        db, id=request.new_cleaned_id, user_id=current_user.id
    )
    if not new_cleaned_review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Selected new cleaned file not found.",
        )

    if not os.path.exists(new_cleaned_review.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="New cleaned file not found on disk.",
        )

    new_combined_review = new_cleaned_review.parent
    if not new_combined_review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Combined review file not found.",
        )

    if not os.path.exists(new_combined_review.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="New combined file not found on disk.",
        )
    try:
        new_reviews = fetch_new_reviews_from_excel(
            excel_path=new_cleaned_review.file_path, default_industry=industry.name
        )

        retriever = DummyRetriever()
        if request.use_past_reviews:
            stmt = select(Index).filter(Index.industry_id == request.industry_id)
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
            new_combined_path=new_combined_review.file_path,
            new_cleaned_path=new_cleaned_review.file_path,
            use_past_reviews=request.use_past_reviews,
            user_api_key=current_user.openai_api_key,
        )

        display_name = (
            request.display_name
            or new_cleaned_review.display_name.replace("Cleaned", "Final")
        )

        await create_review(
            db,
            industry_id=request.industry_id,
            review_type="final",
            display_name=display_name,
            stage="final",
            file_path=output_excel_path,
            parent_id=new_cleaned_review.id,
            user_id=current_user.id,
        )
        encoded_display_name = base64.b64encode(display_name.encode("utf-8")).decode(
            "ascii"
        )

        response = FileResponse(
            output_excel_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response.headers["X-Filename-Base64"] = encoded_display_name
        response.headers["Access-Control-Expose-Headers"] = "X-Filename-Base64"
        return response
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process reviews: {str(e)}",
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
    try:
        success = await delete_review_cascade_up(
            db, review_id, user_id=current_user.id
        )

        if not success:
            raise HTTPException(
                status_code=404, detail=f"Review with ID {review_id} not found"
            )

        return {
            "success": True,
            "message": f"Review with ID {review_id} and its ancestors deleted successfully",
        }
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}",
        )


@router.get("/download/{review_id}")
async def download_file(
    review_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Download a review file by its ID
    """
    try:
        stmt = select(Review).filter(Review.id == review_id)
        result = await db.execute(stmt)
        review = result.scalar_one_or_none()

        if not review:
            raise HTTPException(status_code=404, detail="Review not found")

        if not os.path.exists(review.file_path):
            raise HTTPException(status_code=404, detail="File not found on server")

        return FileResponse(
            review.file_path,
            filename=review.display_name,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}",
        )
