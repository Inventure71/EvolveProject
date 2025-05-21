from typing import Tuple
import os

def create_file(file_path: str, content: str) -> str:
    """
    Creates a file at the specified path and writes the given content to it.

    Args:
        file_path: The path where the file will be created. Parent directories will be created if they do not exist.
        content: The content to write into the file.

    Returns:
        A string message indicating success or the error encountered.
    """
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"File created successfully at {file_path}."
    except Exception as e:
        return f"Error creating file: {e}" 