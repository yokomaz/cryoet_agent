"""
PDF text extraction tool for cryoet_agent.

Provides PDF text extraction using pypdf library.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from pypdf import PdfReader


@dataclass
class PdfExtractResult:
    """Result of PDF text extraction."""
    
    text: str
    num_pages: int
    pdf_path: str
    success: bool
    error: str | None = None
    
    def __str__(self) -> str:
        """Return the extracted text as string representation."""
        return self.text


def validate_pdf_file(pdf_path: str | Path) -> tuple[bool, str | None]:
    """
    Validate that the file exists and is a PDF.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    path = Path(pdf_path)
    
    if not path.exists():
        return False, f"File not found: {pdf_path}"
    
    if not path.is_file():
        return False, f"Path is not a file: {pdf_path}"
    
    if path.suffix.lower() != ".pdf":
        return False, f"File must be a PDF (.pdf): {pdf_path}"
    
    return True, None


def pdf_parser(
    pdf_path: str | Path,
    max_pages: int | None = None,
    include_page_markers: bool = True,
) -> PdfExtractResult:
    """
    Extract text from a PDF file.
    
    Args:
        pdf_path: Path to the PDF file
        max_pages: Maximum number of pages to extract (None for all pages)
        include_page_markers: Whether to include "--- Page N ---" markers
        
    Returns:
        PdfExtractResult containing extracted text and metadata
        
    Raises:
        ValueError: If file is invalid or cannot be parsed
        
    Examples:
        >>> result = pdf_parser("/path/to/paper.pdf")
        >>> print(result.text)
        
        >>> result = pdf_parser("paper.pdf", max_pages=5)
        >>> print(f"Extracted from {result.num_pages} pages")
    """
    # Validate input
    pdf_path_str = str(pdf_path)
    is_valid, error = validate_pdf_file(pdf_path_str)
    if not is_valid:
        raise ValueError(error)
    
    try:
        reader = PdfReader(pdf_path_str)
        total_pages = len(reader.pages)
        
        # Determine pages to extract
        if max_pages is not None and max_pages > 0:
            pages_to_extract = min(max_pages, total_pages)
        else:
            pages_to_extract = total_pages
        
        text_parts = []
        for page_num in range(1, pages_to_extract + 1):
            try:
                page = reader.pages[page_num - 1]
                page_text = page.extract_text()
                
                if page_text and page_text.strip():
                    if include_page_markers:
                        text_parts.append(f"--- Page {page_num} ---\n{page_text}")
                    else:
                        text_parts.append(page_text)
                        
            except Exception as e:
                # Continue with other pages if one fails
                text_parts.append(f"[Error extracting page {page_num}: {e}]")
        
        full_text = "\n\n".join(text_parts)
        
        return PdfExtractResult(
            text=full_text,
            num_pages=pages_to_extract,
            pdf_path=pdf_path_str,
            success=True,
        )
        
    except Exception as e:
        return PdfExtractResult(
            text="",
            num_pages=0,
            pdf_path=pdf_path_str,
            success=False,
            error=str(e),
        )


def pdf_parser_safe(
    pdf_path: str | Path,
    max_pages: int = 100,
    max_chars_per_page: int = 50000,
    include_page_markers: bool = True,
) -> str:
    """
    Safe wrapper for pdf_parser that returns string and handles errors gracefully.
    
    Args:
        pdf_path: Path to the PDF file
        max_pages: Maximum number of pages to extract (default: 100)
        max_chars_per_page: Maximum characters per page (default: 50000)
        include_page_markers: Whether to include page markers
        
    Returns:
        Extracted text as string, or error message if failed
    """
    try:
        result = pdf_parser(
            pdf_path=pdf_path,
            max_pages=max_pages,
            include_page_markers=include_page_markers,
        )
        
        if not result.success:
            return f"Error: {result.error}"
        
        # Truncate if too long
        max_total_chars = max_pages * max_chars_per_page
        text = result.text
        if len(text) > max_total_chars:
            text = text[:max_total_chars] + f"\n... (truncated, total: {len(result.text)} chars)"
        
        return text
        
    except Exception as e:
        return f"Error extracting PDF: {e}"
