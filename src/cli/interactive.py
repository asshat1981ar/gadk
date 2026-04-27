"""Interactive REPL for the Cognitive Foundry swarm CLI."""

import os
import sys

try:
    from prompt_toolkit import PromptSession
except ImportError:
    PromptSession = None
try:
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
except ImportError:
    AutoSuggestFromHistory = None
try:
    from prompt_toolkit.completion import NestedCompleter
except ImportError:
    NestedCompleter = None
try:
    from prompt_toolkit.history import FileHistory
except ImportError:
    FileHistory = None
try:
    from prompt_toolkit.key_binding import KeyBindings
except ImportError:
    KeyBindings = None
try:
    from prompt_toolkit.styles import Style
except ImportError:
    Style = None

from src.cli import swarm_cli
from src.cli.swarm_ctl import clear_shutdown
from src.observability.logger import get_logger

logger = get_logger("interactive")

HISTORY_FILE = ".swarm_history"

COMMANDS = {
    "status": None,
    "prompt": None,
    "stop": None,
    "tasks": {"--status": None, "--state-file": None, "--events-file": None},
    "logs": {"--file": None, "--tail": None},
    "metrics": None,
    "events": {"--task": None, "--tail": None, "--state-file": None, "--events-file": None},
    "dashboard": {"--refresh": None, "--state-file": None, "--events-file": None},
    "queue": None,
    "help": None,
    "clear": None,
    "exit": None,
    "quit": None,
}

if Style is not None:
    SWARM_STYLE = Style.from_dict(
        {
            "prompt": "ansicyan bold",
            "command": "ansigreen",
            "arg": "ansiyellow",
        }
    )
else:
    SWARM_STYLE = None


def get_banner() -> str:
    return """
╔═══════════════════════════════════════════════════════════╗
║     Cognitive Foundry Swarm Interactive Shell             ║
║                                                           ║
║  Commands: status, prompt, stop, tasks, logs, metrics     ║
║            events, dashboard, queue, help, clear, exit    ║
╚═══════════════════════════════════════════════════════════╝
""".strip()


def get_help_text() -> str:
    return """
Available commands:
  status                          Show swarm status
  prompt <message>                Inject a prompt into the swarm queue
  stop                            Request swarm shutdown
  tasks [--status STATUS]         List tasks, optionally filtered
  logs [--file FILE] [--tail N]   View logs
  metrics                         Show metrics summary
  events [--task ID] [--tail N]   Show audit events
  dashboard [--refresh RATE]      Launch live dashboard
  queue                           Show pending prompts
  help                            Show this help message
  clear                           Clear the screen
  exit / quit                     Exit the interactive shell

All commands support --state-file and --events-file options.
""".strip()


def _dispatch_command(command: str, args: list[str]) -> None:
    """Delegate to the existing CLI parser and surface non-zero exits."""
    try:
        ret = swarm_cli.main([command] + args)
        if ret and ret != 0:
            print(f"Command exited with code {ret}")
    except SystemExit as e:
        if e.code and e.code != 0:
            print(f"Command exited with code {e.code}")
    except Exception as e:
        logger.exception(f"Error executing command: {command}")
        print(f"Error: {e}")


def run_interactive() -> int:
    clear_shutdown()
    if PromptSession is None:
        print("prompt_toolkit is not installed; falling back to plain input.")
        _run_interactive_fallback()
        return 0

    history_path = os.path.join(os.getcwd(), HISTORY_FILE)
    session: PromptSession = PromptSession(
        history=FileHistory(history_path),
        auto_suggest=AutoSuggestFromHistory(),
        completer=NestedCompleter.from_nested_dict(COMMANDS),
        style=SWARM_STYLE,
    )

    bindings = KeyBindings()

    @bindings.add("c-c")
    def _(event):
        event.app.exit(exception=KeyboardInterrupt, style="class:aborting")

    print(get_banner())
    print()

    while True:
        try:
            text = session.prompt(
                [("class:prompt", "swarm"), ("class:prompt", "> ")],
                key_bindings=bindings,
            )
        except KeyboardInterrupt:
            print("\nUse 'exit' to quit.")
            continue
        except EOFError:
            print("\nExiting...")
            break

        text = text.strip()
        if not text:
            continue

        parts = text.split()
        command = parts[0].lower()
        args = parts[1:]

        if command in ("exit", "quit"):
            print("Exiting swarm shell.")
            break

        if command == "help":
            print(get_help_text())
            continue

        if command == "clear":
            os.system("clear" if os.name != "nt" else "cls")  # nosec B605 - hardcoded literal command, no user input
            continue

        if command not in COMMANDS:
            print(f"Unknown command: '{command}'. Type 'help' for available commands.")
            continue

        _dispatch_command(command, args)

    return 0


def _run_interactive_fallback() -> None:
    """Minimal fallback loop when prompt_toolkit is unavailable."""
    print(get_banner())
    print()
    while True:
        try:
            text = input("swarm> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break

        if not text:
            continue

        parts = text.split()
        command = parts[0].lower()
        args = parts[1:]

        if command in ("exit", "quit"):
            print("Exiting swarm shell.")
            break

        if command == "help":
            print(get_help_text())
            continue

        if command == "clear":
            os.system("clear" if os.name != "nt" else "cls")  # nosec B605 - hardcoded literal command, no user input
            continue

        if command not in COMMANDS:
            print(f"Unknown command: '{command}'. Type 'help' for available commands.")
            continue

        _dispatch_command(command, args)


if __name__ == "__main__":
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    sys.exit(run_interactive())
