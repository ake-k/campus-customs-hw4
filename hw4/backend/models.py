"""Pydantic models for the Campus Customs API (structured data types live here)."""

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Size = Literal["XS", "S", "M", "L", "XL", "XXL"]

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# A few passwords so common that attackers try them first. Rejected at sign-up.
COMMON_PASSWORDS = {
    "password", "password1", "password123", "12345678", "123456789", "1234567890",
    "qwerty123", "qwertyuiop", "iloveyou", "letmein1", "welcome1", "admin123",
    "yalebulldogs", "bulldogs", "boolaboola", "campuscustoms",
}


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if len(email) > 254 or not EMAIL_RE.match(email):
        raise ValueError("Please enter a valid email address.")
    return email


class SignupRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    email: str
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str

    @field_validator("first_name", "last_name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Name can't be blank.")
        return v

    @field_validator("email")
    @classmethod
    def clean_email(cls, v: str) -> str:
        return normalize_email(v)

    @model_validator(mode="after")
    def check_passwords(self) -> "SignupRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords don't match.")
        if self.password.lower() in COMMON_PASSWORDS or self.password.lower() == self.email:
            raise ValueError("That password is too easy to guess. Please choose another.")
        return self


class LoginRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def clean_email(cls, v: str) -> str:
        return v.strip().lower()


class UserOut(BaseModel):
    """What the API ever reveals about a user. The password hash is never included."""

    id: int
    first_name: str
    last_name: str
    name: str
    email: str
    created_at: str
    preferred_size: Size | None = None  # saved from the size picker ("My size")


class PreferencesUpdate(BaseModel):
    preferred_size: Size | None = Field(None, description="The shopper's size, or null to clear it")


class SessionOut(BaseModel):
    user: UserOut | None


# ---------- Catalogue types (shared by the API, the agent's tools, and chat replies) ----------


class ProductCard(BaseModel):
    """What the chat widget shows for a product the assistant recommends.

    Always built from the database by product_id, never from model text, so the
    price and stock a shopper sees are the real ones.
    """

    product_id: str
    name: str
    category: str
    price: float
    image_url: str
    short_description: str
    colors: list[str]
    sizes_in_stock: list[str]
    total_stock: int


# ---------- Lookup results returned to the agent by its tools ----------
# Every number here (price, quantity) is read straight from campus_customs.db.
# The agent may only quote numbers that appear in these results.

LOW_STOCK_THRESHOLD = 5  # 1-5 units left counts as "low_stock"

StockStatus = Literal["in_stock", "low_stock", "sold_out"]


def stock_status(quantity: int) -> StockStatus:
    if quantity <= 0:
        return "sold_out"
    return "low_stock" if quantity <= LOW_STOCK_THRESHOLD else "in_stock"


class SizeAvailability(BaseModel):
    """Stock for one size of one product (one row of the inventory table)."""

    size: str = Field(description="XS, S, M, L, XL, or XXL")
    quantity: int = Field(description="Units on the shelf right now; 0 means sold out")
    status: StockStatus


class ProductInfo(BaseModel):
    """Everything we know about one product: catalogue row + its inventory rows."""

    product_id: str
    name: str
    category: str = Field(description="Shop category (normalized from garment_type)")
    garment_type: str
    price: float = Field(description="Price in USD from the catalogue table")
    description: str
    description_is_placeholder: bool = Field(description="True = no real description on file; don't describe details")
    colors: list[str]
    tags: list[str]
    sizes: list[SizeAvailability]
    sizes_in_stock: list[str]
    sold_out_sizes: list[str]
    total_in_stock: int


class ProductMatch(BaseModel):
    """One search hit: enough for the agent to pick products and answer simple questions."""

    product_id: str = Field(description="Use this id with the other tools and in product_ids")
    name: str
    category: str
    price: float = Field(description="Price in USD from the catalogue table")
    colors: list[str]
    description: str
    sizes_in_stock: list[str]
    low_stock_sizes: list[str] = Field(description="In-stock sizes with only 1-5 left")
    sold_out_sizes: list[str]


class SearchResult(BaseModel):
    total_matches: int
    showing: int
    matches: list[ProductMatch]
    note: str = ""


class PriceQuote(BaseModel):
    product_id: str
    name: str
    price: float = Field(description="Price in USD from the catalogue table")
    currency: Literal["USD"] = "USD"


