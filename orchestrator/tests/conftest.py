import sys
from pathlib import Path

# Ensure `src/` is importable in tests without installing the package.
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# For E2E tests, we also import config_service as the top-level `src` package.
MONOREPO_ROOT = ROOT.parent
CONFIG_SERVICE_ROOT = MONOREPO_ROOT / "config_service"
if str(CONFIG_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(CONFIG_SERVICE_ROOT))
