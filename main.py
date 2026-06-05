import os
import sys
from kahoot_connector import KahootConnector

class Colors:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"

    @staticmethod
    def wrap(text, style):
        return f"{style}{text}{Colors.RESET}"


def prompt_yes_no(prompt, default=True):
    ans = input(f"{prompt} [{'Y/n' if default else 'y/N'}]: ").strip().lower()
    if not ans:
        return default
    return ans.startswith('y')


def info(text):
    print(f"{Colors.CYAN}[INFO]{Colors.RESET} {text}")


def success(text):
    print(f"{Colors.GREEN}[OK]{Colors.RESET} {text}")


def warning(text):
    print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {text}")


def error(text):
    print(f"{Colors.RED}[ERROR]{Colors.RESET} {text}")


def clear_terminal():
    os.system('cls' if os.name == 'nt' else 'clear')


def main():
    print(f"{Colors.BOLD}{Colors.CYAN}Kahoot quick join{Colors.RESET}")
    pin = input("Enter game PIN: ").strip()
    if not pin.isdigit():
        error("Invalid PIN. Must be numeric.")
        sys.exit(1)

    use_random = prompt_yes_no("Use random name?")
    nickname = None
    if not use_random:
        nickname = input("Enter nickname to use: ").strip()
        if not nickname:
            error("Nickname cannot be empty.")
            sys.exit(1)

    connector = KahootConnector()

    info("Resolving PIN to quiz ID...")
    result = connector.resolve_pin(pin)
    quiz_id = result.get('quiz_id') if isinstance(result, dict) else None
    if quiz_id:
        success(f"Quiz ID: {quiz_id}")
    else:
        error(f"Could not resolve quiz ID: {result.get('error', 'unknown error')}")
        warning("Continuing with PIN join anyway; the joiner can often connect directly using the PIN.")

    name_to_use = nickname if nickname else None
    info(f"Attempting to join as {'random name' if not name_to_use else name_to_use}...")
    proc, msg = connector.join(pin, name_to_use)
    if proc is None:
        error(f"Failed to start joiner: {msg}")
        sys.exit(1)

    success("Joiner started. Output will stream below; press Ctrl+C to exit.")

    try:
        cleared = False
        for line in proc.stdout:
            if isinstance(line, bytes):
                line = line.decode(errors='ignore')
            line = line.rstrip()
            if not line:
                continue
            if not cleared and ('Joined successfully' in line or '[OK] Joined successfully' in line):
                clear_terminal()
                cleared = True
                info('Connected. Terminal cleared. Waiting for questions...')
            if line.startswith('Loaded '):
                print(f"{Colors.GREEN}{line}{Colors.RESET}")
            elif line.startswith('[OK]') or 'Joined successfully' in line:
                print(f"{Colors.GREEN}{line}{Colors.RESET}")
            elif line.startswith('Failed to join:') or line.startswith('Error:') or line.startswith('Unhandled') or '[ERROR]' in line:
                print(f"{Colors.RED}{line}{Colors.RESET}")
            elif line.startswith('[WARN]') or 'Disconnect:' in line:
                print(f"{Colors.YELLOW}{line}{Colors.RESET}")
            elif '[EVENT]' in line:
                print(f"{Colors.CYAN}{line}{Colors.RESET}")
            elif '[DETAIL]' in line:
                print(f"{Colors.YELLOW}{line}{Colors.RESET}")
            else:
                print(line)
    except KeyboardInterrupt:
        info("Stopping...")
        proc.terminate()


if __name__ == '__main__':
    main()
