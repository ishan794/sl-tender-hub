"""
Advanced SEO Optimization Module for Sri Lanka Tender Hub
Includes:
- Schema.org structured data (JSON-LD) for Google rich snippets
- XML Sitemap generation (auto-updated daily)
- Robots.txt endpoint
- RSS/Atom feed for latest tenders
- Open Graph / Twitter Card meta tag generation
- Canonical URLs
- Breadcrumb data
- Category/tag optimized metadata
- Multi-language SEO support (English/Sinhala/Tamil basic)
"""
import os
from datetime import datetime, date
from typing import Dict, List, Optional
from database import get_tenders, get_db_connection
from config import BASE_DIR
import json
import hashlib

# Site configuration - update these to match your domain
SITE_CONFIG = {
    "site_name": "Sri Lanka Tender Hub",
    "site_url": os.getenv("SITE_URL", "https://yourdomain.com"),
    "site_description": "All open government and private tenders in Sri Lanka in one place. Daily updated from Treasury, CEB, NWSDB, Mahaweli, Railways, and 80+ government institutions and private aggregators.",
    "site_keywords": "Sri Lanka tenders, government tenders Sri Lanka, procurement notices, CEB tenders, NWSDB tenders, construction bids, SLPA, Mahaweli tenders, e-procurement, bidding opportunities Sri Lanka",
    "language": "en",
    "locale": "en_LK",
    "logo_url": "/static/logo.png",
    "contact_email": "info@yourdomain.com",
    "update_frequency": "daily",
    "priority_default": 0.7,
}

# Category-level SEO metadata
CATEGORY_SEO = {
    "construction": {
        "title": "Construction Tenders Sri Lanka | Building & Road Bids",
        "description": "Latest construction tenders in Sri Lanka including buildings, roads, bridges, irrigation, civil engineering works from government and private sector.",
        "keywords": "construction tenders Sri Lanka, road construction bids, building tenders, civil engineering Sri Lanka, RDA, irrigation projects",
        "priority": 0.8,
        "changefreq": "daily"
    },
    "goods": {
        "title": "Supply & Goods Tenders Sri Lanka | Equipment & Materials",
        "description": "Latest supply and goods procurement tenders in Sri Lanka: vehicles, machinery, equipment, stationery, pharmaceuticals, and general supplies.",
        "keywords": "supply tenders Sri Lanka, equipment bids, goods procurement, vehicle tenders, pharmaceutical supplies, machinery",
        "priority": 0.7,
        "changefreq": "daily"
    },
    "services": {
        "title": "Services Tenders Sri Lanka | Consultancy & Maintenance Bids",
        "description": "Service tenders including consultancy, security, cleaning, maintenance, financial, insurance, and professional services across Sri Lanka.",
        "keywords": "service tenders, consultancy bids, maintenance contracts, security services, insurance tenders Sri Lanka",
        "priority": 0.7,
        "changefreq": "daily"
    },
    "IT": {
        "title": "IT & Technology Tenders Sri Lanka | Software & Hardware Bids",
        "description": "Latest IT, software development, hardware supply, network infrastructure, server, and technology tenders from Sri Lankan government and private sector.",
        "keywords": "IT tenders Sri Lanka, software development bids, hardware procurement, computer tenders, network infrastructure, ICT tenders",
        "priority": 0.7,
        "changefreq": "daily"
    },
    "health": {
        "title": "Healthcare & Medical Tenders Sri Lanka | Pharmaceutical Bids",
        "description": "Healthcare tenders including pharmaceuticals, medical equipment, hospital supplies, and healthcare services across Sri Lanka.",
        "keywords": "medical tenders Sri Lanka, pharmaceutical bids, hospital supplies, healthcare equipment, SPMC, medical procurement",
        "priority": 0.6,
        "changefreq": "weekly"
    },
    "agriculture": {
        "title": "Agriculture Tenders Sri Lanka | Farming, Seeds & Fertilizer",
        "description": "Agriculture tenders including seeds, fertilizer, machinery, livestock, fisheries, and agri-projects across Sri Lanka.",
        "keywords": "agriculture tenders, seed procurement, fertilizer bids, agriculture Sri Lanka, livestock, fisheries, agrarian services",
        "priority": 0.6,
        "changefreq": "weekly"
    },
    "energy": {
        "title": "Energy & Power Tenders Sri Lanka | CEB, LECO & CPC Bids",
        "description": "Power and energy tenders including electricity projects, solar power, transformers, fuel, petroleum from CEB, LECO, CPC, CPSTL.",
        "keywords": "CEB tenders, energy bids Sri Lanka, power projects, solar tenders, LECO procurement, petroleum, fuel tenders",
        "priority": 0.7,
        "changefreq": "daily"
    },
    "education": {
        "title": "Education Tenders Sri Lanka | University & School Procurement",
        "description": "Education sector tenders from universities, schools, UGC, Ministry of Education including supplies, construction, and services.",
        "keywords": "education tenders, university procurement Sri Lanka, school supplies, UGC, educational services",
        "priority": 0.5,
        "changefreq": "weekly"
    },
    "transport": {
        "title": "Transport Tenders Sri Lanka | Railways, Vehicles & Road Transport",
        "description": "Transport sector tenders including Sri Lanka Railways, vehicles, buses, logistics, and transport services.",
        "keywords": "railway tenders, vehicle procurement, transport bids Sri Lanka, SLR, buses, lorry, transport services",
        "priority": 0.6,
        "changefreq": "weekly"
    },
    "other": {
        "title": "All Sri Lanka Tenders | Government & Private Procurement Notices",
        "description": SITE_CONFIG['site_description'],
        "keywords": SITE_CONFIG['site_keywords'],
        "priority": 0.5,
        "changefreq": "daily"
    },
}

