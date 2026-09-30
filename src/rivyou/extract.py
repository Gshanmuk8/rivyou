"""Pure extraction: saved HTML in, typed values and attributable evidence out."""

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urljoin, urlsplit, urlunsplit

import phonenumbers
from bs4 import BeautifulSoup

from .categories import TAXONOMY
from .fetch import Fetched
from .geo import address_candidates
from .models import Evidence, Store
from .urls import host_of, known_domain, normalize_url, same_site

EMAIL = re.compile(
    r"\b[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9](?:[A-Z0-9.-]*[A-Z0-9])?\.[A-Z]{2,24}\b",
    re.IGNORECASE,
)
SHOP_ID = re.compile(
    r"(?:window\.)?Shopify\.shop\s*=\s*['\"]([a-z0-9][a-z0-9-]*\.myshopify\.com)['\"]",
    re.IGNORECASE,
)
IGNORED_EMAILS = {
    "example.com",
    "domain.com",
    "email.com",
    "yourdomain.com",
    "yourstore.com",
    "yourcompany.com",
    "yourwebsite.com",
    "yoursite.com",
    "example.org",
    "example.net",
    "sentry.io",
    "shopify.com",
    "payu.in",
    "razorpay.com",
    "paypal.com",
    "google.com",
    "facebook.com",
    "emarsys.com",
}
NETWORKS = {
    "instagram.com": "Instagram",
    "facebook.com": "Facebook",
    "twitter.com": "X",
    "x.com": "X",
    "linkedin.com": "LinkedIn",
    "youtube.com": "YouTube",
    "pinterest.com": "Pinterest",
}


@dataclass
class Page:
    fetched: Fetched
    soup: BeautifulSoup

    @classmethod
    def from_fetch(cls, value):
        return cls(value, BeautifulSoup(value.body, "lxml"))

    @property
    def url(self):
        return self.fetched.final_url

    def visible_soup(self):
        soup = BeautifulSoup(str(self.soup), "lxml")
        for node in soup(["script", "style", "noscript", "template"]):
            node.decompose()
        for node in soup.select("[hidden], [aria-hidden='true']"):
            node.decompose()
        return soup

    def evidence(self, field, value, rule, excerpt="", family=""):
        return Evidence(
            field=field,
            value=value,
            source_url=self.url,
            rule=rule,
            excerpt=excerpt[:900],
            observed_at=self.fetched.observed_at,
            content_hash=self.fetched.digest,
            family=family,
        )


def structured(soup):
    def walk(value):
        if isinstance(value, dict):
            yield value
            for child in value.values():
                if isinstance(child, (dict, list)):
                    yield from walk(child)
        elif isinstance(value, list):
            for child in value:
                yield from walk(child)

    for script in soup.select('script[type="application/ld+json"]'):
        try:
            yield from walk(json.loads(script.string or script.get_text()))
        except (ValueError, RecursionError):
            continue


