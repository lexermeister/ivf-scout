INITIAL_SOURCES: list[dict[str, object]] = [
    {
        "name": "CooperSurgical",
        "slug": "cooper-surgical",
        "domain": "coopersurgical.com",
        "website_url": "https://www.coopersurgical.com/",
        "news_url": "https://www.coopersurgical.com/category/press-release/",
        "article_url_patterns": ["/press-release/"],
        "scan_query": (
            "IVF fertility product launch equipment consumables regulatory clearance press release"
        ),
        "source_type": "MANUFACTURER",
        "enabled": True,
    },
    {
        "name": "Vitrolife",
        "slug": "vitrolife",
        "domain": "vitrolife.com",
        "website_url": "https://www.vitrolife.com/",
        "news_url": "https://www.vitrolife.com/",
        "article_url_patterns": ["/our-products/", "/news/"],
        "scan_query": (
            "IVF media incubator embryo evaluation genetics product launch regulatory announcement"
        ),
        "source_type": "MANUFACTURER",
        "enabled": True,
    },
    {
        "name": "Kitazato",
        "slug": "kitazato",
        "domain": "kitazato.co.jp",
        "website_url": "https://www.kitazato.co.jp/en/",
        "news_url": "https://www.kitazato.co.jp/en/ir/ir-all/",
        "article_url_patterns": ["/en/ir/", "/en/images/sites/"],
        "scan_query": (
            "IVF vitrification culture media catheter consumable product launch R&D regulatory"
        ),
        "source_type": "MANUFACTURER",
        "enabled": True,
    },
    {
        "name": "Esco Medical",
        "slug": "esco-medical",
        "domain": "esco-medical.com",
        "website_url": "https://www.esco-medical.com/",
        "news_url": "https://www.esco-medical.com/home",
        "article_url_patterns": ["/news/"],
        "scan_query": (
            "IVF incubator workstation witnessing automation AI product launch partnership"
        ),
        "source_type": "MANUFACTURER",
        "enabled": True,
    },
    {
        "name": "Hamilton Thorne",
        "slug": "hamilton-thorne",
        "domain": "hamiltonthorne.com",
        "website_url": "https://www.hamiltonthorne.com/",
        "news_url": "https://www.hamiltonthorne.com/",
        "article_url_patterns": ["/news/", "/press-release/", "/press-releases/"],
        "scan_query": (
            "IVF laser imaging CASA AI integration laboratory equipment product announcement"
        ),
        "source_type": "MANUFACTURER",
        "enabled": True,
    },
    {
        "name": "Memphasys",
        "slug": "memphasys",
        "domain": "memphasys.com",
        "website_url": "https://www.memphasys.com/",
        "news_url": "https://www.memphasys.com/investor-relations/asx-announcements/",
        "article_url_patterns": ["/wp-content/uploads/"],
        "scan_query": (
            "Felix sperm selection IVF ART product regulatory approval CE mark clinical study "
            "commercial launch distribution agreement Europe ASX announcement"
        ),
        "source_type": "MANUFACTURER",
        "enabled": True,
    },
    {
        "name": "Minitube Human ART",
        "slug": "minitube-human-art",
        "domain": "minitube-humanart.com",
        "website_url": "https://www.minitube-humanart.com/",
        "news_url": "https://www.minitube-humanart.com/en/news/",
        "article_url_patterns": ["/en/news/"],
        "scan_query": (
            "IVF ART product launch cryopreservation consumables embryo and oocyte handling "
            "incubator laboratory equipment regulatory approval MDR certification innovation"
        ),
        "source_type": "MANUFACTURER",
        "enabled": True,
    },
]
