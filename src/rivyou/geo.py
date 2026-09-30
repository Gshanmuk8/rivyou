"""Address-context rules, deliberately conservative and independent of currency."""

import re

STATES = [
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chhattisgarh",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
    "Andaman and Nicobar Islands",
    "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi",
    "Jammu and Kashmir",
    "Ladakh",
    "Lakshadweep",
    "Puducherry",
]
CITY_STATE = {
    "mumbai": "Maharashtra",
    "pune": "Maharashtra",
    "bengaluru": "Karnataka",
    "bangalore": "Karnataka",
    "gurugram": "Haryana",
    "gurgaon": "Haryana",
    "ahmedabad": "Gujarat",
    "surat": "Gujarat",
    "chennai": "Tamil Nadu",
    "hyderabad": "Telangana",
    "kolkata": "West Bengal",
    "jaipur": "Rajasthan",
    "noida": "Uttar Pradesh",
    "new delhi": "Delhi",
    "newdelhi": "Delhi",
    "kochi": "Kerala",
    "lucknow": "Uttar Pradesh",
    "indore": "Madhya Pradesh",
    "parwanoo": "Himachal Pradesh",
}
CONTEXT = re.compile(
    r"\b(address|registered office|corporate office|head office|principal office|office address|contact us|contact information|operated by|owned by)\b",
    re.IGNORECASE,
)
NON_BUSINESS = re.compile(
    r"\b(shipping destinations?|deliver(?:y|ing)? (?:across|to)|ship(?:ping)? (?:across|to)|our (?:suppliers|distributors)|manufactured by)\b",
    re.IGNORECASE,
)
RETURN_ONLY = re.compile(
    r"\b(return address|returns warehouse|fulfil[l]?ment|logistics partner)\b",
    re.IGNORECASE,
)


def states_in(text: str) -> list[str]:
    hits = [
        state
        for state in STATES
        if re.search(r"\b" + re.escape(state) + r"\b", text, re.IGNORECASE)
    ]
    if "Dadra and Nagar Haveli and Daman and Diu" in hits:
        return ["Dadra and Nagar Haveli and Daman and Diu"]
    if not hits:
        hits = list(
            dict.fromkeys(
                state
                for city, state in CITY_STATE.items()
                if re.search(r"\b" + re.escape(city) + r"\b", text, re.IGNORECASE)
            )
        )
    return hits


def address_candidates(blocks: list[str], page_url: str) -> list[dict]:
    found = []
    contact_page = bool(
        re.search(r"(?:contact|privacy|terms|legal)", page_url, re.IGNORECASE)
    )
    for text in blocks:
        text = " ".join(text.split())
        if len(text) < 20 or len(text) > 900:
            continue
        if NON_BUSINESS.search(text) or RETURN_ONLY.search(text):
            continue
        states = states_in(text)
        india = bool(re.search(r"\bIndia\b", text, re.IGNORECASE))
        pin = bool(re.search(r"(?<!\d)[1-9]\d{5}(?!\d)", text))
        # Require explicit business context plus address structure; never a state in a menu.
        context = bool(CONTEXT.search(text))
        street = bool(
            re.search(
                r"\b(road|street|floor|plot|sector|building|office|industrial|estate|nagar|lane|avenue|marg|village|district|pincode|pin code|villas?|colony|complex|phase|block|house|flat|tower|layout|cross|rd)\b",
                text,
                re.IGNORECASE,
            )
        )
        registered = bool(
            re.search(
                r"\b(?:registered|principal) (?:offices?|address)\b",
                text,
                re.IGNORECASE,
            )
        )
        # A labelled registered office with a street/premise, locality and country
        # can establish location even when the merchant omits its postal code.
        strong_unpinned = bool(
            registered
            and india
            and len(states) == 1
            and re.search(
                r"\b(road|street|plot|building|sector|nagar|lane|avenue|marg|villas?|colony|complex|block|house|flat|tower|layout|cross|rd)\b",
                text,
                re.IGNORECASE,
            )
            and re.search(r"\b(?:[A-Z]{1,3}\s*[-/]?\s*)?\d{1,5}\b", text)
        )
        if (
            (context or contact_page)
            and states
            and (pin or strong_unpinned)
            and (street or context)
            and (india or len(states) == 1)
        ):
            priority = (
                4
                if registered
                else 3
                if re.search(
                    r"head office|corporate (?:office|address)", text, re.IGNORECASE
                )
                else 2
            )
            found.append(
                {
                    "excerpt": text,
                    "states": states,
                    "priority": priority,
                    "basis": "business_address"
                    if pin
                    else "registered_office_without_pin",
                }
            )
        elif context and india and pin and street:
            found.append(
                {
                    "excerpt": text,
                    "states": states,
                    "priority": 2,
                    "basis": "business_address",
                }
            )
    # Repeated footer blocks should not create repeated evidence.
    unique = {}
    for row in found:
        unique[row["excerpt"]] = row
    # Exclude enclosing blocks when a smaller complete address is available.
    # This avoids a parent footer merging several unrelated addresses into one.
    values = list(unique.values())
    return [
        row
        for row in values
        if not any(
            other is not row
            and other["excerpt"] in row["excerpt"]
            and other["priority"] >= row["priority"]
            for other in values
        )
    ]
