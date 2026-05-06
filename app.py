import sys
from importlib import import_module
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

app = import_module("agent.api.main").app
