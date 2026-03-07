"""
log_parser.py

Parses infrastructure and deployment log files.
Extracts error blocks, detects error indicators, and structures
raw log content into a format suitable for rule-based or AI analysis.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)

# Error indicators ranked by severity (highest first)
ERROR_INDICATORS = [
    "FATAL",
    "Traceback",
    "Exception",
    "ERROR",
    "permission denied",
    "connection refused",
    "timeout",
    "module not found",
    "no such file",
    "failed",
    "unreachable",
    "refused",
    "killed",
    "segfault",
    "oom",
]

# Context lines to capture around an error line
CONTEXT_WINDOW = 5


@dataclass
class ParsedLog:
    """Structured result of parsing a log file."""

    raw_lines: List[str] = field(default_factory=list)
    error_lines: List[tuple] = field(default_factory=list)   # (line_number, line_text)
    primary_error_block: List[str] = field(default_factory=list)
    primary_error_line: Optional[str] = None
    primary_error_lineno: Optional[int] = None
    detected_indicators: List[str] = field(default_factory=list)
    total_lines: int = 0


def load_log_file(log_path: str) -> List[str]:
    """
    Read a log file and return its lines.

    Args:
        log_path: Absolute or relative path to the log file.

    Returns:
        List of raw log lines (newline stripped).

    Raises:
        FileNotFoundError: If the log file does not exist.
        IOError: If the file cannot be read.
    """
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as fh:
            lines = [line.rstrip("\n") for line in fh.readlines()]
        logger.debug("Loaded %d lines from '%s'", len(lines), log_path)
        return lines
    except FileNotFoundError:
        logger.error("Log file not found: %s", log_path)
        raise
    except IOError as exc:
        logger.error("Failed to read log file '%s': %s", log_path, exc)
        raise


def detect_error_lines(lines: List[str]) -> List[tuple]:
    """
    Scan log lines and return all lines that match known error indicators.

    Args:
        lines: Raw log lines.

    Returns:
        List of (line_number, line_text) tuples for each matching line.
        Line numbers are 1-based.
    """
    matches = []
    for idx, line in enumerate(lines, start=1):
        lower = line.lower()
        for indicator in ERROR_INDICATORS:
            if indicator.lower() in lower:
                matches.append((idx, line))
                break  # avoid duplicate entries for the same line
    logger.debug("Detected %d error lines", len(matches))
    return matches


def extract_primary_error_block(
    lines: List[str], error_lines: List[tuple]
) -> tuple:
    """
    Identify the most critical error line and extract a context block
    of surrounding lines.

    Priority is given to FATAL > Traceback > Exception > ERROR >
    other indicators, in that order.

    Args:
        lines: Full list of raw log lines.
        error_lines: List of (line_number, line_text) error matches.

    Returns:
        Tuple of (primary_line_text, primary_lineno, context_block_lines).
        Returns (None, None, []) if no errors were found.
    """
    if not error_lines:
        return None, None, []

    # Score each error line by indicator priority (lower index = higher priority)
    def priority(item):
        _, text = item
        lower = text.lower()
        for rank, indicator in enumerate(ERROR_INDICATORS):
            if indicator.lower() in lower:
                return rank
        return len(ERROR_INDICATORS)

    primary_lineno, primary_text = min(error_lines, key=priority)

    # Build context window (0-based indexing into lines list)
    start = max(0, primary_lineno - 1 - CONTEXT_WINDOW)
    end = min(len(lines), primary_lineno + CONTEXT_WINDOW)
    block = lines[start:end]

    logger.debug(
        "Primary error at line %d: %s", primary_lineno, primary_text[:120]
    )
    return primary_text, primary_lineno, block


def get_detected_indicators(error_lines: List[tuple]) -> List[str]:
    """
    Return a deduplicated list of indicator keywords found in error lines.

    Args:
        error_lines: List of (line_number, line_text) error matches.

    Returns:
        Unique indicator names found, in order of first appearance.
    """
    found = []
    seen = set()
    for _, text in error_lines:
        lower = text.lower()
        for indicator in ERROR_INDICATORS:
            if indicator.lower() in lower and indicator not in seen:
                found.append(indicator)
                seen.add(indicator)
    return found


def parse_log(log_path: str) -> ParsedLog:
    """
    Full parsing pipeline for a single log file.

    Args:
        log_path: Path to the log file.

    Returns:
        ParsedLog dataclass populated with all extracted information.
    """
    logger.info("Parsing log file: %s", log_path)

    lines = load_log_file(log_path)
    error_lines = detect_error_lines(lines)
    primary_text, primary_lineno, block = extract_primary_error_block(
        lines, error_lines
    )
    indicators = get_detected_indicators(error_lines)

    result = ParsedLog(
        raw_lines=lines,
        error_lines=error_lines,
        primary_error_block=block,
        primary_error_line=primary_text,
        primary_error_lineno=primary_lineno,
        detected_indicators=indicators,
        total_lines=len(lines),
    )

    logger.info(
        "Parsing complete — %d total lines, %d error lines, %d indicators detected",
        result.total_lines,
        len(result.error_lines),
        len(result.detected_indicators),
    )
    return result
