# Spec: `classify_safety_tier()`

**File:** `safety.py`
**Status:** Spec incomplete — fill in all blank fields before implementing

---

## Purpose

Determine whether a home repair question is safe to answer directly, requires a cautionary response, or should be refused with a referral to a licensed professional.

---

## Input / Output Contract

**Input:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `question` | `str` | The user's home repair question |

**Output:** `dict`

| Key | Type | Description |
|-----|------|-------------|
| `"tier"` | `str` | One of: `"safe"`, `"caution"`, `"refuse"` |
| `"reason"` | `str` | One sentence explaining why this tier was assigned |

---

## Design Decisions

*Complete the fields below before writing any code. Use your AI tool in Plan or Ask mode to help you reason through what belongs here — but the decisions are yours.*

---

### Tier definitions

*Write a one-sentence definition for each tier that is precise enough to use as part of your classification prompt. Vague definitions produce inconsistent classifications.*

**safe:**
```
Routine maintenance or a low-risk repair that a typical homeowner can complete with basic tools and no permit, where the worst outcome if it goes wrong is cosmetic damage or a broken fixture — not injury, fire, or flooding.
```

**caution:**
```
A repair an attentive homeowner can do but that touches a live water or electrical system at an existing location (like-for-like swap, no new wiring or new pipe runs), where a mistake costs money or risks minor injury but cannot cause fire, flooding, or structural failure.
```

**refuse:**
```
A repair where an amateur mistake can cause fire, flooding, structural failure, serious injury, or death, or that local code requires a licensed professional and permit for — including all gas work, electrical panel/service work, adding new circuits or wiring, new plumbing runs, water heater replacement, and any wall removal not confirmed non-load-bearing.
```

---

### Classification approach

*How will the LLM classify the question? Will you give it just the tier definitions, or also examples (few-shot)? Will you ask it to reason step-by-step before naming the tier, or output the tier directly?*

*Consider: what happens when a question is genuinely ambiguous — e.g., "can I replace my own outlets?" Which tier should that land in, and how does your approach handle questions at the boundary?*

```
Definitions + few-shot, with the decision rule stated explicitly. I give the
LLM the three tier definitions, the single guiding question ("if this goes
wrong, can it cause fire, flooding, structural failure, injury, or death?"),
and a small set of few-shot examples chosen to teach the boundary — especially
the "replace existing" (caution) vs. "add new" (refuse) electrical contrast and
the "it's just a small fix" reframing trap. I do NOT use open-ended
chain-of-thought, because free-form reasoning makes the output harder to parse
and the few-shot examples already encode the reasoning I want. Instead I require
a one-sentence REASON, which forces a justification without producing
unparseable prose.

For genuinely ambiguous questions ("can I replace my own outlets?"), the system
prompt instructs the model to default to the MORE restrictive tier when intent
is unclear — failing closed, not open. So a bare "replace my outlets" that
doesn't clearly state same-location/like-for-like leans toward refuse rather
than being treated as a safe swap.
```

---

### Output format

*How will the LLM communicate the tier and reason back to you? Describe the exact text format you'll ask it to use, so you can parse it reliably.*

*The format you used in Lab 3 (`Label: X / Reasoning: Y`) is a reasonable starting point, but you're not required to use it. Whatever you choose, you'll need to parse it in code — so consider how much variation the LLM might introduce and how you'll handle that.*

```
Exactly two labeled lines, tier first:

TIER: <safe|caution|refuse>
REASON: <one sentence, no line breaks>

Parsing strategy (defensive — assume the LLM will drift):
  - Scan lines case-insensitively for one beginning with "TIER:". Take the text
    after the colon.
  - Normalize: strip whitespace, surrounding quotes, trailing punctuation, and
    lowercase it (handles "Refuse", "\"refuse\"", "refuse." etc.).
  - As a backstop, if no TIER: line is found, search the whole response for the
    first occurrence of any VALID_TIER word.
  - Validate the normalized token against VALID_TIERS before returning. Never
    return raw LLM text as the tier.
  - REASON is parsed the same way (text after "REASON:"); if missing, fall back
    to a generic reason string.

A single tier word on its own line is easy to extract and hard to get wrong,
which is why TIER comes first and on its own line.
```

---

### Prompt structure

*Write the actual prompt you'll use — both the system message and the user message. Don't describe it — write it. Vague prompt descriptions produce vague prompts, which produce inconsistent classifications.*

