"""agents/models_catalog.py — Qwen 2.5 1.5B Instruct (modèle unique)."""

_HF = "https://huggingface.co"

CATALOG = {
    "default": {
        "nom": "Qwen2.5-1.5B-Instruct",
        "url": f"{_HF}/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "taille_mo": 1100,
        "port": 8080,
    },
}


def total_mo() -> int:
    return sum(m["taille_mo"] for m in CATALOG.values())


def humain(mo: int) -> str:
    return f"{mo/1024:.1f} Go" if mo >= 1024 else f"{mo} Mo"


def modele_pour_agent(agent: str) -> str:
    return "default"
