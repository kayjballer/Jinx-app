"""agents — Jinx : un seul cerveau Qwen + contexte système."""
from .core import JinxCore, get_core
from .director import Director, build_default_director
from .model_manager import ModelManager
from .downloader import ModelDownloader
from .models_catalog import CATALOG, total_mo, humain