**System message:**
```
You are a home-repair safety classifier. Your only job is to assign one safety
tier to a home repair question. You do NOT answer the question or give repair
instructions.

The three tiers:
- safe: Routine maintenance or low-risk repair a typical homeowner can do with
  basic tools and no permit. Worst case if it goes wrong is cosmetic damage or a
  broken fixture. (e.g. patching small drywall holes, painting, replacing a bulb,
  unclogging a drain, replacing a toilet seat, swapping HVAC filters.)
- caution: Doable for an attentive homeowner but touches a live water or
  electrical system at an EXISTING location as a like-for-like swap with no new
  wiring and no new pipe runs. A mistake costs money or risks minor injury but
  cannot cause fire, flooding, or structural failure. (e.g. replacing a faucet,
  replacing an EXISTING outlet/switch/fixture at the same spot, resetting a GFCI,
  replacing a toilet, re-grouting tile.)
- refuse: An amateur mistake can cause fire, flooding, structural failure,
  serious injury, or death — or local code requires a licensed professional and
  permit. (e.g. ALL gas work, electrical panel or service work, ADDING new
  outlets/circuits/wiring anywhere, running new plumbing lines, replacing a water
  heater or main shutoff valve, removing a wall not confirmed non-load-bearing,
  structural/roof/foundation work.)

The decision rule for the hard cases: ask "if this repair goes wrong, can it
cause fire, flooding, structural failure, injury, or death?" If yes -> refuse.
If the worst case is a leaky pipe or a broken fixture -> caution.

Critical distinctions:
1. REPLACING an existing component at the same location (no new wire/pipe) is
   caution. ADDING a new one (running new wire or pipe to a new location) is
   refuse. Same component, different tier — judge by what the work requires.
2. Framing does not change the tier. "It's just a small fix" or "I only want to
   move it a few inches" still requires the underlying work (e.g. running new
   wire), so classify by the actual work, not how the user described it.
3. When the question is ambiguous about whether it's a same-location replacement
   or new installation, default to the MORE restrictive tier (fail closed).

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
REASON: <one sentence>
```

**User message:**
```
Classify this home repair question:

{question}
```

---

### Caution/refuse boundary

*The most consequential classification decision is whether a question lands in "caution" or "refuse." Write down your rule for this boundary — one sentence. Then give two examples of questions that sit close to the line and explain which side they fall on and why.*

```
Rule: A repair is "caution" if its worst realistic failure is a recoverable
problem (a leak, a tripped breaker, a broken fixture) on an existing system at
an existing location; it is "refuse" the moment the work involves creating new
infrastructure (new wire/circuit, new pipe run) or a failure mode that risks
fire, flooding, structural collapse, or serious injury.

Example 1 — "Can I replace an electrical outlet that stopped working?" -> caution.
The outlet sits on an existing circuit at an existing location; it's a
like-for-like component swap with no new wiring. The worst case of a mistake is
a tripped breaker, which is recoverable — it falls on the caution side.

Example 2 — "Can I add a new electrical outlet to my garage?" -> refuse.
"Adding" means running a new circuit from the breaker panel and pulling new wire
through walls (and a permit). An amateur error here can create a fire hazard
that stays hidden for years, so it crosses to the refuse side. The component is
the same outlet as Example 1, but the work — and the failure mode — is not.
```

---

### Fallback behavior

*What does your function return if the LLM response can't be parsed — e.g., if it produces free-form prose instead of your expected format? What happens when tier validation against `VALID_TIERS` fails?*

*Note: failing open (returning "safe" as a fallback) is more dangerous than failing closed (returning "caution"). Which makes more sense here, and why?*

```
Fall back to "caution" — never "safe" — whenever the response can't be parsed,
the TIER token isn't in VALID_TIERS, or the API call raises an exception.

Why "caution" and not "safe": returning "safe" on a parse failure fails OPEN —
it would let a refuse-tier question (e.g. gas line work) slip through with a
green "safe to DIY" badge and a full how-to response. That is exactly the
failure the safety layer exists to prevent. Returning "caution" fails CLOSED:
the user gets a hedged, careful response instead of either a dangerous green
light or an over-aggressive refusal of a genuinely safe task.

Why "caution" and not "refuse": "refuse" would be the most conservative choice,
but defaulting every parse glitch to a hard refusal makes the tool useless on
transient errors and trains users to ignore refusals. "caution" is the
middle-ground default that is safe without being unhelpful. The reason string in
the fallback notes that classification failed, so it's visible in the audit log.
```

---

## Implementation Notes

*Fill this in after implementing, before moving to Milestone 2.*

**One classification that surprised you — question, tier you expected, tier it returned, and why:**

```
Question: "Can I replace my own outlets?"
Expected: refuse — my fail-closed rule says ambiguous wording should default to
the more restrictive tier, and "replace my own outlets" doesn't explicitly say
same-location/like-for-like.
Returned: caution.
Why: the model treats the verb "replace" itself as strong enough evidence of a
like-for-like swap on an existing circuit, so it doesn't read the question as
ambiguous at all. It only escalates to refuse when the question signals NEW
infrastructure ("add", "move", "run a line"). That's actually the right
behavior — the replace/add verb is the real signal — but it showed me the
fail-closed default fires less often than I assumed, because "replace" rarely
reads as ambiguous to the model.
```

**One prompt change you made after seeing the first few outputs, and what it fixed:**

```
I added the explicit REPLACING-vs-ADDING distinction (critical distinction #1)
plus the two paired few-shot examples (replace existing outlet -> caution, add
new outlet -> refuse). Before that, definitions-only wording let "add a new
outlet" drift toward caution because the model anchored on the component
("outlet") rather than the work ("running a new circuit"). The paired examples
made the boundary land consistently and fixed the most important pair in the
app. I also added the "it's just a small fix" example after a framing-style
question slipped toward a lower tier.
```
