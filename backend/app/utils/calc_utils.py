import re


def calculate_average_time(durations):
    """Return the average of a list of durations or 0 if empty."""
    return sum(durations) / len(durations) if durations else 0


def time_to_seconds(time_str):
    """
    Convert a time string like "5m33s", "599ms", or "59.548s" into seconds (float).
    """
    match = re.match(r"(?:(\d+)m)?(?:(\d+(?:\.\d+)?)s)?(?:(\d+)ms)?", time_str)
    if not match:
        raise ValueError(f"Invalid time format: {time_str}")

    minutes = int(match.group(1)) * 60 if match.group(1) else 0
    seconds = float(match.group(2)) if match.group(2) else 0
    milliseconds = int(match.group(3)) / 1000 if match.group(3) else 0

    return minutes + seconds + milliseconds
