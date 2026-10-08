"""Data access + the tools the shop agent can call.

Everything the agent says about price, stock, sizes, and colors comes from these
functions, which read the local SQLite database (data/campus_customs.db).
The API in main.py uses the same helpers, so the website and the chatbot can
never disagree about a product.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai import RunContext
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider

from models import (
    AlternativeMatch,
    AlternativesResult,
    CustomerProfile,
    PageContext,
    PastConversationSearch,
    PastMessage,
    PriceLookup,
    PriceQuote,
    ProductCard,
    ProductInfo,
    ProductMatch,
    SearchResult,
    SizeAvailability,
    StockReport,
    UserOut,
    stock_status,
)

# ---------- Config ----------

HW4_DIR = Path(__file__).resolve().parent.parent
# hw4/.env first (what graders use), then any .env in parent folders for local development.
load_dotenv(HW4_DIR / ".env")
for parent in HW4_DIR.parents:
    if (parent / ".env").exists():
        load_dotenv(parent / ".env")  # never overrides values already set
        break

CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-6-luna")
CHAT_REASONING_EFFORT = os.getenv("CHAT_REASONING_EFFORT", "low")
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1")


class AssistantNotConfigured(RuntimeError):
    pass


def portkey_model(model_name: str = CHAT_MODEL) -> OpenAIResponsesModel:
    """An OpenAI model routed through Portkey, using PORTKEY_API_KEY from .env.

    Uses the Responses API: gpt-6 models only allow tool calls together with
    reasoning there (Chat Completions rejects tools + reasoning_effort).
    """
    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        raise AssistantNotConfigured("PORTKEY_API_KEY is missing. Copy .env.example to .env and add your key.")
    client = AsyncOpenAI(
        base_url=PORTKEY_BASE_URL,
        api_key=api_key,
        default_headers={"x-portkey-api-key": api_key, "x-portkey-provider": "openai"},
        timeout=45,  # per model call
        max_retries=1,  # the SDK default (2) let one slow message take minutes in testing
    )
    return OpenAIResponsesModel(
        model_name,
        provider=OpenAIProvider(openai_client=client),
        settings=OpenAIResponsesModelSettings(openai_reasoning_effort=CHAT_REASONING_EFFORT),
    )


def find_data_dir() -> Path:
    """DATA_DIR env var wins; otherwise look for data/ inside hw4/ or next to it."""
    if os.getenv("DATA_DIR"):
        return Path(os.environ["DATA_DIR"]).expanduser().resolve()
    for candidate in (HW4_DIR / "data", HW4_DIR.parent / "data"):
        if (candidate / "campus_customs.db").exists():
            return candidate
    return HW4_DIR / "data"


DATA_DIR = find_data_dir()
DB_PATH = DATA_DIR / "campus_customs.db"
SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]


class DatabaseMissing(RuntimeError):
    pass


def connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise DatabaseMissing(f"Database not found at {DB_PATH}. See README for setup.")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---------- Catalogue helpers ----------

# garment_type in the database has ~22 spellings; group them into shop categories.
CATEGORY_RULES = [
    ("Quarter-Zips", ("quarter-zip", "1/4 zip")),
    ("Jackets & Fleece", ("jacket", "fleece", "full-zip")),
    ("Hoodies", ("hoodie", "hooded")),
    ("Crewnecks", ("crewneck", "mockneck")),
    ("Long Sleeves", ("long-sleeve",)),
    ("T-Shirts", ("t-shirt",)),
]
CATEGORIES = [c for c, _ in CATEGORY_RULES]


def category_for(garment_type: str) -> str:
    g = garment_type.lower()
    for category, keys in CATEGORY_RULES:
        if any(k in g for k in keys):
            return category
    return "Other"


def load_inventory(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    stock: dict[str, list[dict]] = {}
    for row in conn.execute("SELECT product_id, size, quantity FROM inventory"):
        stock.setdefault(row["product_id"], []).append({"size": row["size"], "quantity": row["quantity"]})
    for sizes in stock.values():
        sizes.sort(key=lambda s: SIZE_ORDER.index(s["size"]) if s["size"] in SIZE_ORDER else 99)
    return stock


def is_placeholder(description: str) -> bool:
    """3 catalogue rows hold a leftover stub ('... Vision blocked; filename-based stub.')."""
    return "filename-based stub" in description or description.startswith("Campus Customs product photo")


def to_product(row: sqlite3.Row, inventory: list[dict]) -> dict:
    placeholder = is_placeholder(row["description"])
    return {
        "product_id": row["product_id"],
        "name": row["name"],
        "garment_type": row["garment_type"],
        "category": category_for(row["garment_type"]),
        # Don't show stub text to shoppers; say only what we actually know.
        "description": f"{row['name']}, officially licensed Yale apparel from Campus Customs." if placeholder else row["description"],
        "description_is_placeholder": placeholder,
        "colors": json.loads(row["colors"]),
        "search_tags": json.loads(row["search_tags"]),
        "image_file_path": row["image_file_path"],
        "image_url": f"/media/{row['image_file_path']}",
        "price": row["price"],
        "inventory": inventory,
        "total_stock": sum(s["quantity"] for s in inventory),
    }


def all_products() -> list[dict]:
    with connect() as conn:
        stock = load_inventory(conn)
        rows = conn.execute("SELECT * FROM catalogue ORDER BY name").fetchall()
    return [to_product(r, stock.get(r["product_id"], [])) for r in rows]


def product_by_id(product_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM catalogue WHERE product_id = ?", (product_id,)).fetchone()
        if row is None:
            return None
        sizes = [
            {"size": r["size"], "quantity": r["quantity"]}
            for r in conn.execute("SELECT size, quantity FROM inventory WHERE product_id = ?", (product_id,))
        ]
    sizes.sort(key=lambda s: SIZE_ORDER.index(s["size"]) if s["size"] in SIZE_ORDER else 99)
    return to_product(row, sizes)


def in_stock_sizes(p: dict) -> list[str]:
    return [s["size"] for s in p["inventory"] if s["quantity"] > 0]


def sold_out_sizes(p: dict) -> list[str]:
    return [s["size"] for s in p["inventory"] if s["quantity"] <= 0]


def product_card(p: dict) -> ProductCard:
    desc = p["description"]
    return ProductCard(
        product_id=p["product_id"],
        name=p["name"],
        category=p["category"],
        price=p["price"],
        image_url=p["image_url"],
        short_description=desc if len(desc) <= 110 else desc[:107].rsplit(" ", 1)[0] + "…",
        colors=p["colors"],
        sizes_in_stock=in_stock_sizes(p),
        total_stock=p["total_stock"],
    )


def cards_for(product_ids: list[str]) -> list[ProductCard]:
    """Product cards for these ids, in order, skipping unknown ids and duplicates."""
    cards, seen = [], set()
    for pid in product_ids:
        if pid in seen:
            continue
        seen.add(pid)
        p = product_by_id(pid)
        if p:
            cards.append(product_card(p))
    return cards


def size_rows(p: dict) -> list[SizeAvailability]:
    return [SizeAvailability(size=x["size"], quantity=x["quantity"], status=stock_status(x["quantity"])) for x in p["inventory"]]


def product_info(p: dict) -> ProductInfo:
    return ProductInfo(
        product_id=p["product_id"],
        name=p["name"],
        category=p["category"],
        garment_type=p["garment_type"],
        price=p["price"],
        description=p["description"],
        description_is_placeholder=p["description_is_placeholder"],
        colors=p["colors"],
        tags=p["search_tags"],
        sizes=size_rows(p),
        sizes_in_stock=in_stock_sizes(p),
        sold_out_sizes=sold_out_sizes(p),
        total_in_stock=p["total_stock"],
    )


SIZE_WORDS = {
    "xs": "XS", "x-small": "XS", "xsmall": "XS", "extra small": "XS", "extra-small": "XS",
    "s": "S", "sm": "S", "small": "S",
    "m": "M", "med": "M", "medium": "M",
    "l": "L", "lg": "L", "large": "L",
    "xl": "XL", "x-large": "XL", "xlarge": "XL", "extra large": "XL", "extra-large": "XL",
    "xxl": "XXL", "2xl": "XXL", "xx-large": "XXL", "xxlarge": "XXL", "2x": "XXL", "double xl": "XXL",
}


def normalize_size(size: str) -> str | None:
    """'medium' -> 'M', '2XL' -> 'XXL'; None if it isn't one of our sizes."""
    return SIZE_WORDS.get(" ".join(size.strip().lower().replace("size", "").split()))


