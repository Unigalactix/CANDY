"""
Helper utility functions
"""
from datetime import datetime
from pathlib import Path
from typing import Dict
import json


def generate_output_path(original_file_name: str, output_prefix: str = "") -> str:
    """
    Generate output path for processed document using original filename.
    If the same file is processed multiple times, it will overwrite the existing one.
    
    Args:
        original_file_name: Original file name (e.g., "document.pdf" or "folder/document.pdf")
        output_prefix: Prefix for output path (empty by default to save directly in container)
        
    Returns:
        Output path string (e.g., "document.json")
    """
    file_path = Path(original_file_name)
    # Use only the filename (stem) with .json extension, ignoring any folder path
    output_name = f"{file_path.stem}.json"
    
    # Add prefix if provided
    if output_prefix:
        output_name = f"{output_prefix}/{output_name}"
    
    return output_name


def format_json_output(data: Dict) -> str:
    """
    Format dictionary as pretty JSON string
    
    Args:
        data: Dictionary to format
        
    Returns:
        Formatted JSON string
    """
    return json.dumps(data, indent=2, ensure_ascii=False)


def get_file_extension(file_name: str) -> str:
    """
    Get file extension from file name
    
    Args:
        file_name: File name
        
    Returns:
        File extension (without dot)
    """
    return Path(file_name).suffix[1:].lower() if Path(file_name).suffix else ""

