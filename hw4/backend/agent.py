"""Campus Customs shop agent (PydanticAI entry / wiring).

- System prompt: prompts/prompt.md (read once at startup)
- Model: CHAT_MODEL from .env (default gpt-6-luna), called through Portkey
- Tools: tools.TOOLS (search_products, get_product_details, get_price, get_stock, list_categories,
  get_viewed_product, get_my_account, recall_past_conversations)
- Deps: tools.AgentDeps (logged-in customer profile, page context + the product on screen, numbers seen)
- Output: models.ChatAgentOutput (reply text + product_ids to show as cards),
  checked by an output validator: product_ids must exist, and every $ price or
  stock count in the reply must match a number a tool returned this turn.

main.py calls `run_chat()` for every chat message.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections.abc import Awaitable, Callable
from datetime import date, datetime, timezone
from pathlib import Path

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic import BaseModel
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.usage import UsageLimits

from models import (
    AuditIteration,
    AuditToolCall,
    AuditUsage,
    ChatAgentOutput,
    ChatMessageOut,
    CustomerProfile,
    PageContext,
    ProductCard,
    UserOut,
)
from tools import CHAT_MODEL, TOOLS, AgentDeps, cards_for, normalize_size, portkey_model, product_by_id, resolve_product

ProgressCallback = Callable[[str], Awaitable[None]]

HERE = Path(__file__).resolve().parent
SYSTEM_PROMPT_PATH = HERE / "prompts" / "prompt.md"
SYSTEM_PROMPT_SHA256 = hashlib.sha256(SYSTEM_PROMPT_PATH.read_bytes()).hexdigest()
HISTORY_TURNS = 10  # most recent messages replayed to the model as context
USAGE_LIMITS = UsageLimits(request_limit=10, tool_calls_limit=14)  # hard cap per chat turn

# "this" / "it" style references that mean the product on screen (see check_page_reference).
DEICTIC_RE = re.compile(r"\b(this|it|this one|that one|these|this item|this hoodie|this shirt|this crewneck)\b", re.IGNORECASE)

# Numbers in a reply that must be backed by a tool result (see check_grounding).
PRICE_RE = re.compile(r"\$\s?(\d{1,4}(?:,\d{3})*(?:\.\d{1,2})?)")
QUANTITY_RE = re.compile(
    r"\b(?:only\s+)?(\d{1,4})\s+(?:units?\s+|pieces?\s+|of them\s+|in stock\s+)?(?:left|in stock|available|remaining|on hand|on the shelf)\b",
    re.IGNORECASE,
)


def amounts_in(text: str) -> set[float]:
    """Dollar amounts and plain numbers a shopper typed ("under $70", "budget 60")."""
    return {round(float(n.replace(",", "")), 2) for n in re.findall(r"\$?\s?(\d{1,4}(?:\.\d{1,2})?)", text)}


def check_grounding(reply: str, deps: AgentDeps) -> str | None:
    """Return a problem description if the reply quotes a price or quantity no tool returned, else None."""
    prices_ok = deps.prices_seen | deps.known_prices | deps.shopper_amounts
    # allow simple arithmetic on real prices: differences ("$8 over budget") and small multiples ("two for $136.00")
    derived = {round(abs(a - b), 2) for a in prices_ok for b in prices_ok} | {round(k * a, 2) for a in deps.prices_seen | deps.known_prices for k in range(2, 6)}
    bad_prices = sorted({float(m.replace(",", "")) for m in PRICE_RE.findall(reply)} - prices_ok - derived)
    bad_qty = sorted({int(m) for m in QUANTITY_RE.findall(reply)} - deps.quantities_seen)
    problems = []
    if bad_prices:
        problems.append(f"prices {', '.join(f'${p:.2f}' for p in bad_prices)}")
    if bad_qty:
        problems.append(f"stock counts {', '.join(map(str, bad_qty))}")
    if not problems:
        return None
    return (
        f"Your reply mentions {' and '.join(problems)}, but no tool returned those numbers this turn. "
        "Call get_price / get_stock (or search_products) and use only the exact numbers they return."
    )


def customer_block(deps: AgentDeps) -> str:
    c = deps.customer
    if c is None:
        return (
            "## Who you're talking to\n"
            "A guest (not logged in). You don't know their name or email; don't ask for them. "
            "Their chat isn't saved after they leave. If they want you to remember them, suggest logging in or creating an account."
        )
    returning = (
        f"Returning customer: {c.saved_messages} earlier chat messages are saved; their last chat was {c.last_chat_at} UTC. "
        "The most recent turns are in the conversation above; use recall_past_conversations for older ones."
        if c.last_chat_at
        else "This is their first chat with us."
    )
    return (
        "## Who you're talking to\n"
        f"Logged-in customer: {c.first_name} {c.last_name}, email {c.email}, customer since {c.member_since}. {returning}\n"
        "Greet them by first name. You may tell THEM their own name or email if they ask (get_my_account), "
        "but never reveal it in any other way, and never discuss other customers."
    )


def page_block(deps: AgentDeps) -> str:
    page, p = deps.page, deps.page_product
    if p is not None:
        return (
            "## What page they're on\n"
            f"The shopper is viewing the product page for **{p['name']}** (product_id `{p['product_id']}`, category {p['category']}).\n"
            f"When they say \"this\", \"it\", \"this one\", or ask about a size or color without naming an item, they mean {p['name']}. "
            f"Look it up with get_viewed_product, or get_stock / get_price with product_id `{p['product_id']}`, and include that id in product_ids. "
            "If they clearly name a different item, follow what they say."
        )
    if page is None:
        return "## What page they're on\nUnknown."
    where = "the home page" if page.path in ("", "/") else "the About Us page" if page.path.startswith("/about") else (
        "the Products page" + (f", filtered to {page.category}" if page.category else "") + (f", searching for \"{page.search}\"" if page.search else "")
        if page.path.startswith("/products") else f"the page {page.path}"
    )
    return (
        "## What page they're on\n"
        f"The shopper is on {where}. They're not on a single product page, so if they say \"this\" or \"it\" without context, ask which item they mean."
    )


def size_block(deps: AgentDeps) -> str:
    if not deps.preferred_size:
        return "## Their size\nThe shopper hasn't picked a size in the site's size picker. Ask if a size matters for the answer."
    s = deps.preferred_size
    return (
        f"## Their size\nThe shopper's size is **{s}** (from the size picker on the site). "
        f"When they ask about availability without naming a size, check {s}. When recommending items, prefer ones in stock in {s}. "
        f"If an item is sold out in {s} (or has only a few left), say so and call find_alternatives to suggest similar items in stock in {s}. "
        "If they name a different size, use that instead."
    )


def build_agent() -> Agent[AgentDeps, ChatAgentOutput]:
    agent = Agent(
        portkey_model(CHAT_MODEL),
        deps_type=AgentDeps,
        output_type=ChatAgentOutput,
        instructions=SYSTEM_PROMPT_PATH.read_text(encoding="utf-8"),
        tools=TOOLS,
        name="campus_customs_shop_agent",
        retries=3,  # covers tool errors and output-validator rejections (unknown ids, unverified numbers)
    )

    @agent.instructions
    def shopper_context(ctx: RunContext[AgentDeps]) -> str:
        """Per-message context, rebuilt every turn: today's date, who is talking, and what page they're on."""
        return "\n\n".join([
            f"Today is {date.today().strftime('%A, %B %-d, %Y')}.", customer_block(ctx.deps), page_block(ctx.deps), size_block(ctx.deps),
        ])

    @agent.output_validator
    def check_products(ctx: RunContext[AgentDeps], output: ChatAgentOutput) -> ChatAgentOutput:
        unknown = [pid for pid in output.product_ids if product_by_id(pid) is None]
        if unknown:
            raise ModelRetry(f"These product_ids don't exist: {unknown}. Use ids exactly as returned by search_products.")
        if not output.reply.strip():
            raise ModelRetry("The reply text is empty.")
        p = ctx.deps.page_product
        if p and ctx.deps.refers_to_page and output.product_ids and p["product_id"] not in output.product_ids:
            raise ModelRetry(
                f"The shopper said 'this'/'it' while viewing {p['name']} (product_id {p['product_id']}), "
                "so the question is about THAT product, not one from earlier in the chat. Look it up and answer about it, "
                "and put its product_id first in product_ids."
            )
        problem = check_grounding(f"{output.reply}\n{output.results_heading or ''}", ctx.deps)
        if problem:
            ctx.deps.grounding_retries += 1
            raise ModelRetry(problem)
        return output

    return agent


_agent: Agent[AgentDeps, ChatAgentOutput] | None = None


def get_agent() -> Agent[AgentDeps, ChatAgentOutput]:
    """Built on first use, so the API can start (and serve products) even without an API key."""
    global _agent
    if _agent is None:
        _agent = build_agent()
    return _agent


def to_model_history(history: list[ChatMessageOut]) -> list[ModelMessage]:
    """Earlier turns as plain text messages. Product cards are noted by id so follow-ups like 'the second one' work."""
    messages: list[ModelMessage] = []
    for m in history[-HISTORY_TURNS:]:
        if m.role == "user":
            text = m.content
            viewed = product_by_id(m.page_product_id) if m.page_product_id else None
            if viewed:  # so an old "do you have this in L?" still makes sense
                text = f"[sent from the product page for {viewed['name']} ({viewed['product_id']})] {text}"
            messages.append(ModelRequest(parts=[UserPromptPart(content=text)]))
        else:
            text = m.content
            if m.products:
                text += "\n[Product cards shown: " + ", ".join(f"{p.name} ({p.product_id})" for p in m.products) + "]"
            messages.append(ModelResponse(parts=[TextPart(content=text)]))
    return messages


# ---------- Loop tracing for the audit trail ----------


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def short(value: object, limit: int = 300) -> str:
    """Compact text version of a tool argument or result."""
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    elif isinstance(value, list):
        value = [v.model_dump(mode="json") if isinstance(v, BaseModel) else v for v in value]
    text = value if isinstance(value, str) else json.dumps(value, default=str, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + "…"


def short_args(args: dict, limit: int = 120) -> dict:
    return {k: (v if len(json.dumps(v, default=str)) <= limit else short(v, limit)) for k, v in args.items()}


class LoopTrace:
    """Builds AuditIteration records while agent.iter() runs, so even an aborted run leaves a trace."""

    def __init__(self) -> None:
        self.iterations: list[AuditIteration] = []
        self.request_started = time.time()
        self.request_started_iso = now_iso()
        self.tools_started: float | None = None
        self.usage = AuditUsage()
        self.final_tool: str | None = None
        self.finish_reason: str | None = None

    def model_request(self, request: ModelRequest) -> None:
        """A new model call is starting; its parts carry the results of the previous step's tools."""
        now = time.time()
        if self.iterations:
            last = self.iterations[-1]
            if self.tools_started is not None:
                last.tool_seconds = round(now - self.tools_started, 2)
            by_id = {c.tool_call_id: c for c in last.tool_calls}
            for part in request.parts:
                call = by_id.get(getattr(part, "tool_call_id", None) or "")
                if call is None:
                    continue
                if isinstance(part, ToolReturnPart):
                    call.status, call.result_summary = "ok", short(part.content)
                elif isinstance(part, RetryPromptPart):
                    call.status, call.result_summary = "retry", short(part.content)
        self.request_started, self.request_started_iso, self.tools_started = now, now_iso(), None

    def model_response(self, response: ModelResponse) -> None:
        now = time.time()
        thoughts = [p.content.strip() for p in response.parts if isinstance(p, (TextPart, ThinkingPart)) and p.content.strip()]
        calls = [
            AuditToolCall(tool_name=p.tool_name, tool_call_id=p.tool_call_id or "", args=short_args(p.args_as_dict()))
            for p in response.parts
            if isinstance(p, ToolCallPart)
        ]
        self.finish_reason = response.finish_reason
        self.iterations.append(AuditIteration(
            step=len(self.iterations) + 1, started_at=self.request_started_iso,
            model_seconds=round(now - self.request_started, 2), finish_reason=response.finish_reason,
            thought=short(" ".join(thoughts), 400) if thoughts else "", tool_calls=calls,
        ))
        self.tools_started = now

    def finished(self, run_usage: object | None) -> None:
        """The run ended with an accepted answer: mark the final_result call."""
        if self.iterations:
            last = self.iterations[-1]
            if self.tools_started is not None:
                last.tool_seconds = round(time.time() - self.tools_started, 2)
            for c in last.tool_calls:
                if c.tool_name.startswith("final_result"):
                    c.status, c.result_summary, self.final_tool = "final answer accepted", "passed output validation", c.tool_name
        self.record_usage(run_usage)

    def record_usage(self, run_usage: object | None) -> None:
        if run_usage is None:
            return
        self.usage = AuditUsage(
            model_requests=getattr(run_usage, "requests", 0) or 0,
            tool_calls=getattr(run_usage, "tool_calls", 0) or 0,
            input_tokens=getattr(run_usage, "input_tokens", 0) or 0,
            output_tokens=getattr(run_usage, "output_tokens", 0) or 0,
        )