def resolve_product(ref: str) -> dict | None:
    """Find a product by product_id, or by its exact or unique partial name (case-insensitive)."""
    ref = ref.strip()
    p = product_by_id(ref) or product_by_id(ref.lower().replace(" ", "-"))
    if p:
        return p
    name = " ".join(ref.lower().split())
    products = all_products()
    exact = [x for x in products if x["name"].lower() == name]
    if exact:
        return exact[0]
    partial = [x for x in products if name in x["name"].lower()]
    return partial[0] if len(partial) == 1 else None


# ---------- Search ----------

# Shopper words -> words used in the catalogue.
SYNONYMS = {
    "tee": ["t-shirt"], "tees": ["t-shirt"], "tshirt": ["t-shirt"], "shirt": ["t-shirt", "shirt"],
    "hoody": ["hoodie"], "hooded": ["hoodie", "hooded"], "sweatshirt": ["sweatshirt", "crewneck", "hoodie"],
    "sweater": ["sweater", "crewneck"], "crew": ["crew", "crewneck"], "quarter": ["quarter-zip"],
    "1/4": ["quarter-zip"], "zip": ["zip"], "zipup": ["full-zip"], "grey": ["gray"],
    "dog": ["bulldog"], "football": ["football", "the game"], "harvard": ["harvard", "the game"],
    "mom": ["mom"], "dad": ["dad"], "grandma": ["grandma"], "grandpa": ["grandpa"],
}
# A requested color also matches these close shades (the reply must still name the real color).
COLOR_FAMILIES = {
    "pink": ["pink", "coral", "rose", "magenta"],
    "purple": ["purple", "violet", "lavender"],
    "grey": ["gray"],
    "gray": ["gray"],
}
STOPWORDS = {
    "a", "an", "the", "and", "or", "for", "with", "in", "of", "to", "do", "you", "have", "any", "some", "me",
    "show", "i", "want", "looking", "my", "is", "are", "that", "this", "what", "under", "over", "something",
    "merch", "apparel", "clothing", "item", "items", "please", "got", "need", "like", "yale",
}


