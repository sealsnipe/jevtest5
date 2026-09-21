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
