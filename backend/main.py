# src/main_api.py
import logging
import os
import time

import uvicorn
from constants import DATA_DIR, GPT_PRICING
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from industry_api import load_industries
from industry_api import router as industry_router
from ingestion.combine_clean import clean_excel_file, combine_excel

# Import modules from your project. Adjust the import paths as needed.
from rag_pipeline.data_loader import fetch_new_reviews_from_excel
from rag_pipeline.indexer import FaissRetriever
from rag_pipeline.openai_llm import OpenAILLM
from rag_pipeline.process_reviews import (
    ProcessReviewsResult,
    process_reviews_in_batches_async,
)
from rich.console import Console
from rich.table import Table
from utils import (
    calculate_average_time,
    get_unique_filename,
    print_status_tracker,
    save_results_to_excel,
)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

console = Console()

origins = [
    "http://localhost:5173",
]

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

app.include_router(industry_router, prefix="/industries", tags=["Industries"])

# Paths
REVIEWS_DIR = os.path.join(DATA_DIR, "reviews")
# New Reviews
NEW_RAW_DIR = os.path.join(REVIEWS_DIR, "new", "raw")
NEW_COMBINED_DIR = os.path.join(REVIEWS_DIR, "new", "combined")
NEW_CLEANED_DIR = os.path.join(REVIEWS_DIR, "new", "cleaned")
# Past Reviews
PAST_RAW_DIR = os.path.join(REVIEWS_DIR, "past", "raw")
PAST_COMBINED_DIR = os.path.join(REVIEWS_DIR, "past", "combined")
PAST_CLEANED_DIR = os.path.join(REVIEWS_DIR, "past", "cleaned")
# Final output remains the same.
FINAL_DIR = os.path.join(REVIEWS_DIR, "final")


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the main dashboard page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.delete("/delete_file")
async def delete_file_endpoint(folder: str = Form(...), filename: str = Form(...)):
    """
    Delete a file from one of the allowed folders.
    Allowed folder values: "raw", "combined", "cleaned", "past_reviews", "final".
    """
    allowed_folders = {
        "raw": os.path.join(DATA_DIR, "reviews", "raw"),
        "combined": os.path.join(DATA_DIR, "reviews", "combined"),
        "cleaned": os.path.join(DATA_DIR, "reviews", "cleaned"),
        "past_reviews": os.path.join(DATA_DIR, "reviews", "past_reviews"),
        "final": os.path.join(DATA_DIR, "reviews", "final"),
    }
    if folder not in allowed_folders:
        raise HTTPException(
            status_code=400,
            detail="Invalid folder. Allowed: raw, combined, cleaned, past_reviews, final.",
        )

    file_path = os.path.join(allowed_folders[folder], filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")

    try:
        os.remove(file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting file: {e}")

    return JSONResponse(
        content={"message": f"File '{filename}' deleted from folder '{folder}'."}
    )


@app.get("/list_files")
async def list_files(industry: str = None, type: str = None):
    """
    List available files for new reviews and past reviews.
    Returns JSON lists for raw, combined, cleaned, and past reviews.
    """
    files = {}
    if type == "new" and industry:
        raw_new_path = os.path.join(NEW_RAW_DIR, industry)
        combined_new_path = os.path.join(NEW_COMBINED_DIR, industry)
        cleaned_new_path = os.path.join(NEW_CLEANED_DIR, industry)
        files["raw_new"] = (
            os.listdir(raw_new_path) if os.path.exists(raw_new_path) else []
        )
        files["combined_new"] = (
            os.listdir(combined_new_path)
            if os.path.exists(combined_new_path)
            else []
        )
        files["cleaned_new"] = (
            os.listdir(cleaned_new_path) if os.path.exists(cleaned_new_path) else []
        )
    elif type == "past" and industry:
        combined_past_path = os.path.join(PAST_COMBINED_DIR, industry)
        cleaned_past_path = os.path.join(PAST_CLEANED_DIR, industry)
        files["combined_past"] = (
            os.listdir(combined_past_path)
            if os.path.exists(combined_past_path)
            else []
        )
        files["cleaned_past"] = (
            os.listdir(cleaned_past_path)
            if os.path.exists(cleaned_past_path)
            else []
        )
    else:
        files = {"error": "Please provide both industry and type."}
    return files


@app.post("/combine_reviews")
async def combine_reviews_endpoint(
    industry: str = Form(...),
    type: str = Form(...),
    files: list[UploadFile] = File(...),
):
    """
    Combine multiple uploaded Excel files (raw reviews) into a single Excel file.
    The files are saved to data/reviews/raw/{type}, then combined into data/reviews/combined/{type}.
    After combining, the raw files are moved to an archive folder.
    """
    if type not in ["new", "past"]:
        raise HTTPException(status_code=400, detail="Type must be 'new' or 'past'.")

    # Use subdirectories based on type
    if type == "new":
        raw_dir = os.path.join(NEW_RAW_DIR, industry)
        combined_dir = os.path.join(NEW_COMBINED_DIR, industry)
    # (Adjust accordingly if you support past reviews here)
    elif type == "past":
        raw_dir = os.path.join(PAST_RAW_DIR, industry)
        combined_dir = os.path.join(PAST_COMBINED_DIR, industry)
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(combined_dir, exist_ok=True)

    # Save uploaded files to the type-specific raw directory
    for file in files:
        file_path = os.path.join(raw_dir, file.filename)
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

    # Combine all raw files from the type-specific raw directory
    input_glob = os.path.join(raw_dir, "*.xlsx")
    output_file = get_unique_filename(combined_dir, type=type)
    combine_excel(input_glob, output_file)

    if not os.path.exists(output_file):
        raise HTTPException(
            status_code=500, detail="Combination failed, output file not found."
        )

    # Move processed files from the type-specific raw directory to archive
    for filename in os.listdir(raw_dir):
        if filename.endswith(".xlsx"):
            src_path = os.path.join(raw_dir, filename)
            os.remove(src_path)
            # Alternatively, use os.rename(src_path, dst_path) to move them

    return JSONResponse(
        content={
            "message": f"Combined file saved to {output_file}",
            "output_file": output_file,
        }
    )


@app.post("/clean_reviews")
async def clean_reviews_endpoint(
    industry: str = Form(...), selected_file: str = Form(...)
):
    """
    Clean the selected combined Excel file for the given type (new or past).
    The combined file (user-selected from data/{type}_combined) is cleaned and saved to data/{type}_cleaned.
    If the 'id' column is missing, it is added.
    """
    type = selected_file.split("_")[0]
    if type not in ["new", "past"]:
        raise HTTPException(status_code=400, detail="Type must be 'new' or 'past'.")
    # Build the full path from the user-selected file.
    input_file = os.path.join(REVIEWS_DIR, type, "combined", industry, selected_file)
    cleaned_dir = os.path.join(REVIEWS_DIR, type, "cleaned", industry)
    os.makedirs(cleaned_dir, exist_ok=True)
    if type == "new":
        output_file = get_unique_filename(cleaned_dir, type=type)
    elif type == "past":
        output_file = os.path.join(
            REVIEWS_DIR,
            "past",
            "cleaned",
            industry,
            f"{industry}_past_reviews_cleaned.xlsx",
        )
    else:
        raise HTTPException(status_code=400, detail="Type must be 'new' or 'past'.")
    if not os.path.exists(input_file):
        raise HTTPException(
            status_code=400,
            detail=f"Combined file '{selected_file}' not found for type {type}. Please combine first.",
        )

    # Perform cleaning.
    clean_excel_file(input_file, output_file)

    return JSONResponse(
        content={
            "message": f"Cleaned file saved to {output_file}",
            "output_file": output_file,
        }
    )


async def run_classification_pipeline(
    new_reviews, industry, past_reviews_path
) -> ProcessReviewsResult:
    """
    Helper function to run the classification pipeline.
    Instantiates a FAISS retriever and LLM, then calls process_reviews_in_batches_async.
    """
    faiss_retriever = FaissRetriever(
        industry=industry, past_excel_path=past_reviews_path
    )
    llm = OpenAILLM(model="gpt-4o-mini", temperature=0)
    result = await process_reviews_in_batches_async(
        new_reviews,
        faiss_retriever,
        llm,
        load_industries(),
        reviews_per_batch=20,
        max_concurrent_batches=20,
        max_attempts=3,
    )
    return result


async def classify_and_merge(
    industry: str,
    new_reviews,
    past_reviews_path: str,
    original_file: str,
    cleaned_file: str,
) -> str:
    """
    Runs the classification pipeline and computes diagnostics (token counts, cost, etc.),
    merges the classification results with the original and cleaned files via save_results_to_excel(),
    and returns the final Excel file path.
    """
    total_start = time.time()

    # Run classification pipeline.
    pipeline_result = await run_classification_pipeline(
        new_reviews, industry, past_reviews_path
    )
    results = pipeline_result.results
    retrieval_durations = pipeline_result.retrieval_durations
    llm = pipeline_result.llm
    status_tracker = pipeline_result.status_tracker
    avg_length = pipeline_result.avg_length

    print_status_tracker(status_tracker)

    total_prompt_tokens = llm.total_prompt_tokens
    total_completion_tokens = llm.total_completion_tokens
    total_tokens = llm.total_tokens
    total_api_calls = llm.api_calls

    section_times = {}
    section_times["retrieval_processing"] = calculate_average_time(
        retrieval_durations
    )
    avg_api_call_duration_ms = calculate_average_time(llm.api_call_durations)
    section_times["avg_api_call_duration"] = avg_api_call_duration_ms / 1000

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

    total_end = time.time()
    total_time = total_end - total_start
    section_times["total_processing"] = total_time

    token_info = {
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "prompt_cost": total_prompt_cost,
        "completion_cost": total_completion_cost,
        "total_cost": total_cost,
        "total_reviews": len(results),
    }

    # Define a helper function for clean printing.
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

    output_excel_path = save_results_to_excel(
        results,
        token_info,
        section_times,
        model=llm.model,
        embeddings_model="default",  # Adjust if needed
        output_dir=FINAL_DIR,
        raw_or_processed="processed",
        original_file=original_file,
        cleaned_file=cleaned_file,
    )

    return output_excel_path


# --------------------------
# Endpoint 2: Process Reviews Using Saved Files
# --------------------------
@app.post("/process_reviews_saved")
async def process_reviews_saved_endpoint(
    industry: str = Form(...),
    combined_file: str = Form(...),
    cleaned_file: str = Form(...),
):
    """
    Process reviews using previously saved files rather than a new upload.
    The user selects the combined (combined) file and the cleaned (cleaned) file.
    The classification pipeline is run using the selected files and the past reviews file,
    then the results are merged and the final Excel file is returned for download.
    """
    # original_file = os.path.join(COMBINED_DIR, combined_file)
    # cleaned_file = os.path.join(CLEANED_DIR, cleaned_file)

    combined_file = os.path.join(NEW_COMBINED_DIR, industry, combined_file)
    cleaned_file = os.path.join(NEW_CLEANED_DIR, industry, cleaned_file)
    past_reviews_path = os.path.join(
        PAST_CLEANED_DIR, industry, f"{industry}_past_reviews_cleaned.xlsx"
    )

    if not os.path.exists(combined_file):
        raise HTTPException(
            status_code=400, detail="Selected combined file not found."
        )
    if not os.path.exists(cleaned_file):
        raise HTTPException(
            status_code=400, detail="Selected cleaned file not found."
        )

    if not os.path.exists(past_reviews_path):
        raise HTTPException(
            status_code=400,
            detail=f"Past reviews file for industry '{industry}' not found. Please update it via /update_past_reviews.",
        )
    new_reviews = fetch_new_reviews_from_excel(
        excel_path=combined_file, default_industry=industry
    )
    output_excel_path = await classify_and_merge(
        industry, new_reviews, past_reviews_path, combined_file, cleaned_file
    )
    return FileResponse(
        output_excel_path,
        filename="categorized_reviews.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.post("/update_past_reviews")
async def update_past_reviews_endpoint(
    industry: str = Form(...), file: UploadFile = File(...)
):
    """
    Update the past reviews file for a given industry.
    """
    cleaned_past_dir = os.path.join(PAST_CLEANED_DIR, industry)
    os.makedirs(cleaned_past_dir, exist_ok=True)
    save_path = os.path.join(
        cleaned_past_dir, f"past_reviews_{industry}_cleaned.xlsx"
    )
    try:
        with open(save_path, "wb") as f:
            content = await file.read()
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving file: {e}")
    return JSONResponse(
        content={
            "message": f"Past reviews for industry '{industry}' updated successfully.",
            "path": save_path,
        }
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