def social_link(value: str) -> tuple[str, str] | None:
    try:
        p = urlsplit(value)
        host = (p.hostname or "").lower().removeprefix("www.").removeprefix("m.")
        if host not in NETWORKS or p.scheme not in {"http", "https"}:
            return None
        path = p.path.strip("/")
        parts = path.split("/")
        if parts[0].lower() in {
            "settings",
            "privacy",
            "help",
            "policies",
            "terms",
            "about",
            "home",
            "explore",
            "accounts",
            "account",
            "watch",
            "marketplace",
            "business",
            "signup",
            "register",
            "notifications",
            "messages",
            "search",
            "ads",
        }:
            return None
        if host == "youtube.com" and parts[-1] in {
            "featured",
            "videos",
            "shorts",
            "playlists",
            "about",
        }:
            parts = parts[:-1]
            path = "/".join(parts)
        if ":" in unquote(path) or any(c.isspace() for c in unquote(path)):
            return None
        if (
            host in {"instagram.com", "twitter.com", "x.com", "pinterest.com"}
            and len(parts) != 1
        ):
            return None
        if (
            host == "facebook.com"
            and len(parts) > 1
            and not (len(parts) == 3 and parts[0] in {"pages", "people"})
        ):
            return None
        if host == "linkedin.com":
            if len(parts) < 2 or parts[0] not in {"company", "in", "school"}:
                return None
            if len(parts) > 2 and parts[2:] != ["mycompany"]:
                return None
            path = "/".join(parts[:2])
        if host == "youtube.com" and not (
            (len(parts) == 1 and parts[0].startswith("@") and len(parts[0]) > 1)
            or (len(parts) == 2 and parts[0] in {"channel", "c", "user"} and parts[1])
        ):
            return None
        if not path or re.search(
            r"(^|/)(share|sharer|sharer.php|share.php|intent|dialog|login|plugins|embed|p|reel)(/|$)",
            path,
            re.IGNORECASE,
        ):
            return None
        if host == "youtube.com" and not (
            path.startswith(("@", "channel/", "c/", "user/"))
        ):
            return None
        query = ""
        if host == "facebook.com" and path == "profile.php":
            ident = parse_qs(p.query).get("id", [""])[0]
            if not ident.isdigit():
                return None
            query = "id=" + ident
        if host == "twitter.com":
            host = "x.com"
        return NETWORKS[
            p.hostname.lower().removeprefix("www.").removeprefix("m.")
        ], urlunsplit(("https", host, "/" + path, query, ""))
    except (ValueError, AttributeError):
        return None


def valid_email(email: str) -> bool:
    """Reject template/provider contacts and text concatenation artifacts."""
    domain = email.rsplit("@", 1)[-1]
    return bool(
        EMAIL.fullmatch(email)
        and known_domain(domain)
        and domain not in IGNORED_EMAILS
        and not domain.endswith((".png", ".jpg", ".webp"))
        and not email.startswith(("yourname@", "example@"))
    )


def runtime_asset(src: str) -> bool:
    """A theme favicon or image is not executable/style runtime evidence."""
    return bool(
        re.search(
            r"(?:cdn\.shopify\.com/shopifycloud/|/cdn/shopifycloud/|/cdn/shop/t/\d+/assets/)",
            src,
        )
        and urlsplit(src).path.lower().endswith((".js", ".mjs", ".css"))
    )


def select_links(page: Page) -> list[str]:
    priority = {
        "contact": 10,
        "about": 8,
        "privacy": 7,
        "terms": 7,
        "legal": 7,
        "return": 6,
        "shipping": 4,
    }
    found = {}
    for link in page.soup.select("a[href]"):
        href = link.get("href", "")
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        try:
            url = normalize_url(urljoin(page.url, href))
        except ValueError:
            continue
        if not same_site(page.url, url):
            continue
        path = urlsplit(url).path.lower()
        if (
            re.search(r"/(?:cart|checkout|account|search)(?:/|$)", path)
            or re.search(r"^/(?:products|collections|apps)/|^/blogs/[^/]+/", path)
            or urlsplit(url).query
        ):
            continue
        label = path + " " + link.get_text(" ", strip=True).lower()
        score = max((v for k, v in priority.items() if k in label), default=0)
        if score:
            found[url] = max(found.get(url, 0), score)
    return sorted(found, key=lambda u: (-found[u], u))


