#!/usr/bin/env python3
"""
Extract text from PDF file.

Usage:
    python extract_text.py <pdf_file_path>
    
Example:
    python extract_text.py /path/to/your/paper.pdf
"""

import argparse
import sys
from pathlib import Path
from pdfminer.high_level import extract_text


def main():
    parser = argparse.ArgumentParser(
        description="Extract text from a PDF file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python extract_text.py paper.pdf
    python extract_text.py /path/to/document.pdf
        """
    )
    parser.add_argument(
        "pdf_path",
        type=str,
        help="Path to the PDF file"
    )
    
    args = parser.parse_args()
    
    # Validate file exists
    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        print(f"Error: File not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)
    
    # Validate it's a PDF file
    if not pdf_path.suffix.lower() == ".pdf":
        print(f"Error: File must be a PDF: {pdf_path}", file=sys.stderr)
        sys.exit(1)
    
    # Extract and print text
    try:
        text = extract_text(str(pdf_path))
        print(text)
    except Exception as e:
        print(f"Error extracting text: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