def _usage(run: object) -> object:
    u = getattr(run, "usage", None)
    return u() if callable(u) else u


def _name(ref: object) -> str:
    p = resolve_product(str(ref)) if ref else None
    return p["name"] if p else "that item"


def describe_step(part: ToolCallPart, deps: AgentDeps) -> str:
    """A short, shopper-friendly line for the live progress list, e.g. 'Checking stock: Basic Hoodie Big Yale in L'."""
    a = part.args_as_dict()
    name = part.tool_name
    if name == "search_products":
        bits = [a.get("query") or "", (a.get("color") or ""), (a.get("category") or "").lower()]
        what = " ".join(b for b in bits if b).strip() or "the catalogue"
        extra = (f" under ${a['max_price']:.0f}" if a.get("max_price") else "") + (f", size {normalize_size(a['size']) or a['size']}" if a.get("size") else "")
        return f"Searching the catalogue: {what}{extra}"
    if name == "get_stock":
        size = normalize_size(a["size"]) if a.get("size") else None
        return f"Checking stock: {_name(a.get('product'))}" + (f" in {size or a['size']}" if a.get("size") else " (all sizes)")
    if name == "get_price":
        items = a.get("products") or []
        return "Looking up the price" + (f" of {_name(items[0])}" if len(items) == 1 else f"s of {len(items)} items")
    if name == "get_product_details":
        return f"Reading the details for {_name(a.get('product'))}"
    if name == "find_alternatives":
        size = normalize_size(a["size"]) if a.get("size") else deps.preferred_size
        return f"Finding similar items in stock{' in ' + size if size else ''}"
    if name == "get_viewed_product":
        return f"Looking at the item on your screen: {deps.page_product['name'] if deps.page_product else 'this page'}"
    if name == "get_my_account":
        return "Checking your account"
    if name == "recall_past_conversations":
        return "Looking back through your past chats"
    if name == "list_categories":
        return "Looking over our categories"
    if name.startswith("final_result"):
        return "Writing your answer"
    return "Working on it"


