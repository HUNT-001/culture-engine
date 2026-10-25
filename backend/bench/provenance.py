"""Evidence provenance tags.

Every reported metric carries exactly one of these tags so a reader can tell *what kind
of evidence* produced it. They are ordered from weakest to strongest claim about the
real product.
"""
from __future__ import annotations

# Pure arithmetic on synthetic inputs. Verifies the metric maths only; says nothing
# about the product.
SYNTHETIC_ARITHMETIC = "synthetic-arithmetic"

# A real production function/class called directly with synthetic inputs.
PRODUCTION_FUNCTION = "production-function"

# Real adapter + workflow (+ routes) driven by Qloo-shaped fixtures over an in-process
# mock HTTP transport. Exercises production code end to end but NOT the real Qloo
# service. Never call this "live".
MOCKED_INTEGRATION = "mocked-integration"

# A request that actually reached the Qloo hackathon API. None in v2 (budget: 0).
LIVE_REQUEST = "live-request"

# Ratings from real people. None collected yet.
HUMAN_STUDY = "human-study"

ALL_TAGS = (
    SYNTHETIC_ARITHMETIC,
    PRODUCTION_FUNCTION,
    MOCKED_INTEGRATION,
    LIVE_REQUEST,
    HUMAN_STUDY,
)

LEGEND = {
    SYNTHETIC_ARITHMETIC: "benchmark-side arithmetic on synthetic inputs; checks metric maths only",
    PRODUCTION_FUNCTION: "a real production function called with synthetic inputs",
    MOCKED_INTEGRATION: ("real adapter/workflow/routes over mock HTTP fixtures; "
                         "not the real Qloo service"),
    LIVE_REQUEST: "a request that reached the live Qloo API (none in v2)",
    HUMAN_STUDY: "ratings from real participants (none collected yet)",
}
