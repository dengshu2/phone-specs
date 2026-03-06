"""models 模块单元测试。"""

from phone_specs.models import Brand, PhoneSpecs, QuickSpecs, SpecGroup, SpecItem


def test_brand_creation():
    brand = Brand(brand_id=48, brand_name="Apple", brand_slug="apple-phones-48", device_count=147)
    assert brand.brand_name == "Apple"
    assert brand.device_count == 147


def test_phone_specs_to_dict():
    specs = PhoneSpecs(
        brand="Xiaomi",
        phone_name="17 Ultra",
        thumbnail="https://example.com/thumb.jpg",
        phone_images=["https://example.com/1.jpg"],
        quick=QuickSpecs(
            release_date="2026, March",
            os="Android 16",
            storage="512GB",
            battery="6000",
        ),
        specifications=[
            SpecGroup(
                title="Network",
                specs=[SpecItem(key="Technology", val=["GSM / HSPA / LTE / 5G"])],
            ),
        ],
    )

    d = specs.to_dict()

    assert d["brand"] == "Xiaomi"
    assert d["phone_name"] == "17 Ultra"
    assert d["release_date"] == "2026, March"
    assert d["os"] == "Android 16"
    assert d["battery"] == "6000"
    assert len(d["specifications"]) == 1
    assert d["specifications"][0]["title"] == "Network"
    assert d["specifications"][0]["specs"][0]["key"] == "Technology"


def test_quick_specs_defaults():
    q = QuickSpecs()
    assert q.release_date == ""
    assert q.battery == ""