async def run_chat(
    message: str,
    history: list[ChatMessageOut],
    user: UserOut | None,
    customer: CustomerProfile | None = None,
    page: PageContext | None = None,
    preferred_size: str | None = None,
    on_progress: ProgressCallback | None = None,
    holder: dict | None = None,
) -> tuple[ChatAgentOutput, list[ProductCard], AgentDeps]:
    """One chat turn. Returns (the agent's structured output, product cards built from the database, the turn's deps).

    on_progress (optional) is awaited with a short status line each time the agent starts a step
    (each tool call, then "Putting your answer together"), so the website can show live progress.
    holder (optional) receives the deps right away; deps.trace holds the loop trace for the audit trail.
    """
    deps = AgentDeps(user=user, customer=customer, page=page, preferred_size=preferred_size)
    if holder is not None:
        holder["deps"] = deps  # lets the caller audit a partial run if it times out or fails
    if page and page.product_id:
        deps.page_product = product_by_id(page.product_id)  # trust the id only if it's a real product
    # Prices on cards already shown in this conversation came from the database, so repeating them is fine.
    recent = history[-HISTORY_TURNS:]
    deps.known_prices = {round(c.price, 2) for m in recent for c in m.products}
    deps.shopper_amounts = amounts_in(" ".join([message, *(m.content for m in recent if m.role == "user")]))
    model_message = message
    if deps.page_product:
        # Same tag the replayed history uses, so the model sees which page THIS message came from.
        deps.refers_to_page = bool(DEICTIC_RE.search(message))
        model_message = f"[sent from the product page for {deps.page_product['name']} ({deps.page_product['product_id']})] {message}"

    async def emit(text: str) -> None:
        if on_progress:
            await on_progress(text)

    await emit("Reading your question")
    trace = deps.trace = LoopTrace()
    async with get_agent().iter(
        model_message, deps=deps, message_history=to_model_history(history), usage_limits=USAGE_LIMITS
    ) as run:
        looked_up = False
        try:
            async for node in run:
                # A CallToolsNode holds the tool calls the model just asked for; announce each before it runs.
                if Agent.is_call_tools_node(node):
                    trace.model_response(node.model_response)
                    for part in node.model_response.parts:
                        if isinstance(part, ToolCallPart) and not part.tool_name.startswith("final_result"):
                            await emit(describe_step(part, deps))
                            looked_up = True
                # A model request = a new loop iteration (it carries the previous tools' results).
                elif Agent.is_model_request_node(node):
                    trace.model_request(node.request)
                    if looked_up:  # the model is now composing the reply
                        await emit("Putting your answer together")
                        looked_up = False
        except BaseException:
            trace.record_usage(_usage(run))  # keep usage for the audit even if the run is cut short
            raise
    trace.finished(_usage(run))
    output = run.result.output
    return output, cards_for(output.product_ids), deps