def terms_for(query: str) -> list[list[str]]:
    """Each query word becomes a group of alternatives; a product must match every group."""
    groups = []
    for word in re.findall(r"[a-z0-9/'-]+", query.lower()):
        if word in STOPWORDS or len(word) < 2:
            continue
        alts = {word, *SYNONYMS.get(word, [])}
        if len(word) > 3 and word.endswith("s"):
            alts.add(word[:-1])
        groups.append(sorted(alts))
    return groups


def score(p: dict, groups: list[list[str]]) -> int:
    name = p["name"].lower()
    tags = " ".join(p["search_tags"]).lower()
    rest = " ".join([p["garment_type"], p["category"], p["description"], *p["colors"]]).lower()
    total = 0
    for alts in groups:
        best = max((3 if a in name else 2 if a in tags else 1 if a in rest else 0) for a in alts)
        if best == 0:
            return 0
        total += best
    return total


def search_catalogue(
    query: str = "",
    category: str | None = None,
    color: str | None = None,
    max_price: float | None = None,
    min_price: float | None = None,
    size: str | None = None,
    limit: int = 8,
) -> SearchResult:
    products = all_products()
    notes = []
    if category:
        wanted = next((c for c in CATEGORIES if c.lower() == category.strip().lower()), None)
        if wanted:
            products = [p for p in products if p["category"] == wanted]
        else:
            notes.append(f"Unknown category '{category}', ignored. Categories: {', '.join(CATEGORIES)}.")
    if color:
        # Match the garment's main color: the first listed color, or the color the description opens with
        # ("Navy pullover hoodie..."). Accent colors (e.g. navy lettering on a gray crewneck) don't count.
        family = COLOR_FAMILIES.get(color.strip().lower(), [color.strip().lower().replace("grey", "gray")])
        products = [
            p for p in products
            if any((p["colors"] and c in p["colors"][0].lower()) or c in p["description"][:30].lower() for c in family)
        ]
    if max_price is not None:
        products = [p for p in products if p["price"] <= max_price]
    if min_price is not None:
        products = [p for p in products if p["price"] >= min_price]
    if size:
        s = size.strip().upper()
        products = [p for p in products if any(x["size"] == s and x["quantity"] > 0 for x in p["inventory"])]
    groups = terms_for(query)
    if groups:
        scored = [(score(p, groups), p) for p in products]
        products = [p for sc, p in sorted(scored, key=lambda t: -t[0]) if sc > 0]
    limit = max(1, min(limit, 12))
    shown = products[:limit]
    return SearchResult(
        total_matches=len(products),
        showing=len(shown),
        matches=[
            ProductMatch(
                product_id=p["product_id"], name=p["name"], category=p["category"], price=p["price"],
                colors=p["colors"], description=p["description"],
                sizes_in_stock=in_stock_sizes(p),
                low_stock_sizes=[x["size"] for x in p["inventory"] if stock_status(x["quantity"]) == "low_stock"],
                sold_out_sizes=sold_out_sizes(p),
            )
            for p in shown
        ],
        note=" ".join(notes),
    )