def logo_candidates(page: Page) -> list[tuple[int, str, str]]:
    choices = []
    for obj in structured(page.soup):
        types = obj.get("@type", "")
        if "Organization" in types or "Store" in types:
            logo = obj.get("logo")
            if isinstance(logo, dict):
                logo = logo.get("url") or logo.get("contentUrl")
            if isinstance(logo, str) and logo:
                choices.append((20, urljoin(page.url, logo), "organization_logo"))
    for img in page.soup.select("img"):
        name = " ".join(
            [
                str(img.get("alt", "")),
                " ".join(img.get("class", [])),
                str(img.get("id", "")),
            ]
        ).lower()
        src = img.get("data-src") or img.get("src") or ""
        if not src or src.startswith("data:"):
            srcset = img.get("data-srcset") or img.get("srcset") or ""
            src = srcset.split(",")[-1].strip().split(" ")[0] if srcset else ""
        if not src or re.search(
            r"favicon|payment|visa|mastercard|placeholder|pixel|whatsapp|facebook|linkedin|instagram|youtube|logout|login|account|cart|social",
            src + " " + name,
            re.IGNORECASE,
        ):
            continue
        in_header = (
            img.find_parent(["header"]) is not None
            or img.find_parent(attrs={"class": re.compile("header", re.IGNORECASE)})
            is not None
        )
        marked = bool(
            re.search(r"(?:^|[^a-z])logo(?:[^a-z]|$)", name + " " + src, re.IGNORECASE)
        )
        anchor = img.find_parent("a", href=True)
        home_link = bool(
            anchor
            and same_site(page.url, urljoin(page.url, anchor["href"]))
            and urlsplit(urljoin(page.url, anchor["href"])).path in {"/", ""}
        )
        if not (marked and (in_header or home_link)) and not (in_header and home_link):
            continue
        score = (
            (6 if marked else 0) + (5 if in_header else 0) + (12 if home_link else 0)
        )
        choices.append(
            (
                score,
                urljoin(page.url, src),
                "header_brand_image" if in_header else "logo_attribute",
            )
        )
    out = {}
    for score, url, rule in choices:
        if re.search(r"favicon|\.ico(?:[?#]|$)", url, re.IGNORECASE):
            continue
        try:
            # Do not normalize away image version/width parameters.
            p = urlsplit(url)
            if p.scheme not in {"https", "http"} or not p.hostname:
                continue
            if re.search(r"favicon", p.path, re.IGNORECASE):
                continue
            if url not in out or score > out[url][0]:
                out[url] = (score, url, rule)
        except ValueError:
            continue
    return sorted(out.values(), reverse=True)


