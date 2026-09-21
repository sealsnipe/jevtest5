"""Thresholds for all Jev layers. Tune here, never inside prompts.

Values are deliberately conservative for a first run. After the smoke test,
adjust them against tests/*.py expectations.
"""

# --- Layer 1: Gatekeeper -------------------------------------------------------
# Above this spam probability the message is dropped without waking Grok Bot.
SPAM_DROP_THRESHOLD = 0.80

# Below this "needs_action" probability the message is logged only (no wake-up).
WAKE_THRESHOLD = 0.50

# Normalized urgency (0..1). At or above -> ping the boss immediately,
# otherwise the message goes into the normal queue for the secretary bot.
URGENT_THRESHOLD = 0.75

# Minimum confidence for the intent choice. Below -> intent "unklar", the
# secretary bot asks a clarifying question instead of acting.
INTENT_MIN_CONFIDENCE = 0.40

# --- Layer 3: Firewall (folded into the gatekeeper request) --------------------
# At or above this injection probability the message is blocked, checked before spam.
INJECTION_BLOCK_THRESHOLD = 0.70

# --- Layer 2: Autonomy gate (draft -> send | review) ---------------------------
# Draft must match the request at least this well, otherwise review.
AUTONOMY_MIN_FIT = 0.70
# Above this probability the draft contains a commitment (price, promise, legal) -> review.
AUTONOMY_COMMITMENT_THRESHOLD = 0.30
# Normalized risk (0..1) at or above -> review.
AUTONOMY_RISK_THRESHOLD = 0.50

# --- Chef reply classification -------------------------------------------------
# Minimum confidence for the chef reply type; below -> "unklar" (secretary asks back).
CHEF_REPLY_MIN_CONFIDENCE = 0.50

# --- Follow-up matching (message -> open case) ---------------------------------
# Minimum confidence to attach a message to an existing open case; below -> new case.
MATCH_MIN_CONFIDENCE = 0.55

# --- Transcript check ----------------------------------------------------------
# Below this "understandable" probability the bot asks the sender to repeat / type.
TRANSCRIPT_MIN_UNDERSTANDABLE = 0.50
# At or above this "truncated" probability the bot asks for the rest, even if the start is clear.
TRANSCRIPT_MAX_TRUNCATED = 0.80

# --- Layer 6: Action gate ------------------------------------------------------
# Normalized risk (0..1): < ASK -> execute, >= ASK -> ask the boss, >= REFUSE -> refuse + log.
ACTION_ASK_THRESHOLD = 0.50
ACTION_REFUSE_THRESHOLD = 0.85
