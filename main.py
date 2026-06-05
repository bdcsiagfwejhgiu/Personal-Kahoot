import os
import re
import sys
import json
from kahoot_connector import KahootConnector
from openrouter_client import OpenRouterClient

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


def parse_question_block(block_lines):
    question_text = None
    answers = []
    for line in block_lines[1:]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('- "') and stripped.endswith('"'):
            clean = stripped[3:-1]
            if question_text is None:
                question_text = clean
            else:
                answers.append(clean)
        elif stripped.startswith('- '):
            answer_match = re.match(r'-\s*"(.+)"', stripped)
            if answer_match:
                answers.append(answer_match.group(1))
    return question_text, answers


def send_answer_to_joiner(proc, index):
    if proc.stdin is None:
        return
    # send 1-based index to be explicit (join_kahoot.js accepts 0-based or 1-based)
    proc.stdin.write(f'ANSWER: {index + 1}\n')
    proc.stdin.flush()


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

    openrouter_client = None
    try:
        openrouter_client = OpenRouterClient()
        success('OpenRouter client ready.')
    except Exception as exc:
        warning(f'OpenRouter not enabled: {exc}')
        openrouter_client = None
    if proc is None:
        error(f"Failed to start joiner: {msg}")
        sys.exit(1)

    success("Joiner started. Output will stream below; press Ctrl+C to exit.")

    try:
        cleared = False
        question_block = []
        collecting_question = False

        def flush_question_block():
            nonlocal question_block, collecting_question
            if not question_block:
                return
            question_text, answers = parse_question_block(question_block)
            if question_text and answers and openrouter_client:
                try:
                    # show payload being sent for transparency
                    payload = openrouter_client._build_payload(question_text, answers)
                    info('Sending question+choices to OpenRouter...')
                    print(json.dumps(payload, indent=2, ensure_ascii=False))

                    index, normalized, raw_text = openrouter_client.select_choice(question_text, answers)
                    info(f'OpenRouter raw response: {raw_text}')
                    info(f'OpenRouter normalized response: {normalized}')
                    info(f'OpenRouter selected choice {index + 1}: "{answers[index]}"')
                    send_answer_to_joiner(proc, index)
                except Exception as exc:
                    warning(f'OpenRouter selection failed: {exc}')
            question_block = []
            collecting_question = False

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
            if line.startswith('- Question '):
                if collecting_question:
                    flush_question_block()
                collecting_question = True
                question_block = [line]
                print(line)
                continue
            if collecting_question and (line.startswith(' ') or line.startswith('\t') or line.startswith('- ')):
                question_block.append(line)
                print(line)
                continue
            if collecting_question:
                flush_question_block()
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
        if collecting_question:
            flush_question_block()
    except KeyboardInterrupt:
        info("Stopping...")
        proc.terminate()


if __name__ == '__main__':
    main()