def generate_slug(text: str) -> str:
    """Generate a SEO-friendly URL slug from text"""
    import re
    text = text.lower()
    # Remove non-alphanumeric characters
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'\s+', '-', text.strip())
    text = re.sub(r'-+', '-', text)
    return text[:80]

def get_tender_url(tender: Dict) -> str:
    """Generate SEO-friendly canonical URL for a tender"""
    slug = generate_slug(tender.get('title', 'tender'))
    master_id = tender.get('master_group_id', '')
    return f"{SITE_CONFIG['site_url']}/tender/{master_id}/{slug}"

def get_category_url(category: str) -> str:
    return f"{SITE_CONFIG['site_url']}/category/{category.lower()}"

def get_source_url(source_site_id: str) -> str:
    return f"{SITE_CONFIG['site_url']}/source/{source_site_id}"

def generate_meta_tags(tender: Dict) -> Dict:
    """Generate full SEO meta tags for a tender detail page (for your web app frontend to use)"""
    title = tender.get('title', 'Sri Lanka Tender Notice')
    # Truncate title to fit 60 char meta length
    if len(title) > 45:
        title = title[:45].rsplit(' ', 1)[0] + '...'
    org = tender.get('organization', '')
    # Truncate organization name
    if len(org) > 15:
        org = org[:15].rsplit(' ',1)[0] + '...'
    if org:
        meta_title = f"{title} | {org} | SL Tenders"
    else:
        meta_title = f"{title} | Sri Lanka Tenders"
    # Enforce max 60 chars for SEO
    if len(meta_title) > 60:
        meta_title = meta_title[:57] + '...'

    # Generate description (first 160 chars of description or title + category)
    desc = tender.get('description') or ''
    if desc:
        meta_desc = desc[:155].strip() + '...'
    else:
        category = tender.get('category', 'procurement')
        closing = tender.get('closing_date', '')
        meta_desc = f"Latest {category} tender notice from {org}. Closing date {closing}. View full details, documents, and submit bids."
        meta_desc = meta_desc[:155] + '...'

    keywords_parts = [
        f"{org} tender", f"Sri Lanka {tender.get('category','')} tender",
        "Sri Lanka tender", "bidding opportunity"
    ]
    if tender.get('category'):
        keywords_parts.append(f"{tender['category']} bids")
    meta_keywords = ", ".join(keywords_parts)

    return {
        "title": meta_title,
        "description": meta_desc,
        "keywords": meta_keywords,
        "canonical": get_tender_url(tender),
        "og:title": meta_title,
        "og:description": meta_desc,
        "og:type": "article",
        "og:url": get_tender_url(tender),
        "og:site_name": SITE_CONFIG['site_name'],
        "og:locale": SITE_CONFIG['locale'],
        "twitter:card": "summary_large_image",
        "twitter:title": meta_title,
        "twitter:description": meta_desc,
        "robots": "index, follow, max-snippet:-1, max-image-preview:large",
        "article:published_time": tender.get('published_date'),
        "article:expiration_time": tender.get('closing_date'),
        "article:section": tender.get('category', 'other').title(),
    }

