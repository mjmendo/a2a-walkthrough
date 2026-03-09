import sys, os

_this = os.path.dirname(os.path.abspath(__file__))

# Ensure this pattern's directory is first in sys.path
if _this in sys.path:
    sys.path.remove(_this)
sys.path.insert(0, _this)

# Evict modules with names that are reused across pattern directories
# (agents, main, run_demo) if they were loaded from a different pattern dir
_SHARED_NAMES = {"agents", "main", "run_demo"}
for _name in list(sys.modules.keys()):
    if _name.split(".")[0] in _SHARED_NAMES:
        _src = getattr(sys.modules.get(_name), "__file__", None) or ""
        if _src and not _src.startswith(_this):
            del sys.modules[_name]
