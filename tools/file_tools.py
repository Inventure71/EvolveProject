# This file is used to read all the files in a directory, including subdirectories

import os
import sys
from typing import Dict, Any, Optional
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
print(os.path.dirname(__file__))

# Directory tree or folder hierarchy.
def create_structure(path: Optional[str], prefix: str, respect_gitignore: bool) -> str:
    """
    Generate a directory tree string for the given path, similar to the 'tree' command output.

    Args:
        path: The root directory path. If None, uses the project root directory.
        prefix: Prefix for formatting the tree (used internally for recursion).
        respect_gitignore: If True, skips directories/files listed in .gitignore (top-level only).

    Returns:
        A string representing the directory tree structure.
    """
    print(f"[DEBUG] create_structure called for: path={path}, prefix={prefix}, respect_gitignore={respect_gitignore}")
    if not path:
        # Assume project root is two levels up from this file (agent_folder/tools/ -> Project_SYNTAX/)
        path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
    ignored = set()
    # Always ignore .git directory
    ignored.add('.git')
    if respect_gitignore:
        # Read .gitignore from project root
        gitignore_path = os.path.join(path, '.gitignore')
        if os.path.exists(gitignore_path):
            with open(gitignore_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Only handle top-level ignores like /DEV or /.venv
                        if line.startswith('/'):
                            ignored.add(line[1:])
                        else:
                            ignored.add(line)
    def _tree(current_path, prefix, is_root=False):
        entries = sorted(os.listdir(current_path))
        if is_root:
            # Always filter .git, and filter top-level entries if respect_gitignore
            entries = [e for e in entries if e not in ignored]
        entries_count = len(entries)
        for idx, entry in enumerate(entries):
            full_path = os.path.join(current_path, entry)
            connector = "└── " if idx == entries_count - 1 else "├── "
            tree_strs.append(prefix + connector + entry)
            if os.path.isdir(full_path):
                extension = "    " if idx == entries_count - 1 else "│   "
                _tree(full_path, prefix + extension)
    tree_strs = []
    tree_str = os.path.basename(os.path.abspath(path)) + "/\n"
    _tree(path, "", is_root=True)
    return tree_str + "\n".join(tree_strs)

def read_directory(path: str, add_line_numbers: bool) -> Dict[str, Any]:
    """
    Recursively reads all files in a directory (or a single file), returning their contents.

    Args:
        path: The directory or file path to read.
        add_line_numbers: If True, adds line numbers to each line of file content.

    Returns:
        A dictionary mapping file paths to a tuple of (filename, content).
    """
    print(f"[DEBUG] read_directory called for: path={path}, add_line_numbers={add_line_numbers}")
    information = {}
    
    # Check if path is a file instead of a directory
    if os.path.isfile(path):
        # Add check to ignore .DS_Store if the path is a single file
        if os.path.basename(path) == ".DS_Store":
            print(f"Skipping .DS_Store file at: {path}")
            return information # Return empty if it's a .DS_Store file

        with open(path, "r") as f:
            content = f.read()
            if add_line_numbers:
                # Add line numbers to each line (1-indexed like in modify_code.py)
                lines = content.split('\n')
                numbered_lines = [f"{i}: {line}" for i, line in enumerate(lines, 1)]
                content = '\n'.join(numbered_lines)
            information[path] = [os.path.basename(path), content]
        return information
        
    # Process directory
    for directory in os.listdir(path):
        # Add check to ignore .DS_Store
        if directory == ".DS_Store":
            print(f"Skipping .DS_Store directory entry: {os.path.join(path, directory)}")
            continue

        full_path = os.path.join(path, directory)
        print(directory)
        if os.path.isdir(full_path):
            info = read_directory(full_path, add_line_numbers)
            information.update(info)
        else:
            print(full_path)
            with open(full_path, "r") as f:
                content = f.read()
                if add_line_numbers:
                    # Add line numbers to each line (1-indexed like in modify_code.py)
                    lines = content.split('\n')
                    numbered_lines = [f"{i}: {line}" for i, line in enumerate(lines, 1)]
                    content = '\n'.join(numbered_lines)
                information[full_path] = [directory, content]
    return information



if __name__ == "__main__":
    information = read_directory("common", add_line_numbers=True)

    print(information)
    #for key, value in information.items():
    #    print(key)

    print(create_structure(None, "", True))

    print("--------------------------------"*5)

    print(create_structure("assets", "", True))


    
