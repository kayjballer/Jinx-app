"""agents/director.py — Orchestrateur. Chaque agent a son modèle."""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib import request

from .base import Agent
from .workers import (TimeAgent, MathAgent, DictionnaireAgent,
                      MemoryAgent, CodeAgent, EchoAgent)
from .model_manager import ModelManager

log = logging.getLogger("jinx.director")


@dataclass
class AgentResult:
    agent: str
    output: str
    success: bool = True
    error: Optional[str] = None
    elapsed: float = 0.0


class Director:
    SEUIL = 0.50

    def __init__(self, model_manager: Optional[ModelManager] = None):
        self.agents: Dict[str, Agent] = {}
        self.model_manager = model_manager
        self.history: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def register(self, agent: Agent) -> None:
        with self._lock:
            self.agents[agent.name] = agent
            log.info("Agent : %s -> modele %s", agent.name, agent.requires_model)

    def list_agents(self):
        return list(self.agents.keys())

    def get_agents_info(self):
        out = []
        for a in self.agents.values():
            out.append({
                "name": a.name,
                "description": a.description,
                "keywords": list(a.keywords),
                "db": a.db.path.split("/")[-1] if a.db else None,
                "db_mo": round(a.db.size_mo(), 1) if a.db else 0,
                "model": a.requires_model,
            })
        return out

    def select_agents(self, query: str, max_agents: int = 1) -> List[str]:
        scores: List[Tuple[float, str]] = []
        for name, agent in self.agents.items():
            if name == "echo":
                continue
            try:
                s = agent.match(query)
            except Exception as e:
                log.warning("match(%s): %s", name, e)
                s = 0.0
            if s >= self.SEUIL:
                scores.append((s, name))
        scores.sort(reverse=True, key=lambda t: t[0])
        if scores:
            return [scores[0][1]]
        return ["echo"]

    def _llm_pour(self, model_name: str, url: str):
        def _call(prompt: str, context: Dict[str, Any]) -> str:
            messages = [{"role": "user", "content": prompt}]
            payload = {
                "messages": messages,
                "temperature": context.get("temperature", 0.3),
                "max_tokens": context.get("max_tokens", 512),
                "stream": False,
            }
            data = json.dumps(payload).encode("utf-8")
            req = request.Request(url, data=data,
                                  headers={"Content-Type": "application/json"})
            try:
                with request.urlopen(req, timeout=300) as r:
                    body = json.loads(r.read().decode("utf-8"))
                return body["choices"][0]["message"]["content"].strip()
            except Exception as e:
                return f"Erreur modele {model_name} : {e}"
        return _call

    def handle(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        context = dict(context or {})
        picked = self.select_agents(query)
        if not picked:
            return "Aucun agent."
        results: List[AgentResult] = []
        for name in picked:
            agent = self.agents[name]
            t0 = time.time()
            llm_fn = None
            if agent.requires_model and self.model_manager:
                url = self.model_manager.ensure(agent.requires_model)
                if url:
                    llm_fn = self._llm_pour(agent.requires_model, url)
                    log.info("Agent %s sur modele %s", name, agent.requires_model)
                else:
                    log.warning("Modele %s indispo pour %s",
                                agent.requires_model, name)
            agent.llm_fn = llm_fn
            try:
                out = agent.run(query, context)
                results.append(AgentResult(name, out, True, None, time.time() - t0))
            except Exception as e:
                log.exception("Agent %s plante", name)
                results.append(AgentResult(name, "", False, str(e), time.time() - t0))
        if len(results) == 1:
            r = results[0]
            return r.output if r.success else f"Erreur : {r.error}"
        return "\n".join(
            f"- {r.agent} : {r.output}" if r.success
            else f"- {r.agent} : echec ({r.error})" for r in results)

    def handle_async(self, query, callback, context=None):
        def worker():
            try:
                out = self.handle(query, context)
            except Exception as e:
                out = f"Erreur directeur : {e}"
            try:
                from kivy.clock import Clock
                Clock.schedule_once(lambda *_: callback(out), 0)
            except Exception:
                callback(out)
        threading.Thread(target=worker, daemon=True).start()


def build_default_director(dossier: str,
                           model_manager: Optional[ModelManager] = None) -> Director:
    d = Director(model_manager=model_manager)
    d.register(TimeAgent(dossier))
    d.register(MathAgent(dossier))
    d.register(DictionnaireAgent(dossier))
    d.register(MemoryAgent(dossier))
    d.register(CodeAgent(dossier))
    d.register(EchoAgent(dossier))
    return d
