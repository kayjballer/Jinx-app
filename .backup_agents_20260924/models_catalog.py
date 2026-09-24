"""agents/models_catalog.py — 2 modèles (Phase B optimisation)."""

_HF = "https://huggingface.co"

MODELE_RAPIDE = {
    "nom": "Qwen2.5-0.5B-Instruct",
    "url": f"{_HF}/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf",
    "taille_mo": 400,
    "port": 8080,
}

MODELE_INTELLIGENT = {
    "nom": "Qwen2.5-3B-Instruct",
    "url": f"{_HF}/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf",
    "taille_mo": 2000,
    "port": 8081,
}

AGENT_VERS_MODELE = {
    "time": "rapide",
    "memory": "rapide",
    "math": "rapide",
    "dictionnaire": "rapide",
    "alarm": "rapide",
    "media": "rapide",
    "calendar": "rapide",
    "system_control": "rapide",
    "system": "rapide",
    "conversations": "rapide",
    "code": "intelligent",
    "researcher": "intelligent",
    "echo": "intelligent",
}

CATALOG = {
    "rapide": MODELE_RAPIDE,
    "intelligent": MODELE_INTELLIGENT,
}


def total_mo() -> int:
    return sum(m["taille_mo"] for m in CATALOG.values())


def humain(mo: int) -> str:
    return f"{mo/1024:.1f} Go" if mo >= 1024 else f"{mo} Mo"


def modele_pour_agent(agent: str) -> str:
    return AGENT_VERS_MODELE.get(agent, "rapide")
