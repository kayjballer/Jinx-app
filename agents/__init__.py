"""agents — Jinx (1 cerveau Qwen 3.5 2B)."""
from .core import JinxCore, get_core
from .director import Director, build_default_director
from .model_manager import ModelManager
from .models_catalog import CATALOG, total_mo, humain
from .downloader import ModelDownloader
