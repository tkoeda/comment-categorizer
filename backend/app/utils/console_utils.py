from rich.console import Console
from rich.progress import Progress
from rich.table import Table

console = Console()


def print_rate_limit_info(response):
    headers = response.headers

    table = Table(
        title="Rate Limit Information", show_header=True, header_style="bold magenta"
    )

    table.add_column("Field", style="bold cyan")
    table.add_column("Value", style="bold yellow")
    table.add_column("Description", style="dim white")

    table.add_row(
        "openai-processing-ms",
        headers.get("openai-processing-ms", "N/A") + "ms",
        "openai-processing-ms",
    )
    table.add_row(
        "x-ratelimit-limit-requests",
        headers.get("x-ratelimit-limit-requests", "N/A"),
        "The max number of requests allowed before hitting the rate limit.",
    )
    table.add_row(
        "x-ratelimit-limit-tokens",
        headers.get("x-ratelimit-limit-tokens", "N/A"),
        "The max number of tokens allowed before hitting the rate limit.",
    )
    table.add_row(
        "x-ratelimit-remaining-requests",
        headers.get("x-ratelimit-remaining-requests", "N/A"),
        "The number of requests you have left before hitting the limit.",
    )
    table.add_row(
        "x-ratelimit-remaining-tokens",
        headers.get("x-ratelimit-remaining-tokens", "N/A"),
        "The number of tokens you have left before hitting the limit.",
    )
    table.add_row(
        "x-ratelimit-reset-requests",
        headers.get("x-ratelimit-reset-requests", "N/A"),
        "Time until request limit resets (e.g., 1s means 1 second).",
    )
    table.add_row(
        "x-ratelimit-reset-tokens",
        headers.get("x-ratelimit-reset-tokens", "N/A"),
        "Time until token limit resets (e.g., 6m0s means 6 minutes).",
    )

    console.print(table)


def display_rate_limit_progress(headers):
    """
    Displays rate limit progress bars for remaining tokens and requests.
    """
    total_requests = int(headers.get("x-ratelimit-limit-requests", 10000))
    remaining_requests = int(headers.get("x-ratelimit-remaining-requests", 10000))

    total_tokens = int(headers.get("x-ratelimit-limit-tokens", 200000))
    remaining_tokens = int(headers.get("x-ratelimit-remaining-tokens", 200000))

    console.clear()

    with Progress() as progress:
        req_task = progress.add_task(
            "[cyan]Remaining Requests...", total=total_requests
        )
        tok_task = progress.add_task(
            "[green]Remaining Tokens...", total=total_tokens
        )

        progress.update(req_task, completed=remaining_requests)
        progress.update(tok_task, completed=remaining_tokens)


def print_status_tracker(status_tracker):
    console = Console()
    table = Table(title="Batch Processing Status Tracker", title_style="bold blue")

    table.add_column("Metric", style="cyan", justify="left")
    table.add_column("Value", style="magenta", justify="right")

    table.add_row("Batches Started", str(status_tracker.num_batches_started))
    table.add_row("Batches Succeeded", str(status_tracker.num_batches_succeeded))
    table.add_row("Batches Failed", str(status_tracker.num_batches_failed))

    console.print(table)
