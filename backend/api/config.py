"""Configurable limits for the capture API.

These values are not final. See docs/API_CONTRACT.md section 11.
"""

# Minimum GPS samples needed to describe a loop (proposed, not in the contract).
MIN_SAMPLES = 4

# Contract section 4: the sample count must not exceed 10,000.
# 10,000 samples is about 1.04 MB of JSON. After gzip + base64 it is about
# 134 KiB for a realistic route and about 321 KiB for the worst case (random
# points), so it fits in one SQS message (see MAX_MESSAGE_BYTES).
MAX_SAMPLES = 10_000

# Largest request body the API accepts, in bytes.
# PROPOSED, not decided yet (docs/API_CONTRACT.md section 10, item 6).
# 10,000 samples is about 1.04 MB of JSON, so 2 MB leaves some room.
MAX_BODY_BYTES = 2_000_000

# Hard limit for one SQS message body, in bytes (1 MiB). SQS has allowed 1 MiB
# since August 2025, but a queue created before that may still be set to 256 KiB.
# The queue's MaximumMessageSize must therefore be at least this value
# (an infrastructure setting, not decided here).
MAX_MESSAGE_BYTES = 1_048_576

# Room kept for the other fields of the message (IDs and field names).
MESSAGE_ENVELOPE_BYTES = 2_048
