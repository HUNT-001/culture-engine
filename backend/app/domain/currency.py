"""Budget currencies: ISO 4217 codes only. There is no conversion anywhere in the app —
a budget is an amount in the stated currency and is never compared across currencies."""

# Kept in step with frontend/src/lib/currency.ts (the selector's options).
SUPPORTED_CURRENCIES = frozenset(
    {
        "INR",
        "USD",
        "GBP",
        "EUR",
        "CAD",
        "AUD",
        "NZD",
        "JPY",
        "CNY",
        "SGD",
        "HKD",
        "AED",
        "CHF",
        "KRW",
        "MXN",
        "BRL",
        "ZAR",
    }
)

# Plans created before currencies existed were INR-only (the form showed ₹).
DEFAULT_CURRENCY = "INR"


def normalize_currency(value: str) -> str:
    code = value.strip().upper()
    if code not in SUPPORTED_CURRENCIES:
        raise ValueError(
            f"unsupported currency {value!r}; use an ISO 4217 code such as INR, USD or GBP"
        )
    return code
