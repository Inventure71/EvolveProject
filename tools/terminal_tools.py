import subprocess
import os
from typing import Optional

TERMINAL_LOG_FILE = "terminal_output.log"


def run_shell_command(command: str, use_sudo: bool = False, sudo_password: Optional[str] = None, sudo_user: str = "root") -> str:
    """
    Runs a shell command on the Linux system, optionally with sudo and a specified sudo user.

    Args:
        command: The shell command to execute.
        use_sudo: Whether to run the command with sudo.
        sudo_password: The sudo password to use (if use_sudo is True).
        sudo_user: The sudo user to run the command as (default: 'root').

    Returns:
        The output (stdout and stderr) of the command, or an error message.
    """
    try:
        if use_sudo:
            if not sudo_password:
                return "Error: sudo_password is required when use_sudo is True."
            # Use 'sudo -u <user>' if a user is specified (default is root)
            full_command = f"echo {sudo_password} | sudo -S -u {sudo_user} {command}"
            shell = True
        else:
            full_command = command
            shell = True
        result = subprocess.run(full_command, shell=shell, capture_output=True, text=True)
        output = result.stdout + result.stderr
        # Log the output
        with open(TERMINAL_LOG_FILE, "a", encoding="utf-8") as log:
            log.write(f"$ {command}\n{output}\n")
        return output.strip()
    except Exception as e:
        return f"Error running command: {e}"


def read_terminal_output(last_n_lines: int = 20) -> str:
    """
    Reads the last N lines of the terminal output log file.

    Args:
        last_n_lines: The number of lines to read from the end of the log file.

    Returns:
        The last N lines of the terminal output, or an error message if the log file does not exist.
    """
    if not os.path.exists(TERMINAL_LOG_FILE):
        return "No terminal output log found."
    try:
        with open(TERMINAL_LOG_FILE, "r", encoding="utf-8") as log:
            lines = log.readlines()
        return "".join(lines[-last_n_lines:]).strip()
    except Exception as e:
        return f"Error reading terminal output: {e}" 