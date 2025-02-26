import os
import re
from typing import Any
from datetime import datetime

def sanitize_filename(filename: str) -> str:
    """
    Convert a string into a valid filename
    
    Args:
        filename: String to convert
    
    Returns:
        Sanitized filename
    """
    # Remove invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Replace spaces with underscores
    filename = filename.replace(' ', '_')
    # Limit length
    return filename[:50]

def create_markdown_file(filepath: str, content: str) -> None:
    """
    Create a markdown file with the given content
    
    Args:
        filepath: Path to save the file
        content: Content to write
    """
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        log_error(f"Error creating markdown file {filepath}: {str(e)}")

def log_error(message: str) -> None:
    """
    Log error message to console and error log file
    
    Args:
        message: Error message to log
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    error_msg = f"[{timestamp}] ERROR: {message}"
    
    print(error_msg)
    
    try:
        with open('research_error.log', 'a', encoding='utf-8') as f:
            f.write(error_msg + '\n')
    except Exception as e:
        print(f"Failed to write to error log: {str(e)}")