def extract(pages: list[Page], store_id: str, candidate_url: str) -> Store:
    if not pages:
        return Store(
            store_id=store_id,
            domain_url=candidate_url,
            status="unreachable",
            reason="No allowed HTML page was retrieved.",
        )
    home = pages[0]
    store = Store(
        store_id=store_id,
        domain_url=normalize_url(home.url, homepage=True),
        pages_checked=len(pages),
        aliases=list(dict.fromkeys([candidate_url, *home.fetched.chain])),
        observed_at=max(p.fetched.observed_at for p in pages),
    )
    title = home.soup.select_one('meta[property="og:site_name"]')
    if title and title.get("content"):
        store.name = title["content"].strip()[:120]
    else:
        raw = (
            home.soup.title.get_text(" ", strip=True)
            if home.soup.title
            else host_of(home.url)
        )
        store.name = re.split(r"\s[|–—]\s", raw)[0][:90]
    for selector in ['meta[name="description"]', 'meta[property="og:description"]']:
        meta = home.soup.select_one(selector)
        if meta and len(meta.get("content", "").strip()) >= 20:
            description = meta["content"].strip()
            store.description = description[:700]
            rule = (
                "meta_description_truncated"
                if len(description) > 700
                else "meta_description"
            )
            store.evidence.append(
                home.evidence("description", store.description, rule, store.description)
            )
            break

    emails, phones, socials = set(), set(), defaultdict(set)
    identities, runtime, commerce, platform_conflicts = set(), [], False, []
    addresses = []
    for page in pages:
        soup = page.visible_soup()
        text = soup.get_text(" ", strip=True)
        # Some storefronts omit the semicolon in a non-breaking-space entity.
        # Decode only that known markup artifact; do not rewrite email spelling.
        text = re.sub(r"&nbsp;?", " ", text)
        for script in page.soup.select("script"):
            if script.get("type", "").lower() in {
                "application/ld+json",
                "application/json",
            }:
                continue
            for identity in SHOP_ID.findall(script.string or script.get_text()):
                identities.add(identity.lower())
                store.evidence.append(
                    page.evidence(
                        "shopify",
                        identity.lower(),
                        "shopify_shop_assignment",
                        f"Shopify.shop = '{identity}'",
                        "identity",
                    )
                )
        for tag in page.soup.select("script[src], link[href]"):
            src = tag.get("src") or tag.get("href") or ""
            if runtime_asset(src):
                runtime.append(src)
                if not any(
                    e.field == "shopify" and e.family == "delivery"
                    for e in store.evidence
                ):
                    store.evidence.append(
                        page.evidence(
                            "shopify",
                            urljoin(page.url, src),
                            "shopify_runtime_asset",
                            src,
                            "delivery",
                        )
                    )
        commerce_node = page.soup.select_one(
            'a[href*="/products/"], form[action*="/cart/add"], [itemtype*="schema.org/Product"]'
        )
        if commerce_node:
            commerce = True
            if not any(
                e.field == "shopify" and e.family == "commerce" for e in store.evidence
            ):
                attribute = next(
                    key
                    for key in ("href", "action", "itemtype")
                    if commerce_node.get(key)
                )
                store.evidence.append(
                    page.evidence(
                        "shopify",
                        "commerce_markup",
                        "storefront_commerce_markup",
                        f"{commerce_node.name} {attribute}={commerce_node[attribute]}",
                        "commerce",
                    )
                )
        if re.search(r"/wp-content/plugins/woocommerce/", str(page.soup)):
            platform_conflicts.append("WooCommerce assets present")

        contact_values = [(m, "visible_email") for m in EMAIL.findall(text)]
        phone_values = []
        for organization in structured(page.soup):
            kinds = organization.get("@type", [])
            kinds = [kinds] if isinstance(kinds, str) else kinds
            if not isinstance(kinds, list) or not any(
                kind
                in {
                    "Organization",
                    "Corporation",
                    "LocalBusiness",
                    "Store",
                    "OnlineStore",
                }
                for kind in kinds
                if isinstance(kind, str)
            ):
                continue
            organization_url = organization.get("url")
            try:
                if not isinstance(organization_url, str) or not same_site(
                    page.url, organization_url
                ):
                    continue
            except ValueError:
                continue
            points = organization.get("contactPoint", [])
            points = points if isinstance(points, list) else [points]
            for point in [organization, *points]:
                if not isinstance(point, dict):
                    continue
                for field in ("email", "telephone"):
                    values = point.get(field, [])
                    values = values if isinstance(values, list) else [values]
                    for value in values:
                        if not isinstance(value, str):
                            continue
                        if field == "email":
                            contact_values.extend(
                                (m, "merchant_organization_contact")
                                for m in EMAIL.findall(value)
                            )
                        else:
                            phone_values.append(
                                (value, "merchant_organization_contact")
                            )
        for a in soup.select("a[href]"):
            href = str(a.get("href", ""))
            if href.lower().startswith("mailto:"):
                displayed = EMAIL.findall(a.get_text(" ", strip=True))
                contact_values.extend(
                    (m, "mailto_link")
                    for m in (
                        displayed or EMAIL.findall(unquote(href.split("?", 1)[0]))
                    )
                )
            if href.lower().startswith("tel:"):
                phone_values.append((unquote(href[4:]), "tel_link"))
            if re.match(r"https?://(?:wa.me|api.whatsapp.com)/", href):
                p = urlsplit(href)
                value = (
                    p.path.strip("/")
                    if p.hostname == "wa.me"
                    else parse_qs(p.query).get("phone", [""])[0]
                )
                if value:
                    phone_values.append(
                        ("+" + value.lstrip("+"), "whatsapp_business_link")
                    )
            social = social_link(urljoin(page.url, href))
            if social and social[1] not in socials[social[0]]:
                socials[social[0]].add(social[1])
                store.evidence.append(
                    page.evidence(
                        "socials", {social[0]: social[1]}, "merchant_profile_link", href
                    )
                )
        for email, rule in contact_values:
            email = email.strip(".,;").lower()
            if not valid_email(email):
                continue
            if email not in emails:
                emails.add(email)
                store.evidence.append(page.evidence("emails", email, rule, email))
        # libphonenumber requires complete numbers; local-region interpretation is only a parsing hint.
        for match in phonenumbers.PhoneNumberMatcher(text, "IN"):
            if match.number.country_code == 91 and not re.search(
                r"\+?91|phone|call|contact|whatsapp|mobile|tel",
                text[max(0, match.start - 50) : match.end + 20],
                re.IGNORECASE,
            ):
                continue
            phone_values.append((match.raw_string, "visible_phone"))
        for value, rule in phone_values:
            try:
                number = phonenumbers.parse(value, "IN")
                if not phonenumbers.is_valid_number(number):
                    continue
                normalized = phonenumbers.format_number(
                    number, phonenumbers.PhoneNumberFormat.E164
                )
                if number.extension:
                    normalized += " ext. " + number.extension
                if normalized not in phones:
                    phones.add(normalized)
                    store.evidence.append(
                        page.evidence("phones", normalized, rule, value)
                    )
            except phonenumbers.NumberParseException:
                pass
        blocks = []
        for element in soup.select("address, p, li, div, section, td, span"):
            chunk = element.get_text(" ", strip=True)
            if 20 <= len(chunk) <= 900:
                blocks.append(chunk)
        for address in address_candidates(blocks, page.url):
            addresses.append((page, address))

    store.emails, store.phones = sorted(emails), sorted(phones)
    store.socials = {k: sorted(v) for k, v in sorted(socials.items())}
    if len(identities) > 1 or platform_conflicts:
        store.shopify = "conflict"
    elif identities and runtime and commerce:
        store.shopify = "verified"
        store.shop_identity = next(iter(identities))
    else:
        store.shopify = "unconfirmed"
    # Prefer the most explicit principal-office evidence, never a currency or shipping clue.
    if addresses:
        priority = max(a["priority"] for _, a in addresses)
        chosen = [(p, a) for p, a in addresses if a["priority"] == priority]
        states = {s for _, a in chosen for s in a["states"]}
        store.india = "verified"
        store.state = next(iter(states)) if len(states) == 1 else None
        for page, address in addresses:
            store.evidence.append(
                page.evidence(
                    "india",
                    "India",
                    address["basis"],
                    address["excerpt"],
                    "business_location",
                )
            )
            if len(states) == 1 and address["priority"] == priority:
                store.evidence.append(
                    page.evidence(
                        "state",
                        store.state,
                        "state_in_business_address",
                        address["excerpt"],
                    )
                )
        if len(states) > 1:
            store.missing["state"] = "ambiguous"

    # Merchant descriptions outweigh a stray 'coffee mug' or gift keyword in navigation.
    primary_text = " ".join([store.name, store.description or ""]).lower()
    nav_text = " ".join(
        n.get_text(" ", strip=True) for n in home.soup.select("nav, h1, h2")
    )[:12000].lower()
    scores = {}
    for category, words in TAXONOMY.items():
        matches = [
            w
            for w in words
            if re.search(r"\b" + re.escape(w) + r"\b", primary_text + " " + nav_text)
        ]
        if matches:
            weight = sum(
                4 if re.search(r"\b" + re.escape(w) + r"\b", primary_text) else 1
                for w in matches
            )
            # One incidental navigation word is not enough to classify a store.
            if weight >= 2:
                scores[category] = (weight, matches)
    if scores:
        ranked = sorted(scores, key=lambda k: scores[k][0], reverse=True)
        if len(ranked) == 1 or scores[ranked[0]][0] > scores[ranked[1]][0]:
            store.category = ranked[0]
            store.evidence.append(
                home.evidence(
                    "category",
                    store.category,
                    "weighted_taxonomy_keywords",
                    ", ".join(scores[ranked[0]][1]),
                )
            )
        else:
            store.missing["category"] = "ambiguous"

    if store.shopify == store.india == "verified":
        store.status, store.reason = (
            "accepted",
            "Store identity and Indian business address are supported by live pages.",
        )
    else:
        store.status = "review"
        store.reason = (
            "Conflicting platform evidence."
            if store.shopify == "conflict"
            else "Shopify identity needs review."
            if store.shopify != "verified"
            else "Shopify is supported; an Indian business address is still needed."
        )
    for field in [
        "emails",
        "phones",
        "socials",
        "category",
        "description",
        "logo_url",
        "state",
    ]:
        if not getattr(store, field):
            store.missing.setdefault(field, "not_found_in_allowed_pages")
    # Deduplicate evidence without collapsing independent source URLs.
    unique = {}
    for e in store.evidence:
        unique[
            (
                e.field,
                json.dumps(e.value, sort_keys=True),
                e.source_url,
                e.rule,
                e.excerpt,
            )
        ] = e
    store.evidence = list(unique.values())
    return store
