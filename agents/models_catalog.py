"""agents/models_catalog.py — Modèles GGUF par agent."""
_HF = "https://huggingface.co"

CATALOG = {
    "time": {
        "nom": "Qwen2.5-0.5B-Instruct",
        "url": f"{_HF}/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf",
        "taille_mo": 400, "sha256": "", "port": 8091},
    "math": {
        "nom": "Qwen2.5-Math-1.5B-Instruct",
        "url": f"{_HF}/bartowski/Qwen2.5-Math-1.5B-Instruct-GGUF/resolve/main/Qwen2.5-Math-1.5B-Instruct-Q4_K_M.gguf",
        "taille_mo": 1050, "sha256": "", "port": 8092},
    "dictionnaire": {
        "nom": "Qwen2.5-1.5B-Instruct",
        "url": f"{_HF}/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "taille_mo": 1500, "sha256": "", "port": 8093},
    "memory": {
        "nom": "Qwen2.5-0.5B-Instruct",
        "url": f"{_HF}/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf",
        "taille_mo": 400, "sha256": "", "port": 8094},
    "code": {
        "nom": "Qwen2.5-Coder-3B-Instruct",
        "url": f"{_HF}/bartowski/Qwen2.5-Coder-3B-Instruct-GGUF/resolve/main/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf",
        "taille_mo": 2100, "sha256": "", "port": 8095},
    "echo": {
        "nom": "Qwen2.5-3B-Instruct",
        "url": f"{_HF}/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf",
        "taille_mo": 2000, "sha256": "", "port": 8096},
}


def total_mo() -> int:
    return sum(m["taille_mo"] for m in CATALOG.values())


def humain(mo: int) -> str:
    return f"{mo/1024:.1f} Go" if mo >= 1024 else f"{mo} Mo"
