import base64
import logging
import os
import time

from app.common.constants import DATA_DIR, get_user_dirs
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.crud.industries import get_industry
from app.crud.reviews import (
    create_review,
    delete_review_cascade_up,
    get_review,
)
from app.models.index import Index
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

logger = logging.getLogger(__name__)
REVIEWS_DIR = os.path.join(DATA_DIR, "reviews")


console = Console()

router = APIRouter()


@router.get("/list", response_model=FileListResponse)
async def list_files(
    industry_id: int = None,
    review_type: str = None,
    stage: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List available files for new reviews and past reviews.
    Returns JSON lists for raw, combined, cleaned, and past reviews.
    """
    try:
        if industry_id:
            industry = await get_industry(db, industry_id, current_user)
            if not industry:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Industry not found",
                )
            valid_types = ["new", "past", "final"]
            if review_type and review_type not in valid_types:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="無効なレビュータイプです",
                )

            stmt = select(Review).filter(Review.user_id == current_user.id)
            if industry_id:
                stmt = stmt.filter(Review.industry_id == industry_id)
            if review_type:
                stmt = stmt.filter(Review.review_type == review_type)
            if stage:
                stmt = stmt.filter(Review.stage == stage)
            result = await db.execute(stmt)
            reviews = result.scalars().all()
            file_list = []
            for review in reviews:
                file_item = {
                    "id": review.id,
                    "display_name": review.display_name,
                    "file_path": review.file_path,
                    "stage": review.stage,
                    "review_type": review.review_type,
                    "created_at": review.created_at.isoformat(),
                    "parent_id": review.parent_id,
                }

                file_list.append(file_item)
                print(file_item)
        return {"reviews": file_list}
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"データベースエラー: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"予期しないエラーが発生しました: {str(e)}",
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
            detail="タイプは 'new' または 'past' のいずれかである必要があります。",
        )

    industry = await get_industry(db, industry_id, current_user)

    if not industry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="業界が見つかりませんでした。",
        )

    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No files uploaded."
        )
    temp_files = []
    combined_file = None
    cleaned_file = None

    try:
        user_dir = get_user_dirs(current_user.id)
        if review_type == "new":
            raw_dir = os.path.join(user_dir["new"]["raw"], industry.name)
            combined_dir = os.path.join(user_dir["new"]["combined"], industry.name)
            cleaned_dir = os.path.join(user_dir["new"]["cleaned"], industry.name)
        elif review_type == "past":
            raw_dir = os.path.join(user_dir["past"]["raw"], industry.name)
            combined_dir = os.path.join(user_dir["past"]["combined"], industry.name)
            cleaned_dir = os.path.join(user_dir["past"]["cleaned"], industry.name)

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
            user_id=current_user.id,
        )

        input_glob = os.path.join(raw_dir, "*.xlsx")
        try:
            combine_excel(input_glob, combined_file)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Excelファイルの結合に失敗しました: {str(e)}",
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
                detail=f"Excelファイルの結合に失敗しました: {str(e)}",
            )

        if not os.path.exists(cleaned_file):
            raise HTTPException(
                status_code=500,
                detail="クリーニングに失敗しました。出力ファイルが見つかりません。",
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
            message="レビューの結合とクリーニングが完了しました。",
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
            detail="OpenAI APIキーが見つかりません。アカウント設定にAPIキーを追加してください。",
        )

    industry = await get_industry(db, request.industry_id, current_user)

    if not industry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="業界が見つかりませんでした。",
        )
    new_cleaned_review = await get_review(
        db, id=request.new_cleaned_id, user_id=current_user.id
    )
    if not new_cleaned_review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="選択された新しいクリーニング済みファイルが見つかりません。",
        )

    if not os.path.exists(new_cleaned_review.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="新しいクリーニング済みファイルがディスク上に存在しません。",
        )

    new_combined_review = new_cleaned_review.parent
    if not new_combined_review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="結合されたコメントファイルが見つかりません。",
        )

    if not os.path.exists(new_combined_review.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="新しい結合ファイルがディスク上に存在しません。",
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
                logger.info("No index found for industry. Skipping FAISS retrieval.")
                retriever = DummyRetriever()

        user_dirs = get_user_dirs(current_user.id)
        final_dir = os.path.join(user_dirs["final"]["processed"], industry.name)
        os.makedirs(final_dir, exist_ok=True)

        # Generate output path in user's directory
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_filename = f"{industry.name}_{timestamp}_final.xlsx"
        output_excel_path = os.path.join(final_dir, output_filename)

        await classify_and_merge(
            industry=industry,
            new_reviews=new_reviews,
            retriever=retriever,
            new_combined_path=new_combined_review.file_path,
            new_cleaned_path=new_cleaned_review.file_path,
            use_past_reviews=request.use_past_reviews,
            user_api_key=current_user.openai_api_key,
            output_path=output_excel_path,
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
            detail=f"予期しないエラーが発生しました: {str(e)}",
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
            detail=f"予期しないエラーが発生しました: {str(e)}",
        )