# ---------- Agent tools ----------
# Each tool records the prices and quantities it returned in ctx.deps, so the
# agent's output validator (agent.py) can reject any reply that quotes a price
# or stock count the database didn't return this turn.


@dataclass
class AgentDeps:
    """Everything one chat turn knows besides the messages: who is talking, where they are, what the tools found."""

    user: UserOut | None = None  # the logged-in account (None = guest)
    customer: CustomerProfile | None = None  # what the agent may know about that shopper (see get_my_account)
    page: PageContext | None = None  # the page the shopper is on, as sent by the browser
    page_product: dict | None = None  # the product on that page, re-read from the database (None if not a valid product page)
    preferred_size: str | None = None  # the shopper's size from the size picker / their account ("My size")
    refers_to_page: bool = False  # message says "this"/"it" while on a product page
    trace: Any = None  # agent.LoopTrace for the audit trail (set by run_chat)
    tool_calls: list[str] = field(default_factory=list)  # tools used this turn (for logging)
    prices_seen: set[float] = field(default_factory=set)  # every price a tool returned this turn
    quantities_seen: set[int] = field(default_factory=set)  # every stock count a tool returned this turn
    known_prices: set[float] = field(default_factory=set)  # prices on cards already shown (from the DB) in history
    shopper_amounts: set[float] = field(default_factory=set)  # numbers the shopper typed (budgets like "under $70")
    grounding_retries: int = 0  # times the output validator sent a reply back for unverified numbers

    def saw_product(self, p: dict) -> None:
        self.prices_seen.add(round(p["price"], 2))
        self.quantities_seen.add(p["total_stock"])
        self.quantities_seen.update(x["quantity"] for x in p["inventory"])


def not_found(ref: str) -> str:
    """Helpful message when a product reference doesn't resolve (lists candidates if it was ambiguous)."""
    name = " ".join(ref.lower().split())
    candidates = [p for p in all_products() if name and name in p["name"].lower()][:6]
    if len(candidates) > 1:
        return f"'{ref}' matches several products: " + "; ".join(f"{c['name']} (product_id {c['product_id']})" for c in candidates) + ". Ask which one, or use the exact product_id."
    return f"No product matches '{ref}'. Call search_products to find the right product_id."


