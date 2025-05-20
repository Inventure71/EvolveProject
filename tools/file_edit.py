from typing import Tuple
import os

def edit_file_lines(file_path: str, start_line: int, end_line: int, new_content: str) -> str:
    """
    Edits specific lines in a file, replacing them with new content.

    Args:
        file_path: The path to the file to edit.
        start_line: The first line number to replace (1-indexed, inclusive).
        end_line: The last line number to replace (1-indexed, inclusive).
        new_content: The content to insert in place of the specified lines.

    Returns:
        A string message indicating success or the error encountered.
    """
    print(f"[DEBUG] edit_file_lines called for: {file_path}, lines {start_line}-{end_line}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        # Save old version for debugging
        debug_dir = 'file_edit_debug'
        os.makedirs(debug_dir, exist_ok=True)
        old_file_path = os.path.join(debug_dir, os.path.basename(file_path) + '_old')
        with open(old_file_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        # Convert to 0-indexed
        start = start_line - 1
        end = end_line
        new_lines = new_content.splitlines(keepends=True)
        # If new_content doesn't end with a newline, add it
        if new_lines and not new_lines[-1].endswith('\n'):
            new_lines[-1] += '\n'
        updated_lines = lines[:start] + new_lines + lines[end:]
        # Save new version for debugging
        new_file_path = os.path.join(debug_dir, os.path.basename(file_path) + '_new')
        with open(new_file_path, 'w', encoding='utf-8') as f:
            f.writelines(updated_lines)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(updated_lines)
        return f"Lines {start_line}-{end_line} in {file_path} successfully edited. Debug files saved."
    except Exception as e:
        return f"Error editing file: {e}" 