import state
from logger import log_print
import sys



# At top of main.py, after imports
def color_text(text, color):
    """ANSI colors for terminal—light green/red for trends."""
    colors = {
        'light_green': '\033[92m',
        'light_red': '\033[91m',
        'reset': '\033[0m'
    }
    return f"{colors.get(color, '')}{text}{colors['reset']}"