def search_products(
    ctx: RunContext[AgentDeps],
    query: str = "",
    category: str | None = None,
    color: str | None = None,
    max_price: float | None = None,
    min_price: float | None = None,
    size: str | None = None,
    limit: int = 8,
) -> SearchResult:
    """Search the Campus Customs catalogue. Use this first to find products and their product_id.

    Args:
        query: Keywords, e.g. "hockey", "bulldog hoodie", "Davenport", "The Game". Leave empty to browse with filters only.
        category: One of Hoodies, Crewnecks, T-Shirts, Quarter-Zips, Jackets & Fleece, Long Sleeves.
        color: The garment's main color, e.g. "navy", "gray", "white", "red" (accent colors don't count).
            "pink" also matches close shades like coral; always tell the shopper the item's real color.
        max_price: Highest price in USD.
        min_price: Lowest price in USD.
        size: Only return items with this size in stock (XS, S, M, L, XL, XXL, or words like "medium").
        limit: How many matches to return (1-12).
    """
    ctx.deps.tool_calls.append("search_products")
    norm = normalize_size(size) if size else None
    result = search_catalogue(query, category, color, max_price, min_price, norm or size, limit)
    for m in result.matches:
        ctx.deps.prices_seen.add(round(m.price, 2))
    return result


def get_product_details(ctx: RunContext[AgentDeps], product: str) -> ProductInfo | str:
    """Full facts for one product: description, price, colors, tags, and stock for every size.

    Use for "tell me about...", "what does it look like", "what colors", or before describing an item.

    Args:
        product: The product_id from a search result (preferred), or the product's exact name.
    """
    ctx.deps.tool_calls.append("get_product_details")
    p = resolve_product(product)
    if p is None:
        return not_found(product)
    ctx.deps.saw_product(p)
    return product_info(p)


def get_price(ctx: RunContext[AgentDeps], products: list[str]) -> PriceLookup:
    """Current price (USD) of one or more products. Use for every "how much is..." or price comparison.

    Args:
        products: product_ids (preferred) or exact product names, e.g. ["basic-hoodie-big-yale"].
    """
    ctx.deps.tool_calls.append("get_price")
    quotes, missing = [], []
    for ref in products[:12]:
        p = resolve_product(ref)
        if p is None:
            missing.append(ref)
            continue
        ctx.deps.prices_seen.add(round(p["price"], 2))
        quotes.append(PriceQuote(product_id=p["product_id"], name=p["name"], price=p["price"]))
    return PriceLookup(quotes=quotes, not_found=missing)


def get_stock(ctx: RunContext[AgentDeps], product: str, size: str | None = None) -> StockReport | str:
    """How many units of a product are in stock, for every size or one specific size.

    Use for every "is it in stock", "do you have it in M", or "how many are left" question.
    A quantity of 0 means that size is SOLD OUT.

    Args:
        product: The product_id from a search result (preferred), or the product's exact name.
        size: Optional size to check: XS, S, M, L, XL, XXL (words like "medium" or "2XL" are fine).
    """
    ctx.deps.tool_calls.append("get_stock")
    p = resolve_product(product)
    if p is None:
        return not_found(product)
    ctx.deps.saw_product(p)
    rows = size_rows(p)
    in_stock, sold_out = in_stock_sizes(p), sold_out_sizes(p)
    report = dict(
        product_id=p["product_id"], name=p["name"], price=p["price"], sizes=rows,
        sizes_in_stock=in_stock, sold_out_sizes=sold_out, total_in_stock=p["total_stock"],
    )
    if size is None:
        summary = (
            f"{p['name']}: sold out in every size." if not in_stock
            else f"{p['name']}: in stock in {', '.join(in_stock)}"
            + (f"; sold out in {', '.join(sold_out)}." if sold_out else " (every size available).")
        )
        return StockReport(**report, summary=summary)
    norm = normalize_size(size)
    row = next((r for r in rows if r.size == norm), None)
    if row is None:
        return StockReport(
            **report,
            requested_size=size,
            summary=f"{p['name']} doesn't come in size '{size}'. Sizes offered: {', '.join(r.size for r in rows)}.",
        )
    if row.status == "sold_out":
        summary = f"Size {row.size} of {p['name']} is SOLD OUT (0 left)." + (
            f" In stock in: {', '.join(in_stock)}." if in_stock else " Every size is sold out."
        )
    elif row.status == "low_stock":
        summary = f"Size {row.size} of {p['name']} is in stock, but only {row.quantity} left."
    else:
        summary = f"Size {row.size} of {p['name']} is in stock: {row.quantity} available."
    return StockReport(**report, requested_size=row.size, requested_quantity=row.quantity, requested_status=row.status, summary=summary)


