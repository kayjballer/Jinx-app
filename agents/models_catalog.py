"""agents/models_catalog.py — Qwen 3.5 2B (modèle unique)."""
_HF = "https://huggingface.co"

CATALOG = {
    "default": {
        "nom": "Qwen3.5-2B-Instruct",
        "url": f"{_HF}/Qwen/Qwen3.5-2B-Instruct-GGUF/resolve/main/qwen3.5-2b-instruct-q4_k_m.gguf",
        "taille_mo": 1200,
        "port": 8080,
    },
}


def total_mo() -> int:
    return sum(m["taille_mo"] for m in CATALOG.values())


def humain(mo: int) -> str:
    return f"{mo/1024:.1f} Go" if mo >= 1024 else f"{mo} Mo"


def modele_pour_agent(agent: str) -> str:
    return "default"
