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
ACTION_REFUSE_THRESHOLD = 0.90

# --- Voice check (TTS reply text) ---------------------------------------------
VOICE_MAX_WORDS = 35
VOICE_MAX_SENTENCES = 2
VOICE_MIN_NATURAL = 0.60      # below -> "klingt geschrieben"
VOICE_MIN_ONE_TOPIC = 0.60    # below -> split into two messages
VOICE_MAX_FILLER = 0.50       # at or above -> opener/closer present

# --- Uncertainty escalation ----------------------------------------------------
# Only the answers that *carry* a decision are checked. A noul inside
# [0.5-band, 0.5+band] is uncertain. For a score, the decision is uncertain when the
# probability mass on the levels beyond the threshold is at least SCORE_TAIL, even
# though the expected score stayed below. Uncertain decisions are escalated one step
# (gatekeeper: drop/log -> queue, autonomy: send -> review, action: execute -> ask)
# so Grok Bot takes a second look instead of Jev deciding alone.
UNCERTAIN_NOUL_BAND = 0.15
UNCERTAIN_SCORE_TAIL = 0.40
# Action gate uses a slightly wider tail: reads outside the workspace on the user's own
# request sit at ~0.30 tail mass and should still execute.
ACTION_UNCERTAIN_SCORE_TAIL = 0.40