class PriceLookup(BaseModel):
    """Prices for one or more products, for "how much is..." and price comparisons."""

    quotes: list[PriceQuote]
    not_found: list[str] = Field(default_factory=list, description="Requested products that don't exist")


class StockReport(BaseModel):
    """Stock for one product, either every size or one requested size."""

    product_id: str
    name: str
    price: float
    requested_size: str | None = Field(None, description="The size the shopper asked about, normalized (e.g. 'medium' -> 'M')")
    requested_quantity: int | None = Field(None, description="Units in the requested size (0 = sold out)")
    requested_status: StockStatus | None = None
    sizes: list[SizeAvailability] = Field(description="Every size this product comes in, XS to XXL")
    sizes_in_stock: list[str]
    sold_out_sizes: list[str]
    total_in_stock: int
    summary: str = Field(description="One plain-English sentence of the result, safe to paraphrase")


class AlternativeMatch(BaseModel):
    """A similar product that IS in stock in the requested size."""

    product_id: str
    name: str
    category: str
    price: float = Field(description="Price in USD from the catalogue table")
    colors: list[str]
    description: str
    quantity_in_size: int = Field(description="Units in stock in the requested size")
    status_in_size: StockStatus
    why_similar: str = Field(description="Plain-English reasons it's a good substitute")


class AlternativesResult(BaseModel):
    """In-stock substitutes for a product, in one size (find_alternatives)."""

    original_product_id: str
    original_name: str
    size: str = Field(description="The size checked (normalized), e.g. 'L'")
    size_source: Literal["asked", "preferred_size"] = Field(description="Whether the size came from the question or the shopper's saved size")
    original_quantity_in_size: int = Field(description="Units of the ORIGINAL product in that size (0 = sold out)")
    alternatives: list[AlternativeMatch]
    note: str = ""


# ---------- Chat ----------


ShopCategory = Literal["Hoodies", "Crewnecks", "T-Shirts", "Quarter-Zips", "Jackets & Fleece", "Long Sleeves"]
MAX_RESULT_CARDS = 12


class ChatAgentOutput(BaseModel):
    """The agent's structured answer for one turn (the agent side of the chat -> page contract)."""

    reply: str = Field(description="What to say to the shopper, in the Campus Customs voice. Plain text; short '- ' bullet lists are fine.")
    product_ids: list[str] = Field(
        default_factory=list,
        max_length=MAX_RESULT_CARDS,
        description="product_id values (from tool results) of the items to show on the page as product cards, best first "
        f"(up to {MAX_RESULT_CARDS}). Include every good match for 'what X do you have?' questions. Empty if no product fits.",
    )
    results_heading: str | None = Field(
        None,
        max_length=60,
        description="Short title for the product cards shown on the page, e.g. 'Hoodies', 'Navy hoodies under $70', "
        "'Davenport College gear'. No counts. Required whenever product_ids is not empty.",
    )
    see_all_category: ShopCategory | None = Field(
        None,
        description="If the shopper asked about a whole category, that category, so the page can link to the full "
        "category listing. Otherwise null.",
    )


CARD_LIKE = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")


class PageContext(BaseModel):
    """Where the shopper is on the website when they send a chat message.

    Sent by the browser; the backend only trusts product_id after looking it up in the database.
    """

    path: str = Field("/", max_length=200, description="The page's path + query, e.g. /products/basic-hoodie-big-yale")
    product_id: str | None = Field(None, max_length=120, description="Set on a single-item page")
    category: ShopCategory | None = Field(None, description="Set on the Products page when a category tab is selected")
    search: str | None = Field(None, max_length=100, description="Text in the Products page search box, if any")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    page: PageContext | None = None
    preferred_size: Size | None = Field(None, description="The size picked in the site's size picker (guests); accounts use their saved size")

    @field_validator("message")
    @classmethod
    def clean_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Please type a message.")
        # Card-like numbers never reach the model or the saved chat history.
        return CARD_LIKE.sub("[card number removed]", v)