def list_categories(ctx: RunContext[AgentDeps]) -> list[dict]:
    """The shop's product categories with item counts and price ranges (USD)."""
    ctx.deps.tool_calls.append("list_categories")
    summary: dict[str, dict] = {}
    for p in all_products():
        c = summary.setdefault(p["category"], {"category": p["category"], "items": 0, "min_price": p["price"], "max_price": p["price"]})
        c["items"] += 1
        c["min_price"] = min(c["min_price"], p["price"])
        c["max_price"] = max(c["max_price"], p["price"])
    for c in summary.values():
        ctx.deps.prices_seen.update({c["min_price"], c["max_price"]})
    return sorted(summary.values(), key=lambda c: c["category"])


# ---------- In-stock alternatives ----------

# Tags that almost every product has; they say nothing about similarity.
GENERIC_TAGS = {
    "yale", "campus customs", "college apparel", "yale merch", "college merch", "yale apparel", "apparel",
    "sweatshirt", "long sleeve", "pullover", "college sweatshirt", "college sports",
}


# Words about the garment itself (style features), as opposed to its theme (sport, school, graphic).
GARMENT_WORDS = {
    "hoodie", "hoodies", "hooded", "hood", "drawstring", "kangaroo", "pocket", "crewneck", "crew", "neck", "sweatshirt",
    "sweater", "pullover", "zip", "quarter", "full", "1/4", "t-shirt", "tee", "shirt", "sleeve", "long", "short",
    "left", "chest", "logo", "graphic", "lettering", "wordmark", "text", "navy", "blue", "gray", "grey", "heather",
    "white", "black", "charcoal", "dark", "light", "jacket", "fleece", "ribbed", "cuffs", "hem", "college", "apparel",
    "university", "yale", "campus", "customs", "merch", "sports", "tri", "blend", "district", "vit", "basic", "big",
}


def _tag_words(p: dict) -> set[str]:
    return {t.lower() for t in p["search_tags"] if t.lower() not in GENERIC_TAGS}


def _theme_words(p: dict) -> set[str]:
    """Distinctive words (sport, school, mascot, event) from the name and tags, e.g. {'hockey'} or {'davenport'}."""
    text = " ".join([p["name"], *p["search_tags"]]).lower()
    return {w for w in re.findall(r"[a-z]+", text) if len(w) > 2 and w not in GARMENT_WORDS}


