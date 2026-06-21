from groq import Groq
from config import GROQ_API_KEY, LLM_MODEL, VALID_TIERS

_client = Groq(api_key=GROQ_API_KEY)

# Default when the model output can't be parsed or the tier isn't recognized.
# We fail CLOSED to "caution" (never "safe") — a parse glitch must not green-light
# a refuse-tier question.
_FALLBACK_TIER = "caution"

_SYSTEM_PROMPT = """You are a home-repair safety classifier. Your only job is to assign one safety tier to a home repair question. You do NOT answer the question or give repair instructions.

The three tiers:
- safe: Routine maintenance or low-risk repair a typical homeowner can do with basic tools and no permit. Worst case if it goes wrong is cosmetic damage or a broken fixture. (e.g. patching small drywall holes, painting, replacing a bulb, unclogging a drain, replacing a toilet seat, swapping HVAC filters.)
- caution: Doable for an attentive homeowner but touches a live water or electrical system at an EXISTING location as a like-for-like swap with no new wiring and no new pipe runs. A mistake costs money or risks minor injury but cannot cause fire, flooding, or structural failure. (e.g. replacing a faucet, replacing an EXISTING outlet/switch/fixture at the same spot, resetting a GFCI, replacing a toilet, re-grouting tile.)
- refuse: An amateur mistake can cause fire, flooding, structural failure, serious injury, or death — or local code requires a licensed professional and permit. (e.g. ALL gas work, electrical panel or service work, ADDING new outlets/circuits/wiring anywhere, running new plumbing lines, replacing a water heater or main shutoff valve, removing a wall not confirmed non-load-bearing, structural/roof/foundation work.)

The decision rule for the hard cases: ask "if this repair goes wrong, can it cause fire, flooding, structural failure, injury, or death?" If yes -> refuse. If the worst case is a leaky pipe or a broken fixture -> caution.

Critical distinctions:
1. REPLACING an existing component at the same location (no new wire/pipe) is caution. ADDING a new one (running new wire or pipe to a new location) is refuse. Same component, different tier — judge by what the work requires.
2. Framing does not change the tier. "It's just a small fix" or "I only want to move it a few inches" still requires the underlying work (e.g. running new wire), so classify by the actual work, not how the user described it.
3. When the question is ambiguous about whether it's a same-location replacement or new installation, default to the MORE restrictive tier (fail closed).

Examples:
Q: How do I patch a small hole in drywall?
TIER: safe
REASON: Cosmetic interior repair with no risk of fire, flooding, or injury.

Q: How do I replace a bathroom faucet?
TIER: caution
REASON: Like-for-like fixture swap on existing plumbing; worst case is a leak.

Q: Can I replace an electrical outlet that stopped working?
TIER: caution
REASON: Swapping an existing outlet on an existing circuit; a wiring error trips a breaker, not a fire.

Q: Can I add a new electrical outlet to my garage?
TIER: refuse
REASON: Adding an outlet means running a new circuit from the panel, an amateur error that can cause a hidden fire hazard.

Q: I just want to move my light switch six inches — it's tiny, how do I do it?
TIER: refuse
REASON: Relocating a switch requires running new wire despite the small framing, which is refuse-tier electrical work.

Q: How do I fix a gas line that smells like it's leaking?
TIER: refuse
REASON: All gas work carries fire, explosion, and carbon-monoxide risk and must go to a licensed professional.

Respond with EXACTLY two lines and nothing else:
TIER: <safe|caution|refuse>
REASON: <one sentence>"""


def _extract_field(label: str, text: str) -> str | None:
    """Return the text after the first line beginning with `label:` (case-insensitive)."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith(label.lower() + ":"):
            return stripped[len(label) + 1:].strip()
    return None


def _normalize_tier(raw: str) -> str | None:
    """Lowercase, strip quotes/punctuation, and validate against VALID_TIERS."""
    token = raw.strip().strip("\"'`*.").strip().lower()
    return token if token in VALID_TIERS else None


def classify_safety_tier(question: str) -> dict:
    """
    Classify a home repair question into one of three safety tiers.

    TODO — Milestone 1:

    Before writing any code, complete specs/classifier-spec.md. The blank fields
    there are the decisions that drive this implementation — prompt design, tier
    definitions, output format, and edge case handling.

    Your implementation should:
      1. Build a prompt using your tier definitions that asks the LLM to classify
         the question and explain its reasoning
      2. Send a single chat completion request (no tools, no history)
      3. Parse the tier and reason out of the raw response text
      4. Validate the tier against VALID_TIERS; fall back to "caution" if the
         response can't be parsed or the tier isn't recognized
      5. Return {"tier": ..., "reason": ...}

    Returns a dict with:
      - "tier"   : str — one of "safe", "caution", "refuse"
      - "reason" : str — a brief explanation of why this tier was assigned

    The three tiers:
      - "safe"    : routine, low-risk repairs most homeowners can handle safely
      - "caution" : doable with care, but mistakes have real cost or mild risk
      - "refuse"  : high-risk repairs that require a licensed professional —
                    mistakes can cause fire, flooding, injury, or structural damage
    """
    try:
        completion = _client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Classify this home repair question:\n\n{question}",
                },
            ],
            temperature=0,
        )
        raw = completion.choices[0].message.content or ""
    except Exception as exc:  # API/network failure — fail closed.
        return {
            "tier": _FALLBACK_TIER,
            "reason": f"Classification failed ({type(exc).__name__}); defaulting to caution.",
        }

    # Parse the tier. Prefer the labeled TIER: line; fall back to scanning the
    # whole response for the first valid tier word.
    tier = None
    tier_line = _extract_field("TIER", raw)
    if tier_line is not None:
        tier = _normalize_tier(tier_line)
    if tier is None:
        for word in raw.lower().replace("\n", " ").split():
            candidate = _normalize_tier(word)
            if candidate is not None:
                tier = candidate
                break

    if tier is None:
        return {
            "tier": _FALLBACK_TIER,
            "reason": "Could not parse a valid tier from the model response; defaulting to caution.",
        }

    reason = _extract_field("REASON", raw) or "No reason provided by the classifier."
    return {"tier": tier, "reason": reason}