class ChatMessageOut(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    products: list[ProductCard] = []
    page_product_id: str | None = None  # product page the shopper was on when they sent this (user messages)


# ---------- Customer memory (what the agent knows about a logged-in shopper) ----------


class CustomerProfile(BaseModel):
    """The logged-in shopper, as the agent sees them. No password hash or other customers' data, ever."""

    user_id: int
    first_name: str
    last_name: str
    email: str
    member_since: str = Field(description="Account creation date (YYYY-MM-DD)")
    saved_messages: int = Field(description="Chat messages already saved for this shopper, before this one")
    last_chat_at: str | None = Field(None, description="When they last chatted with us (UTC), or null if this is their first chat")
    preferred_size: Size | None = Field(None, description="Their saved size from the size picker")


class PastMessage(BaseModel):
    when: str = Field(description="UTC timestamp")
    role: Literal["user", "assistant"]
    content: str
    products_shown: list[str] = Field(default_factory=list, description="Names of products shown with this message")


class PastConversationSearch(BaseModel):
    """Matches from THIS shopper's own saved chats (never anyone else's)."""

    matches: list[PastMessage]
    note: str = ""


class ProductResults(BaseModel):
    """Product cards for the website to render on the page (the server side of the chat -> page contract).

    Built by the backend from the agent's product_ids: every card is re-read from the database.
    """

    heading: str = Field(description="Title shown above the cards")
    query: str = Field(description="The shopper message that produced these results")
    products: list[ProductCard]
    category: ShopCategory | None = Field(None, description="Set when the results are a whole category")
    category_total: int | None = Field(None, description="How many items the shop has in that category (from the database)")
    see_all_url: str | None = Field(None, description="Link to the full category listing on the Products page")


class ChatLimits(BaseModel):
    """How many more messages this shopper may send (shown in the chat when running low)."""

    remaining_this_minute: int
    remaining_today: int
    per_minute: int
    per_day: int


class ChatResponse(BaseModel):
    reply: str
    screened: bool = False  # True = blocked by the input check before reaching the model (reply is a canned message)
    limits: ChatLimits | None = None
    products: list[ProductCard]  # same cards as results.products; also shown as mini cards in the chat bubble
    results: ProductResults | None  # None when the reply has no products to show on the page
    user: UserOut | None  # who the assistant thinks it is talking to (None = guest)


class ChatHistory(BaseModel):
    messages: list[ChatMessageOut]
    user: UserOut | None


# ---------- Audit trail (output/audit_trail.json, append-only) ----------


class AuditToolCall(BaseModel):
    """One tool the model asked for during one loop iteration."""

    tool_name: str
    tool_call_id: str
    args: dict = Field(default_factory=dict, description="Arguments, long values shortened")
    status: Literal["ok", "retry", "final answer accepted", "not run"] = "not run"
    result_summary: str = Field("", description="Short version of what the tool returned (or why it was retried)")


class AuditIteration(BaseModel):
    """One turn of the agent loop: a model call, then the tools it requested."""

    step: int
    started_at: str
    model_seconds: float
    tool_seconds: float = 0.0
    finish_reason: str | None = None
    thought: str = Field("", description="Any text the model produced alongside its tool calls")
    tool_calls: list[AuditToolCall] = Field(default_factory=list)


class AuditUsage(BaseModel):
    model_requests: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


class AuditEntry(BaseModel):
    """Everything that happened for one chat message. Appended, never rewritten."""

    run_id: str
    kind: Literal["chat", "screened", "rate_limited"]
    started_at: str
    finished_at: str
    total_seconds: float
    status: Literal["ok", "blocked", "error"]
    stop_reason: str = Field(description="Why the run ended: final answer, screened, rate limit, usage limit, timeout, error")
    model: str
    system_prompt_sha256: str = Field(description="Fingerprint of prompts/prompt.md used for this run")
    shopper: str = Field(description="'user:<id>' or 'guest' (no names or emails are logged)")
    page_path: str | None = None
    page_product_id: str | None = None
    preferred_size: str | None = None
    message: str = Field("", description="The shopper's message after redaction (card numbers, SSNs, passwords removed), max 300 chars")
    redactions: list[str] = Field(default_factory=list)
    iterations: list[AuditIteration] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    product_ids: list[str] = Field(default_factory=list, description="Products shown as cards with the reply")
    reply: str = Field("", description="The reply shown to the shopper, max 400 chars")
    grounding_retries: int = 0
    usage: AuditUsage = Field(default_factory=AuditUsage)