def similar_products(base: dict, size: str | None = None, max_price: float | None = None, limit: int = 4) -> list[tuple[dict, int, str]]:
    """Products most like `base`, as (product, quantity_in_size_or_total, why_similar), best first.

    With a size, only items in stock in that size; without one, any item with stock.
    Shared by the agent's find_alternatives tool and the product page's "You might also like".
    """
    base_tags, base_color = _tag_words(base), (base["colors"][0].lower() if base["colors"] else "")
    base_theme = _theme_words(base)
    scored = []
    for p in all_products():
        if p["product_id"] == base["product_id"]:
            continue
        qty = next((x["quantity"] for x in p["inventory"] if x["size"] == size), 0) if size else p["total_stock"]
        if qty <= 0 or (max_price is not None and p["price"] > max_price):
            continue
        score, why = 0, []
        if p["category"] == base["category"]:
            score += 5
            why.append(f"also a {p['category'][:-1].lower() if p['category'].endswith('s') else p['category'].lower()}")
        if p["garment_type"].lower() == base["garment_type"].lower():
            score += 2
        main = p["colors"][0].lower() if p["colors"] else ""
        if base_color and main and (base_color in main or main in base_color or base_color.split()[-1] == main.split()[-1]):
            score += 2
            why.append(f"same main color ({p['colors'][0]})")
        theme = sorted(base_theme & _theme_words(p))[:3]
        if theme:  # same sport / school / mascot matters most to a shopper
            score += 4 * len(theme)
            why.append("same theme: " + ", ".join(theme))
        shared = sorted(base_tags & _tag_words(p))[:3]
        if shared:
            score += len(shared)
            if not theme:
                why.append("shares " + ", ".join(f'"{t}"' for t in shared))
        if abs(p["price"] - base["price"]) <= 10:
            score += 1
        if score >= 5:
            scored.append((score, qty, p, "; ".join(why) or "similar style"))
    scored.sort(key=lambda t: (-t[0], -t[1], t[2]["name"]))
    return [(p, qty, why) for _, qty, p, why in scored[: max(1, min(limit, 12))]]


def find_alternatives(
    ctx: RunContext[AgentDeps], product: str, size: str | None = None, max_price: float | None = None, limit: int = 4
) -> AlternativesResult | str:
    """Similar products that ARE in stock in a size: use when an item is sold out (or low) in the shopper's size.

    Ranks the catalogue by similarity to the given product (same category and style, main color,
    shared school/sport/theme tags, similar price) and keeps only items in stock in that size.

    Args:
        product: The product_id (preferred) or exact name of the item they wanted.
        size: The size needed (XS-XXL, or words like "large"). Leave empty to use the shopper's saved size.
        max_price: Optional budget in USD.
        limit: How many alternatives to return (1-6).
    """
    ctx.deps.tool_calls.append("find_alternatives")
    base = resolve_product(product)
    if base is None:
        return not_found(product)
    source = "asked"
    norm = normalize_size(size) if size else None
    if norm is None:
        if size:
            return f"'{size}' isn't one of our sizes (XS, S, M, L, XL, XXL)."
        if not ctx.deps.preferred_size:
            return "No size given and the shopper hasn't picked a size. Ask which size they need."
        norm, source = ctx.deps.preferred_size, "preferred_size"
    ctx.deps.saw_product(base)
    base_qty = next((x["quantity"] for x in base["inventory"] if x["size"] == norm), 0)
    picks = similar_products(base, norm, max_price, max(1, min(limit, 6)))
    for p, _, _ in picks:
        ctx.deps.saw_product(p)
    return AlternativesResult(
        original_product_id=base["product_id"],
        original_name=base["name"],
        size=norm,
        size_source=source,
        original_quantity_in_size=base_qty,
        alternatives=[
            AlternativeMatch(
                product_id=p["product_id"], name=p["name"], category=p["category"], price=p["price"],
                colors=p["colors"], description=p["description"], quantity_in_size=qty,
                status_in_size=stock_status(qty), why_similar=why,
            )
            for p, qty, why in picks
        ],
        note="" if picks else f"Nothing similar is in stock in {norm}" + (f" under ${max_price:.2f}" if max_price else "") + ". Offer other sizes or a broader search.",
    )


# ---------- Customer memory + page context tools ----------


def get_my_account(ctx: RunContext[AgentDeps]) -> CustomerProfile | str:
    """The logged-in shopper's own account: first/last name, email, member-since date, and when they last chatted.

    Use when they ask "what's my email?", "do you remember me?", or similar. Guests have no account.
    """
    ctx.deps.tool_calls.append("get_my_account")
    if ctx.deps.customer is None:
        return "The shopper is a guest (not logged in). There is no account on file; suggest logging in or creating an account."
    return ctx.deps.customer