def generate_schema_org_tender(tender: Dict) -> Dict:
    """
    Generate Schema.org JSON-LD structured data for a tender notice.
    Uses GovernmentPermit / OfferCatalog / DemandEvent schema types optimized for Google.
    This enables rich snippets in Google Search results.
    """
    tender_url = get_tender_url(tender)
    org_name = tender.get('organization', 'Government of Sri Lanka')

    schema = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "GovernmentPermit",
                "name": tender.get('title', ''),
                "description": tender.get('description') or f"Procurement notice from {org_name}",
                "url": tender_url,
                "identifier": tender.get('source_id', ''),
                "issuedBy": {
                    "@type": "GovernmentOrganization",
                    "name": org_name,
                    "url": tender.get('source_url'),
                    "areaServed": {"@type": "Country", "name": "Sri Lanka"}
                },
                "validFrom": tender.get('published_date'),
                "validUntil": tender.get('closing_date'),
                "provider": {
                    "@type": "WebSite",
                    "name": SITE_CONFIG['site_name'],
                    "url": SITE_CONFIG['site_url']
                }
            },
            {
                "@type": "Offer",
                "name": tender.get('title', ''),
                "description": tender.get('description') or f"Open bidding opportunity - {tender.get('category', 'procurement')}",
                "category": tender.get('category', 'other').title(),
                "url": tender_url,
                "availability": "https://schema.org/InStock" if tender.get('status') == 'open' else "https://schema.org/Discontinued",
                "availabilityStarts": tender.get('published_date'),
                "availabilityEnds": tender.get('closing_date'),
                "priceCurrency": tender.get('currency', 'LKR'),
                "seller": {
                    "@type": "Organization",
                    "name": org_name
                },
                "offeredBy": {
                    "@type": "WebSite",
                    "name": SITE_CONFIG['site_name']
                }
            }
        ]
    }

    # Add price if available
    if tender.get('estimated_value'):
        for item in schema['@graph']:
            if item['@type'] == 'Offer':
                item['price'] = tender['estimated_value']

    # Add breadcrumb schema
    breadcrumbs = {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE_CONFIG['site_url']},
            {"@type": "ListItem", "position": 2, "name": f"{tender.get('category','').title()} Tenders", "item": get_category_url(tender.get('category','other'))},
            {"@type": "ListItem", "position": 3, "name": tender.get('title', '')[:60], "item": tender_url},
        ]
    }
    schema['@graph'].append(breadcrumbs)

    return schema

def generate_organization_schema() -> Dict:
    """Schema.org Organization / Website data for homepage"""
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": SITE_CONFIG['site_name'],
        "url": SITE_CONFIG['site_url'],
        "description": SITE_CONFIG['site_description'],
        "potentialAction": {
            "@type": "SearchAction",
            "target": f"{SITE_CONFIG['site_url']}/search?q={{search_term_string}}",
            "query-input": "required name=search_term_string"
        },
        "publisher": {
            "@type": "Organization",
            "name": SITE_CONFIG['site_name'],
            "url": SITE_CONFIG['site_url'],
            "logo": {"@type": "ImageObject", "url": f"{SITE_CONFIG['site_url']}{SITE_CONFIG['logo_url']}"}
        }
    }

def generate_sitemap() -> str:
    """Generate XML sitemap for search engines"""
    urls = []

    # Homepage
    urls.append({
        "loc": SITE_CONFIG['site_url'],
        "lastmod": date.today().isoformat(),
        "changefreq": "hourly",
        "priority": 1.0
    })

    # Category pages
    for cat, seo in CATEGORY_SEO.items():
        urls.append({
            "loc": get_category_url(cat),
            "lastmod": date.today().isoformat(),
            "changefreq": seo['changefreq'],
            "priority": seo['priority']
        })

    # Tender detail pages (up to last 1000 tenders to keep sitemap reasonable)
    tenders = get_tenders(filters={"status": "open"}, limit=1000, page=1)
    for tender in tenders['results']:
        urls.append({
            "loc": get_tender_url(tender),
            "lastmod": (tender.get('published_date') or tender.get('scraped_at', date.today().isoformat()))[:10],
            "changefreq": "weekly",
            "priority": 0.6
        })

    # Build XML
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for u in urls:
        xml += '  <url>\n'
        xml += f'    <loc>{u["loc"]}</loc>\n'
        xml += f'    <lastmod>{u["lastmod"]}</lastmod>\n'
        xml += f'    <changefreq>{u["changefreq"]}</changefreq>\n'
        xml += f'    <priority>{u["priority"]}</priority>\n'
        xml += '  </url>\n'
    xml += '</urlset>'

    # Save to file for static serving
    sitemap_path = BASE_DIR / "sitemap.xml"
    with open(sitemap_path, 'w') as f:
        f.write(xml)
    return xml

