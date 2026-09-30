from rivyou.extract import extract, logo_candidates, social_link
from rivyou.geo import address_candidates, states_in


def test_organization_metadata_cannot_turn_a_favicon_into_a_logo(page_factory):
    page = page_factory("""<script type="application/ld+json">
        {"@type":"Organization","logo":"/assets/favicon.png"}</script>""")
    assert logo_candidates(page) == []


def test_requires_both_checks(page_factory, storefront_html):
    store = extract([page_factory(storefront_html)], "id", "https://merchant.in/")
    assert store.status == "accepted"
    assert store.shop_identity == "brand.myshopify.com"
    assert {e.family for e in store.evidence if e.field == "shopify"} == {
        "identity",
        "delivery",
        "commerce",
    }
    assert store.state == "Karnataka"
    assert store.category == "Skincare"
    assert store.emails == ["hello@merchant.in"]
    assert store.phones == ["+919876543210"]
    assert store.socials == {"Instagram": ["https://instagram.com/testbrand"]}
    assert all(
        e.source_url and e.content_hash and e.observed_at for e in store.evidence
    )


def test_cdn_image_and_footer_are_not_shopify(page_factory):
    html = '<img src="https://cdn.shopify.com/a.png"><p>Powered by Shopify</p><a href="/products/test">Buy</a>'
    assert (
        extract([page_factory(html)], "id", "https://merchant.in/").shopify
        == "unconfirmed"
    )


def test_india_shipping_currency_and_tld_are_insufficient(
    page_factory, storefront_html
):
    html = storefront_html.replace(
        "Registered office: Brand Private Limited, 12 MG Road, Bengaluru, Karnataka 560001, India.",
        "Shipping to India. Prices in INR. Call +91 9876543210.",
    )
    store = extract([page_factory(html)], "id", "https://merchant.in/")
    assert store.shopify == "verified"
    assert store.india == "unconfirmed"
    assert store.status == "review"


def test_quote_in_pre_not_runtime_identity(page_factory):
    html = '<pre>Shopify.shop = "copied.myshopify.com";</pre><script src="/cdn/shopifycloud/test.js"></script><a href="/products/a">Buy</a>'
    assert (
        extract([page_factory(html)], "id", "https://merchant.in/").shopify
        == "unconfirmed"
    )


def test_conflicting_shop_ids_need_review(page_factory, storefront_html):
    html = storefront_html.replace(
        "</body>", '<script>Shopify.shop = "other.myshopify.com";</script></body>'
    )
    assert (
        extract([page_factory(html)], "id", "https://merchant.in/").shopify
        == "conflict"
    )


def test_wholesale_is_not_excluded(page_factory, storefront_html):
    assert (
        extract(
            [page_factory(storefront_html.replace("Test brand", "Wholesale supplier"))],
            "id",
            "https://merchant.in/",
        ).status
        == "accepted"
    )


def test_foreign_return_provider_is_not_india_proof():
    assert not address_candidates(
        [
            "Returns warehouse: Acme logistics partner, MG Road, Bengaluru Karnataka 560001 India"
        ],
        "https://merchant.com/contact",
    )


def test_registered_address_wins_over_corporate_address(page_factory, storefront_html):
    html = storefront_html.replace(
        "</body>", "<p>Corporate office: Mumbai, Maharashtra, 400001, India.</p></body>"
    )
    store = extract([page_factory(html)], "id", "https://merchant.in/")
    assert store.state == "Karnataka"
    assert len([e for e in store.evidence if e.field == "india"]) == 2


def test_address_conflicts_preserved_in_evidence(page_factory, storefront_html):
    html = storefront_html.replace(
        "</body>",
        "<p>Registered office: Other Building, Mumbai, Maharashtra 400001 India</p></body>",
    )
    store = extract([page_factory(html)], "id", "https://merchant.in/")
    assert store.state is None
    assert store.missing["state"] == "ambiguous"
    assert len([e for e in store.evidence if e.field == "india"]) == 2


def test_state_in_shipping_list_is_not_address():
    assert not address_candidates(
        ["Shipping destinations: Maharashtra, Karnataka 560001, India"],
        "https://merchant.in/contact",
    )


def test_pincode_alone_is_not_state():
    assert not address_candidates(
        ["Contact us: phone 560001 and price INR 560001"], "https://merchant.in/contact"
    )


def test_logo_excludes_account_and_social_icons(page_factory):
    page = page_factory(
        '<header><img alt="logo" src="/login-logout.png"><img alt="logo" src="/linkedin.svg"><a href="/"><img alt="Brand logo" src="/brand.png"></a></header><link rel="icon" href="/favicon.ico">'
    )
    choices = logo_candidates(page)
    assert len(choices) == 1
    assert choices[0][1] == "https://merchant.in/brand.png"


def test_logo_ignores_product_with_logo_in_name(page_factory):
    assert (
        logo_candidates(
            page_factory(
                '<a href="/products/shirt"><img src="/logo-shirt.jpg" alt="Logo shirt"></a>'
            )
        )
        == []
    )


def test_home_brand_image_outranks_press_logo(page_factory):
    page = page_factory(
        '<header><a href="/"><img src="/brand-logo.png"></a></header><section class="logo-list"><img src="/press-logo.png"></section>'
    )
    assert logo_candidates(page)[0][1].endswith("/brand-logo.png")


def test_favicon_not_a_logo(page_factory):
    assert logo_candidates(page_factory('<link rel="icon" href="/favicon.png">')) == []


def test_description_stays_verbatim(page_factory, storefront_html):
    store = extract([page_factory(storefront_html)], "id", "https://merchant.in/")
    assert store.description == "Small-batch skincare with sunscreen and face serum."


def test_home_decor_outweighs_coffee_mug_nav(page_factory):
    html = '<meta name="description" content="Handcrafted home decor and furniture for your home."><nav>Coffee mugs and tea cups</nav>'
    assert (
        extract([page_factory(html)], "id", "https://merchant.in/").category
        == "Home & living"
    )


def test_vendor_contact_excluded(page_factory, storefront_html):
    store = extract(
        [
            page_factory(
                storefront_html.replace(
                    "</body>", "<p>Payment gateway support: care@payu.in</p></body>"
                )
            )
        ],
        "id",
        "https://merchant.in/",
    )
    assert "care@payu.in" not in store.emails


def test_social_profiles_not_sharing_links():
    assert social_link("https://facebook.com/sharer.php?u=x") is None
    assert social_link("https://x.com/intent/tweet?text=x") is None
    assert social_link("https://youtube.com/watch?v=xyz") is None
    assert social_link("https://youtube.com/@brand") == (
        "YouTube",
        "https://youtube.com/@brand",
    )
    assert social_link("https://twitter.com/brand?utm_source=x") == (
        "X",
        "https://x.com/brand",
    )


def test_state_reference_handles_city():
    assert states_in("MG Road Bengaluru 560001") == ["Karnataka"]
