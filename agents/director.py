"""agents/director.py — Orchestrateur. Chaque agent a son modèle."""
from __future__ import annotations

import json
import logging
import ssl
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib import request

try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _SSL_CTX = ssl.create_default_context()

from .base import Agent
from .workers import (MathAgent, DictionnaireAgent,
                      MemoryAgent, CodeAgent)
from .conversations import ConversationStore
from .model_manager import ModelManager
from .permissions import PermissionManager, Niveau, get_perms
from .researcher import ResearcherAgent, WebCache
from .system_agent import SystemAgent
from .jarvis_agents import (AlarmAgent, CalendarAgent,
                             MediaAgent, SystemControlAgent)

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
        self._conv_store = None
        self.perms: Optional[PermissionManager] = None

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
            top = scores[0][1]
            if self.perms:
                peut, besoin_confirm, niv = self.perms.peut_executer(top)
                if besoin_confirm:
                    return ["__CONFIRM__" + top]
            return [top]
        return ["__LLM__"]

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
                with request.urlopen(req, timeout=300, context=_SSL_CTX) as r:
                    body = json.loads(r.read().decode("utf-8"))
                return body["choices"][0]["message"]["content"].strip()
            except Exception as e:
                return f"Erreur modele {model_name} : {e}"
        return _call

    def _init_conv_store(self, dossier: str) -> None:
        if self._conv_store is None:
            try:
                self._conv_store = ConversationStore(dossier)
            except Exception as e:
                log.warning("conv_store: %s", e)

    def _log_conversation(self, query: str, reponse: str, agents: list) -> None:
        if self._conv_store is None:
            return
        try:
            self._conv_store.enregistrer(query, reponse, ",".join(agents))
        except Exception as e:
            log.warning("log conv: %s", e)


    def confirmer_action(self, agent: str, query: str,
                         context: Optional[Dict[str, Any]] = None) -> str:
        """Exécute une action critique APRÈS confirmation utilisateur."""
        if agent not in self.agents:
            return f"Agent {agent} inconnu."
        try:
            ctx = dict(context or {})
            ctx["confirmed"] = True
            return self.agents[agent].run(query, ctx)
        except Exception as e:
            log.exception("confirmer_action %s", agent)
            return f"Erreur : {e}"

    def niveau_agent(self, agent: str) -> str:
        if not self.perms:
            return "passif"
        return self.perms.niveau(agent).value

    def handle(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        context = dict(context or {})
        picked = self.select_agents(query)
        if not picked:
            return "Aucun agent."

        # Cas spécial : action critique → demander confirmation
        if picked and picked[0].startswith("__CONFIRM__"):
            agent_name = picked[0].replace("__CONFIRM__", "")
            return f"[JINX_CONFIRM]{agent_name}|||{query}|||Action sensible : {agent_name}"

        # Cas spécial : LLM direct (plus d'agent echo)
        if picked and picked[0] == "__LLM__":
            llm_fn = context.get("llm_fn")
            if not llm_fn:
                return "Aucun agent disponible pour cette demande."
            try:
                memoire = context.get("memoire", "")
                exemples = context.get("exemples", [])
                rep = llm_fn(query, (memoire, exemples))
                self._log_conversation(query, rep, ["llm"])
                return rep
            except Exception as e:
                log.exception("LLM direct")
                return f"Erreur LLM : {e}"
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
            final = r.output if r.success else f"Erreur : {r.error}"
            self._log_conversation(query, final, [r.agent])
            return final
        final = "\n".join(
            f"- {r.agent} : {r.output}" if r.success
            else f"- {r.agent} : echec ({r.error})" for r in results)
        self._log_conversation(query, final, [r.agent for r in results])
        return final

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
    d.register(SystemAgent(dossier))
    d.register(AlarmAgent(dossier))
    d.register(CalendarAgent(dossier))
    d.register(MediaAgent(dossier))
    d.register(SystemControlAgent(dossier))
    d.register(MathAgent(dossier))
    d.register(DictionnaireAgent(dossier))
    d.register(MemoryAgent(dossier))
    d.register(ResearcherAgent(dossier))
    d.register(CodeAgent(dossier))
    d.perms = PermissionManager(dossier)
    return d
