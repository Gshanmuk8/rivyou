from rivyou.extract import select_links
from rivyou.geo import address_candidates


def test_registered_office_can_omit_pin_but_needs_full_address_structure():
    text = "Registered office at Angoori Badi, AA -2, Ansal Villas, Satbari, Chattarpur, New Delhi, India."
    found = address_candidates([text], "https://brand.in/pages/privacy-policy")
    assert found[0]["states"] == ["Delhi"]
    assert found[0]["priority"] == 4
    assert found[0]["basis"] == "registered_office_without_pin"
    assert not address_candidates(
        ["Registered office in Delhi, India."], "https://brand.in/"
    )
    assert not address_candidates(
        ["Shipping to Delhi, India, from our office at 12 London Road."],
        "https://brand.in/",
    )


def test_parwanoo_alias_requires_address_context_and_pin():
    text = "Address: Solidus Lifesciences Private Limited, #25, Sector 2, Parwanoo, H.P. 173220"
    assert address_candidates([text], "https://brand.in/")[0]["states"] == [
        "Himachal Pradesh"
    ]
    assert not address_candidates(
        ["Visit Parwanoo for our summer sale"], "https://brand.in/"
    )


def test_informational_crawl_does_not_follow_products_containing_about_or_contact(
    page_factory,
):
    page = page_factory("""<a href="/products/all-about-love">All about love</a>
        <a href="/collections/contact-lenses">Contact lenses</a>
        <a href="/pages/contact-us">Contact us</a><a href="/policies/privacy-policy">Privacy</a>""")
    assert select_links(page) == [
        "https://merchant.in/pages/contact-us",
        "https://merchant.in/policies/privacy-policy",
    ]


def test_toy_description_outweighs_incidental_nursery_navigation(page_factory):
    from rivyou.extract import extract

    page = page_factory(
        '<meta name="description" content="Toys, games, action figures and collectibles."><nav>Nursery</nav>'
    )
    assert extract([page], "test", page.url).category == "Toys & games"


def test_single_navigation_keyword_does_not_guess_category(page_factory):
    from rivyou.extract import extract

    page = page_factory("<title>A brand</title><nav>Nursery</nav>")
    assert extract([page], "test", page.url).category is None


def test_office_label_and_founding_year_are_not_a_street_address():
    from rivyou.geo import address_candidates

    assert not address_candidates(
        ["Registered office: Company Limited, Delhi, India. Established 2020."],
        "https://merchant.in/pages/contact",
    )


def test_template_emails_and_malformed_space_entities_are_not_contacts(page_factory):
    from rivyou.extract import extract

    page = page_factory(
        '<p>&nbsp &nbspcontact@merchant.in</p><a href="mailto:shop@yourstore.com">hello@merchant.in</a>'
    )
    assert extract([page], "test", page.url).emails == [
        "contact@merchant.in",
        "hello@merchant.in",
    ]


def test_structured_contacts_require_the_merchants_organization_url(page_factory):
    from rivyou.extract import extract

    page = page_factory("""<script type="application/ld+json">[
      {"@type":"Organization","url":"https://merchant.in/","telephone":"+91-63661-60553"},
      {"@type":"Organization","url":"https://supplier.com/","telephone":"+91-98765-43210"}
    ]</script><p>Call +91 63661 60553 9AM - 1 PM</p>""")
    store = extract([page], "test", page.url)
    assert store.phones == ["+916366160553"]
    assert any(e.rule == "merchant_organization_contact" for e in store.evidence)


def test_personalized_gift_description_outweighs_bag_navigation(page_factory):
    from rivyou.extract import extract

    page = page_factory(
        '<meta name="description" content="An online gift shop for personalized custom gifts."><nav>Backpacks Wallets</nav>'
    )
    assert extract([page], "test", page.url).category == "Gifts & personalization"
