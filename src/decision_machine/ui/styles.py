from dataclasses import dataclass

@dataclass
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    RED_LIGHT = "\033[91m"
    GREEN_LIGHT = "\033[92m"
    YELLOW_LIGHT = "\033[93m"
    BLUE_LIGHT = "\033[94m"
    MAGENTA_LIGHT = "\033[95m"
    CYAN_LIGHT = "\033[96m"
    BG_GREEN = "\033[42m"
    BG_GREEN_LIGHT = "\033[102m"
    BG_RED = "\033[41m"
    BG_RED_LIGHT = "\033[101m"
    BG_YELLOW = "\033[43m"


class Styles:
    HEADER = f"{Colors.BOLD}{Colors.CYAN}"
    PROS_TEXT = f"{Colors.CYAN}"
    CONS_TEXT = f"{Colors.MAGENTA}"
    JUDGE_TEXT = f"{Colors.YELLOW_LIGHT}"
    SUCCESS = f"{Colors.GREEN}"
    WARNING = f"{Colors.YELLOW}"
    ERROR = f"{Colors.RED}"
    INFO = f"{Colors.CYAN}"

    @staticmethod
    def pros_text(text: str) -> str:
        return f"{Colors.CYAN}{text}{Colors.RESET}"

    @staticmethod
    def cons_text(text: str) -> str:
        return f"{Colors.MAGENTA}{text}{Colors.RESET}"

    @staticmethod
    def judge_text(text: str) -> str:
        return f"{Colors.YELLOW}{text}{Colors.RESET}"
