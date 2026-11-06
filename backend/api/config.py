"""Configurable limits for the capture API.

These values are not final. See docs/API_CONTRACT.md section 11.
"""

# Minimum GPS samples needed to describe a loop (proposed, not in the contract).
MIN_SAMPLES = 4

# Contract section 4: the sample count must not exceed 10,000.
# UNFINISHED: 10,000 samples is about 1 MB of JSON, but one SQS message
# can hold only 256 KB. The team must decide how to handle this.
MAX_SAMPLES = 10_000
