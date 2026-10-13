"""LangGraph workflow: evidence specialist -> route -> advisory specialist -> MCP staging -> human review."""
from contextlib import asynccontextmanager
from datetime import timedelta
import json
import os
from pathlib import Path
import sys
from typing import TypedDict
from urllib.parse import urlparse

import httpx
from langgraph.graph import END, START, StateGraph
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from rag import build_prompt, detect_language, is_crop_prompt, prefill_of, tidy_answer

from .knowledge import fetch_is_relevant, needs_region, validate_query, validate_region
from .store import Store, digest

ROOT = Path(__file__).resolve().parents[1]
FAO_URL = "https://www.fao.org/fall-armyworm/en/"
# Same stop strings as the existing app (app.py).
MODEL_STOP = ["<|im_end|>", "<|im_start|>", "FARMER'S MESSAGE:", "REFERENCE INFORMATION:", "\nQUESTION:"]


@asynccontextmanager
async def session(parameters):
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=20)) as client:
            await client.initialize()
            yield client


async def call(client, name, arguments):
    response = await client.call_tool(name, arguments, read_timeout_seconds=timedelta(seconds=20))
    if response.isError:
        raise ValueError("MCP tool failed: " + " ".join(getattr(c, "text", "") for c in response.content))
    if response.structuredContent is not None:
        return response.structuredContent
    return json.loads("".join(c.text for c in response.content if c.type == "text"))


class EvidenceAgent:
    """Bounded read-only plan; all agricultural lookups go through real MCP calls."""
    async def run(self, client, query, region):
        evidence = await call(client, "search_extension_knowledge", {"query": query})
        urgency = await call(client, "assess_extension_urgency", {"query": query})
        context = await call(client, "get_natural_region_context", {"region": region}) if region else None
        return {"evidence": evidence, "urgency": urgency, "region": context}


async def fetch_external():
    # Actual third-party server maintained by the MCP project, not a custom HTTP tool.
    # Only a fixed public reference URL is sent; farmer messages are never sent to Fetch.
    network_keys = {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "http_proxy",
                    "https_proxy", "all_proxy", "no_proxy", "SSL_CERT_FILE",
                    "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"}
    network_env = {key: value for key, value in os.environ.items() if key in network_keys}
    parameters = StdioServerParameters(command=sys.executable, args=["-m", "mcp_server_fetch"],
                                       cwd=str(ROOT), env=network_env)
    async with session(parameters) as client:
        result = await client.call_tool("fetch", {"url": FAO_URL, "max_length": 3000},
                                        read_timeout_seconds=timedelta(seconds=15))
        if result.isError:
            raise ValueError("Third-party Fetch MCP returned an error")
        text = "\n".join(c.text for c in result.content if c.type == "text")
        if not text.strip():
            raise ValueError("Third-party Fetch MCP returned no text")
        return {"url": FAO_URL, "text": text[:3000]}