def generate_robots_txt() -> str:
    """Generate robots.txt"""
    return f"""User-agent: *
Allow: /
Disallow: /api/
Disallow: /admin/
Disallow: /private/

Sitemap: {SITE_CONFIG['site_url']}/sitemap.xml
"""

def generate_rss_feed(limit: int = 50) -> str:
    """Generate RSS 2.0 feed of latest tenders for SEO + subscriber use"""
    tenders = get_tenders(filters={"status": "open"}, limit=limit, page=1)

    rss = '<?xml version="1.0" encoding="UTF-8"?>\n'
    rss += f'<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
    rss += '<channel>\n'
    rss += f'  <title>{SITE_CONFIG["site_name"]} - Latest Tenders</title>\n'
    rss += f'  <link>{SITE_CONFIG["site_url"]}</link>\n'
    rss += f'  <description>{SITE_CONFIG["site_description"]}</description>\n'
    rss += f'  <language>en-lk</language>\n'
    rss += f'  <lastBuildDate>{datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")}</lastBuildDate>\n'
    rss += f'  <atom:link href="{SITE_CONFIG["site_url"]}/rss" rel="self" type="application/rss+xml"/>\n'

    for tender in tenders['results']:
        url = get_tender_url(tender)
        pub_date = tender.get('published_date') or tender.get('scraped_at', '')
        title = tender.get('title', '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        desc = (tender.get('description') or f"Category: {tender.get('category','')} | Organization: {tender.get('organization','')} | Closing: {tender.get('closing_date','')}")
        desc = desc.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        docs = tender.get('document_links', [])
        if docs:
            desc += f"&lt;br&gt;&lt;br&gt;&lt;strong&gt;Documents:&lt;/strong&gt; "
            for d in docs:
                desc += f'&lt;a href="{d}"&gt;Download Document&lt;/a&gt; '

        rss += '  <item>\n'
        rss += f'    <title>{title}</title>\n'
        rss += f'    <link>{url}</link>\n'
        rss += f'    <guid isPermaLink="true">{url}</guid>\n'
        rss += f'    <description>{desc}</description>\n'
        rss += f'    <category>{tender.get("category","other").title()}</category>\n'
        if pub_date:
            try:
                from email.utils import formatdate
                import time
                ts = datetime.fromisoformat(pub_date.replace('Z','+00:00'))
                rss += f'    <pubDate>{formatdate(time.mktime(ts.timetuple()))}</pubDate>\n'
            except:
                pass
        rss += '  </item>\n'

    rss += '</channel>\n</rss>'

    # Save static copy
    rss_path = BASE_DIR / "rss.xml"
    with open(rss_path, 'w') as f:
        f.write(rss)
    return rss

def get_homepage_seo() -> Dict:
    """Get SEO metadata for homepage"""
    return {
        "title": "Sri Lanka Tenders | Daily Updated Government & Private Procurement Notices",
        "description": SITE_CONFIG['site_description'],
        "keywords": SITE_CONFIG['site_keywords'],
        "canonical": SITE_CONFIG['site_url'],
        "og:title": SITE_CONFIG['site_name'],
        "og:description": SITE_CONFIG['site_description'],
        "og:type": "website",
        "og:url": SITE_CONFIG['site_url'],
        "schema": generate_organization_schema(),
        "robots": "index, follow"
    }

def get_category_seo(category: str) -> Dict:
    """Get SEO metadata for a category page"""
    cat = category.lower()
    seo = CATEGORY_SEO.get(cat, CATEGORY_SEO['other'])
    return {
        "title": seo['title'],
        "description": seo['description'],
        "keywords": seo['keywords'],
        "canonical": get_category_url(cat),
        "og:title": seo['title'],
        "og:description": seo['description'],
        "og:type": "website",
        "og:url": get_category_url(cat),
        "robots": "index, follow"
    }