def recall_past_conversations(
    ctx: RunContext[AgentDeps],
    query: str = "",
    oldest_first: bool = False,
    since: str | None = None,
    before: str | None = None,
    limit: int = 8,
) -> PastConversationSearch | str:
    """Search THIS logged-in shopper's earlier saved chats (older than the recent turns you already see).

    Use for "what was that hoodie you showed me last time?", "what did I ask about before?", or
    "what was the first thing I asked you?". Only ever returns this shopper's own messages.

    Args:
        query: Words to look for, e.g. "hoodie", "Davenport". Leave empty to list messages by date only.
        oldest_first: True to get their earliest messages (e.g. "the first thing I asked"); default is most recent first.
        since: Only messages on or after this date, YYYY-MM-DD (e.g. "2026-09-01").
        before: Only messages before this date, YYYY-MM-DD (e.g. "2026-10-01").
        limit: How many messages to return (1-12).
    """
    ctx.deps.tool_calls.append("recall_past_conversations")
    if ctx.deps.user is None:
        return "The shopper is a guest, so there is no saved chat history. Guest chats are not kept between visits."
    limit = max(1, min(limit, 12))
    words = [w for w in re.findall(r"[a-z0-9'-]+", query.lower()) if w not in STOPWORDS and len(w) > 1]
    sql = "SELECT role, content, products_json, page_product_id, created_at FROM chat_messages WHERE user_id = ?"
    params: list = [ctx.deps.user.id]
    for w in words:  # match the text, the products shown, or the product page it was asked from
        sql += " AND (lower(content) LIKE ? OR lower(coalesce(products_json, '')) LIKE ? OR lower(coalesce(page_product_id, '')) LIKE ?)"
        params += [f"%{w}%", f"%{w}%", f"%{w}%"]
    for value, op in ((since, ">="), (before, "<")):
        if value and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
            sql += f" AND date(created_at) {op} date(?)"
            params.append(value.strip())
    sql += f" ORDER BY id {'ASC' if oldest_first else 'DESC'} LIMIT ?"
    params.append(limit)
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
        span = conn.execute(
            "SELECT count(*) AS n, min(created_at) AS first, max(created_at) AS last FROM chat_messages WHERE user_id = ?",
            (ctx.deps.user.id,),
        ).fetchone()
    if not oldest_first:
        rows = list(reversed(rows))  # always present in chronological order
    matches = []
    for r in rows:
        shown = [p.get("name", "") for p in json.loads(r["products_json"] or "[]") if isinstance(p, dict)]
        content = r["content"][:500]
        if r["page_product_id"]:
            content = f"[asked on the {r['page_product_id']} product page] {content}"
        matches.append(PastMessage(when=r["created_at"], role=r["role"], content=content, products_shown=[n for n in shown if n][:6]))
    note = f"This shopper has {span['n']} saved messages, from {span['first']} to {span['last']} (UTC)."
    if not matches:
        note += " Nothing matched; try fewer or different words, or an empty query with oldest_first / dates."
    return PastConversationSearch(matches=matches, note=note)


def get_viewed_product(ctx: RunContext[AgentDeps]) -> ProductInfo | str:
    """Full details (description, price, colors, stock per size) of the product page the shopper is looking at right now.

    Use when they say "this", "it", or "this one" while on a product page.
    """
    ctx.deps.tool_calls.append("get_viewed_product")
    if ctx.deps.page_product is None:
        return "The shopper isn't on a product page right now. Ask which item they mean, or use search_products."
    p = product_by_id(ctx.deps.page_product["product_id"]) or ctx.deps.page_product
    ctx.deps.saw_product(p)
    return product_info(p)


TOOLS = [
    search_products, get_product_details, get_price, get_stock, list_categories, find_alternatives,
    get_viewed_product, get_my_account, recall_past_conversations,
]