class AdvisoryAgent:
    """Local LLM drafts when configured; evidence-only template works without weights.

    AI mode reuses the existing app's tested prompt path (rag.build_prompt: Qwen
    chat layout, answer started by the app, condition named from the matched
    entry) and its output clean-up (rag.tidy_answer). A free-form JSON prompt
    was tried first; on the 1.5B model that style of prompt ran on past the
    answer and invented entries, and its ~1,500-token prompt took minutes to
    read on a farm laptop."""
    def __init__(self, model_url=None, timeout=300):
        if model_url:
            parsed = urlparse(model_url)
            if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
                raise ValueError("Model endpoint must be local HTTP; farmer data stays on-device")
        self.model_url = model_url
        self.timeout = timeout

    @staticmethod
    def footer(facts):
        ids = ", ".join(s["id"] for s in facts["evidence"]["sources"])
        return ("\n\nSources: " + ids + " (Murimi Fara knowledge base)\n"
                + facts["urgency"]["referral"] + ". Draft for officer review - not yet approved.")

    async def run(self, query, facts):
        evidence = facts["evidence"]
        sources = evidence["sources"]
        if not self.model_url:
            text = "For review: these reference entries match your question; confirm the cause with an officer.\n"
            text += "\n\n".join(f"[{s['id']}] {s['text']}" for s in sources)
            text += "\n\n" + facts["urgency"]["referral"] + ". Do not use this draft before review."
            return text[:6000], "grounded_template"
        # No tool or review credentials are exposed to the model. External page content
        # is deliberately excluded: third-party text must not become instructions.
        chunks = [s["text"] for s in sources]
        message = query
        if facts.get("region"):
            # Worded without "my farm is", which the app would read as a problem report.
            message += "\n(Farm location: Natural Region %s.)" % facts["region"]["region"]
            if facts["region"]["text"] not in chunks:
                chunks.append(facts["region"]["text"])
        prompt = build_prompt(message, chunks, domain=evidence["domain"],
                              language=detect_language(query))
        async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as http:
            response = await http.post(self.model_url, json={
                "prompt": prompt, "n_predict": 350, "temperature": 0.3, "repeat_penalty": 1.1,
                "cache_prompt": True, "stream": False, "stop": MODEL_STOP})
            response.raise_for_status()
            raw = prefill_of(prompt) + response.json().get("content", "")
        text, _ = tidy_answer(raw, crop=is_crop_prompt(prompt), query=query)
        if not 20 <= len(text) <= 5500:
            raise ValueError("Local model returned an empty or oversized draft")
        return text + self.footer(facts), "local_llm"


class AgentState(TypedDict, total=False):
    query: str
    region: str
    facts: dict
    external_status: str
    external_text: str
    urgent: bool
    text: str
    generation: str
    result: dict


URGENT_BANNER = ("URGENT - the signs match a time-critical condition. Contact a veterinary "
                 "officer or animal-health worker TODAY; do not wait for this advisory.\n\n")


def build_graph(client, store, writer, online=False, require_external=False):
    """The agent's workflow as a LangGraph state machine.

    gather_evidence -> (clarify | urgent_referral | fetch_reference | skip_reference
    | write_draft) -> write_draft -> stage_for_review. Every route decision is
    written to the audit log, so a reviewer can see which path the agent took."""

    def route(name, **detail):
        store.log("route_selected", "orchestrator", {"route": name, **detail})

    async def gather_evidence(state):
        facts = await EvidenceAgent().run(client, state["query"], state.get("region", ""))
        return {"facts": facts, "urgent": bool(facts["evidence"]["urgent"]),
                "external_status": "not_requested", "external_text": ""}

    def after_evidence(state):
        evidence = state["facts"]["evidence"]
        if not evidence["grounded"] or evidence["blocked"]:
            route("clarify", grounded=evidence["grounded"], blocked=evidence["blocked"])
            return "clarify"
        if state["urgent"]:
            route("urgent_referral")
            return "urgent_referral"
        return after_urgency(state)

    def after_urgency(state):
        if online or require_external:
            if fetch_is_relevant(state["facts"]["evidence"]):
                route("fetch_reference")
                return "fetch_reference"
            route("skip_reference", reason="reference_not_relevant")
            return "skip_reference"
        route("write_draft")
        return "write_draft"

    async def clarify(state):
        store.log("clarification_requested", "orchestrator", {"grounded": False})
        return {"result": {"state": "needs_information",
                           "message": state["facts"]["evidence"]["clarification"]}}

    async def urgent_referral(state):
        # Urgent cases are still drafted (the officer needs the evidence), but the
        # draft opens with a referral and the audit shows the escalation.
        store.log("urgent_case_escalated", "orchestrator",
                  {"source_ids": [s["id"] for s in state["facts"]["evidence"]["sources"]]})
        return {}

    async def skip_reference(state):
        # The fixed FAO page is about fall armyworm; attaching it to, say, a cattle
        # question would mislead the reviewer.
        store.log("third_party_skipped", "orchestrator", {"reason": "reference_not_relevant"})
        if require_external:
            raise ValueError("The third-party reference only covers fall armyworm; "
                             "--require-external cannot be met for this question")
        return {"external_status": "not_relevant_to_question"}

    async def fetch_reference(state):
        try:
            external = await fetch_external()
        except Exception as exc:
            # Do not silently fabricate a successful third-party call.
            store.log("third_party_unavailable", "orchestrator", {"error_type": type(exc).__name__})
            if require_external:
                raise ValueError("Required third-party Fetch MCP unavailable; no draft staged") from exc
            return {"external_status": "unavailable_using_local_evidence"}
        store.log("third_party_reference_fetched", "orchestrator",
                  {"url": external["url"], "content_hash": digest(external["text"])})
        return {"external_status": "fetched_reference_only", "external_text": external["text"]}

    async def write_draft(state):
        text, generation = await writer.run(state["query"], state["facts"])
        if state.get("urgent"):
            text = (URGENT_BANNER + text)[:6000]
        return {"text": text, "generation": generation}

    async def stage_for_review(state):
        result = await call(client, "stage_extension_advisory",
                            {"query": state["query"], "text": state["text"],
                             "region": state.get("region", ""),
                             "source_ids": [s["id"] for s in state["facts"]["evidence"]["sources"]],
                             "generation": state["generation"],
                             "external_text": state.get("external_text", "")})
        return {"result": result}

    graph = StateGraph(AgentState)
    for name, node in [("gather_evidence", gather_evidence), ("clarify", clarify),
                       ("urgent_referral", urgent_referral), ("skip_reference", skip_reference),
                       ("fetch_reference", fetch_reference), ("write_draft", write_draft),
                       ("stage_for_review", stage_for_review)]:
        graph.add_node(name, node)
    graph.add_edge(START, "gather_evidence")
    graph.add_conditional_edges("gather_evidence", after_evidence,
                                ["clarify", "urgent_referral", "fetch_reference",
                                 "skip_reference", "write_draft"])
    graph.add_conditional_edges("urgent_referral", after_urgency,
                                ["fetch_reference", "skip_reference", "write_draft"])
    graph.add_edge("fetch_reference", "write_draft")
    graph.add_edge("skip_reference", "write_draft")
    graph.add_edge("write_draft", "stage_for_review")
    graph.add_edge("stage_for_review", END)
    graph.add_edge("clarify", END)
    return graph.compile()


async def draft(query, db_path, region="", model_url=None, online=False, require_external=False):
    query = validate_query(query)
    region = validate_region(region) if region else ""
    writer = AdvisoryAgent(model_url)
    store = Store(db_path)
    store.log("run_started", "orchestrator", {"query_hash": digest(query), "online": online,
                                              "generation": "local_llm" if model_url else "grounded_template"})
    if needs_region(query) and not region:
        store.log("clarification_requested", "orchestrator", {"field": "natural_region"})
        return {"state": "needs_information", "message": "Which Natural Region (I–V) is your farm in?"}
    # Child has only the custom server and local database; approval is not in its tool set.
    env = dict(os.environ, MURIMI_AGENT_DB=str(Path(db_path).resolve()))
    parameters = StdioServerParameters(command=sys.executable, args=["-m", "challenge_agent.server"],
                                       cwd=str(ROOT), env=env)
    try:
        async with session(parameters) as client:
            graph = build_graph(client, store, writer, online, require_external)
            state = await graph.ainvoke({"query": query, "region": region})
            result = state["result"]
            if result.get("state") == "needs_information":
                return result
            store.log("run_completed", "orchestrator",
                      {"id": result["id"], "external_status": state["external_status"]})
            return {**result, "external_status": state["external_status"], "urgent": state["urgent"],
                    "message": "Draft stored for human review; no farmer delivery has occurred."}
    except Exception as exc:
        store.log("run_failed", "orchestrator", {"error_type": type(exc).__name__})
        raise
