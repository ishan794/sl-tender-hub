#!/usr/bin/env python3
"""
REST API Server for Sri Lanka Tender Hub
Lightweight FastAPI server (<50MB idle RAM, no heavy dependencies)
Connect your web application to this API base URL.
Includes FULL ADVANCED SEO support.
"""
import sys

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

try:
    from fastapi import FastAPI, HTTPException, Query, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, Response, HTMLResponse, PlainTextResponse
    from fastapi.staticfiles import StaticFiles
except ImportError:
    print("FastAPI not installed. Install API dependencies with: pip install fastapi uvicorn")
    exit(1)


from typing import Optional, List
import base64
import hashlib
import os
import re
from datetime import date, datetime
from database import init_db, get_tenders, get_statistics, get_tender_sources, mark_expired_tenders, insert_submitted_tender
from config import UPLOAD_DIR
from sources import ALL_SOURCES, get_source
from pydantic import BaseModel
from seo import (
    generate_sitemap, generate_robots_txt, generate_rss_feed,
    get_homepage_seo, get_category_seo, get_tender_url, get_category_url,
    generate_meta_tags, generate_schema_org_tender, SITE_CONFIG, CATEGORY_SEO
)

app = FastAPI(
    title="Sri Lanka Tender Hub API",
    description="Local/self-hosted aggregated tender data API for Sri Lanka government/private tenders - with full SEO support",
    version="2.0.0",
    docs_url="/docs",
    openapi_tags=[
        {"name": "Tenders", "description": "Tender search, filtering and details"},
        {"name": "SEO", "description": "Advanced SEO endpoints for frontend integration"},
        {"name": "Feeds", "description": "RSS/Sitemap feeds for search engines and users"},
        {"name": "Dashboard", "description": "Statistics and overview data"},
        {"name": "Sources", "description": "Source website registry"},
        {"name": "Status", "description": "Health and status checks"},
    ]
)

# Enable CORS for your web application (restrict this to your domain in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with your web app domain in production: e.g. ["https://yourdomain.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded notice images (manual submissions)
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

class TenderResponse(BaseModel):
    total: int
    page: int
    total_pages: int
    limit: int
    results: List[dict]

# ==========================================
# MANUAL TENDER SUBMISSION (POST)
# ==========================================
class SubmitTender(BaseModel):
    title: str                                    # notice title (required)
    organization: Optional[str] = None            # Company / issuing authority
    category: Optional[str] = "other"             # construction/goods/services/IT/... or free text
    source: Optional[str] = None                  # where it was published, e.g. "Sunday Observer"
    location: Optional[str] = None                # e.g. "Western Province, Gampaha"
    published_date: Optional[str] = None          # YYYY-MM-DD
    closing_date: Optional[str] = None            # YYYY-MM-DD
    description: Optional[str] = None
    notice_image: Optional[str] = None            # image URL or base64 data-URL of the notice

def _slugify(value: str) -> str:
    """Turn a source name into a safe source_site_id, e.g. 'Sunday Observer' -> 'sunday_observer'."""
    slug = re.sub(r'[^a-zA-Z0-9]+', '_', (value or '').lower()).strip('_')
    return slug or 'user_submission'

def _parse_date_str(value: Optional[str]):
    """Parse a date string into a date object. Accepts YYYY-MM-DD and DD/MM/YYYY style."""
    if not value:
        return None
    value = value.strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y', '%d %B %Y', '%d %b %Y'):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None

def _save_notice_image(data_or_url: Optional[str], tender_key: str) -> Optional[str]:
    """Save a notice image. Accepts a URL or a base64 data-URL; returns the stored path/URL."""
    if not data_or_url:
        return None
    data_or_url = data_or_url.strip()
    if data_or_url.startswith(('http://', 'https://')):
        return data_or_url
    m = re.match(r'data:image/([a-zA-Z0-9]+);base64,(.*)', data_or_url, re.DOTALL)
    if m:
        ext = m.group(1).lower()
        if ext == 'jpeg':
            ext = 'jpg'
        filename = f"notice_{tender_key}.{ext}"
        with open(os.path.join(UPLOAD_DIR, filename), 'wb') as f:
            f.write(base64.b64decode(m.group(2)))
        return f"/uploads/{filename}"
    return data_or_url  # unknown format — store as-is

@app.on_event("startup")
def startup():
    init_db()
    # Auto-mark expired tenders as closed on startup
    mark_expired_tenders()
    # Pre-generate sitemap and RSS on startup
    try:
        generate_sitemap()
        generate_rss_feed()
    except Exception:
        pass

@app.get("/", tags=["Status"])
def root():
    return {
        "name": "Sri Lanka Tender Hub API",
        "version": "2.0.0 - SEO Optimized",
        "status": "running",
        "endpoints": {
            "GET /api/tenders": "Search/list tenders with filters",
            "POST /api/tenders": "Submit a tender notice manually (with notice image)",
            "GET /api/tenders/{master_group_id}": "Get single tender details",
            "GET /api/tenders/{master_group_id}/seo": "Get full SEO meta tags + JSON-LD schema for a tender page",
            "GET /api/seo/home": "Homepage SEO metadata",
            "GET /api/seo/category/{category}": "Category page SEO metadata",
            "GET /sitemap.xml": "XML Sitemap for search engines",
            "GET /robots.txt": "Robots.txt for crawlers",
            "GET /rss": "RSS 2.0 feed of latest tenders",
            "GET /api/statistics": "Get summary statistics",
            "GET /api/sources": "List all registered tender sources",
            "GET /api/health": "Health check for monitoring",
        }
    }

@app.get("/api/health", tags=["Status"])
def health_check():
    return {"status": "healthy", "service": "sl-tender-hub", "version": "2.0.0"}

@app.get("/api/tenders", response_model=TenderResponse, tags=["Tenders"])
def list_tenders(
    search: Optional[str] = Query(None, description="Search keyword in title, description, organization"),
    category: Optional[str] = Query(None, description="Filter by category: construction/goods/services/IT/health/education/agriculture/energy/transport/other"),
    status: str = Query("open", description="Filter by status: open/closed/awarded/cancelled/all"),
    organization: Optional[str] = Query(None, description="Filter by organization name"),
    source_site_id: Optional[str] = Query(None, description="Filter by source website ID"),
    published_after: Optional[str] = Query(None, description="Only show tenders published after date (YYYY-MM-DD)"),
    closing_after: Optional[str] = Query(None, description="Only show tenders closing after date (YYYY-MM-DD)"),
    closing_before: Optional[str] = Query(None, description="Only show tenders closing before date (YYYY-MM-DD)"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page (max 100)")
):
    """
    List and search tenders with full filtering and pagination.
    Each result includes a `seo_url` field that you should use as the canonical URL on your frontend.
    """
    filters = {}
    if status.lower() != "all":
        filters['status'] = status
    if category:
        filters['category'] = category.lower()
    if organization:
        filters['organization'] = organization
    if source_site_id:
        filters['source_site_id'] = source_site_id
    if search:
        filters['search'] = search
    if published_after:
        filters['published_after'] = published_after
    if closing_after:
        filters['closing_after'] = closing_after
    if closing_before:
        filters['closing_before'] = closing_before

    result = get_tenders(filters=filters, limit=limit, page=page)
    # Add SEO URL to each result
    for t in result['results']:
        t['seo_url'] = get_tender_url(t)
        t['seo_slug'] = get_tender_url(t).split('/')[-1]
        t['category_url'] = get_category_url(t.get('category', 'other'))
    return result

@app.post("/api/tenders", tags=["Tenders"], status_code=201, summary="Submit a tender notice manually")
def submit_tender(payload: SubmitTender):
    """
    Submit a tender notice manually (e.g. a newspaper ad from Sunday Observer).
    Supports all the fields shown on a notice: Company, Category, Source,
    Location, Published Date, Closing Date + a notice image (URL or base64).

    Dates are validated: published date cannot be after closing date.
    A tender whose closing date has already passed is stored as 'closed'.
    """
    title = (payload.title or '').strip()
    if len(title) < 10:
        raise HTTPException(status_code=422, detail="Title is required (at least 10 characters)")

    published = _parse_date_str(payload.published_date)
    closing = _parse_date_str(payload.closing_date)

    # Reject impossible dates (e.g. published 30 Sep 2026 but closing 7 Sep 2026)
    if published and closing and published > closing:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid dates: published date ({published.isoformat()}) cannot be after closing date ({closing.isoformat()})"
        )

    # Auto-mark as closed if the closing date has already passed
    status = "open"
    today = date.today()
    if closing and closing < today:
        status = "closed"

    source_name = (payload.source or 'User Submission').strip()
    source_site_id = _slugify(source_name)
    source_id = f"submit_{hashlib.md5((title + (payload.published_date or '') + (payload.closing_date or '')).encode()).hexdigest()[:10]}"

    notice_image = _save_notice_image(payload.notice_image, source_id)

    tender = {
        "source_site_id": source_site_id,
        "source_id": source_id,
        "title": title,
        "organization": payload.organization,
        "category": (payload.category or 'other').strip().lower(),
        "published_date": published.isoformat() if published else None,
        "closing_date": closing.isoformat() if closing else None,
        "location": payload.location,
        "description": payload.description,
        "document_links": [],
        "source_url": f"user-submitted://{source_site_id}/{source_id}",
        "status": status,
        "notice_image": notice_image,
        "source_name": source_name,
    }

    master_group_id = insert_submitted_tender(tender)
    if not master_group_id:
        raise HTTPException(status_code=409, detail="This tender already exists")

    return {
        "created": True,
        "master_group_id": master_group_id,
        "source_id": source_id,
        "status": status,
        "notice_image": notice_image,
    }

@app.get("/api/tenders/{master_group_id}", tags=["Tenders"])
def get_tender_detail(master_group_id: str):
    """Get full details of a single tender by its master group ID"""
    result = get_tenders(filters=None, limit=10000, page=1, include_duplicates=True)
    for tender in result['results']:
        if tender['master_group_id'] == master_group_id:
            tender['all_sources'] = get_tender_sources(master_group_id)
            tender['seo_url'] = get_tender_url(tender)
            tender['seo'] = generate_meta_tags(tender)
            tender['schema_org'] = generate_schema_org_tender(tender)
            return tender
    raise HTTPException(status_code=404, detail="Tender not found")

@app.get("/api/tenders/{master_group_id}/sources", tags=["Tenders"])
def get_tender_all_sources(master_group_id: str):
    """Get all websites/sources where this particular tender is published (cross-site listings)"""
    sources = get_tender_sources(master_group_id)
    if not sources:
        raise HTTPException(status_code=404, detail="Tender not found")
    return {"master_group_id": master_group_id, "sources": sources}

# ==========================================
# SEO ENDPOINTS
# ==========================================
@app.get("/api/seo/home", tags=["SEO"], summary="Get homepage SEO metadata")
def seo_home():
    """
    Returns all SEO data for the homepage:
    - Meta title, description, keywords
    - Open Graph tags
    - Twitter Card tags
    - Schema.org JSON-LD structured data
    - Canonical URL
    Use these directly in your frontend <head> section.
    """
    return get_homepage_seo()

@app.get("/api/seo/category/{category}", tags=["SEO"], summary="Get category page SEO metadata")
def seo_category(category: str):
    """
    Returns all SEO data for a category listing page.
    Optimized for category-level search ranking.
    """
    return get_category_seo(category)

@app.get("/api/tenders/{master_group_id}/seo", tags=["SEO"], summary="Get tender detail page SEO metadata")
def seo_tender(master_group_id: str):
    """
    Returns FULL SEO data for a tender detail page:
    - Optimized meta title/description/keywords
    - Full Open Graph + Twitter Card tags
    - Schema.org GovernmentPermit + Offer + BreadcrumbList JSON-LD
    - Canonical URL
    - Robots directives
    - Article published/expiration dates

    Render the JSON-LD schema in your frontend <script type="application/ld+json"> tag
    to get Google rich snippets in search results.
    """
    result = get_tenders(filters=None, limit=10000, page=1, include_duplicates=True)
    for tender in result['results']:
        if tender['master_group_id'] == master_group_id:
            return {
                "meta": generate_meta_tags(tender),
                "schema_org": generate_schema_org_tender(tender),
                "canonical_url": get_tender_url(tender),
                "slug": get_tender_url(tender).split('/')[-1],
                "hreflang": [
                    {"lang": "en", "url": get_tender_url(tender)},
                    {"lang": "si", "url": f"{get_tender_url(tender)}/si"},
                    {"lang": "ta", "url": f"{get_tender_url(tender)}/ta"},
                ]
            }
    raise HTTPException(status_code=404, detail="Tender not found")

@app.get("/api/seo/categories", tags=["SEO"], summary="Get SEO metadata for all categories")
def seo_all_categories():
    """Get SEO metadata for every category in one call (useful for navigation/sitemap generation)"""
    results = {}
    for cat, seo in CATEGORY_SEO.items():
        results[cat] = {
            **seo,
            "url": get_category_url(cat),
            "tender_count": get_statistics()['by_category'].get(cat, 0)
        }
    return results

# ==========================================
# FEED / SEARCH ENGINE ENDPOINTS
# ==========================================
@app.get("/sitemap.xml", response_class=Response, tags=["Feeds"], summary="XML Sitemap for search engines")
def sitemap():
    """Generate fresh XML sitemap (auto-refreshed). Submit this URL to Google Search Console."""
    xml = generate_sitemap()
    return Response(content=xml, media_type="application/xml")

@app.get("/robots.txt", response_class=PlainTextResponse, tags=["Feeds"], summary="Robots.txt")
def robots():
    """Auto-generated robots.txt that points to your sitemap"""
    return PlainTextResponse(content=generate_robots_txt())

@app.get("/rss", response_class=Response, tags=["Feeds"], summary="RSS 2.0 feed of latest tenders")
def rss_feed():
    """RSS 2.0 feed of latest open tenders. Users/aggregators can subscribe to this."""
    xml = generate_rss_feed(limit=100)
    return Response(content=xml, media_type="application/rss+xml")

@app.get("/feed", response_class=Response, tags=["Feeds"], summary="Alias for RSS feed")
def feed_alias():
    return rss_feed()

# ==========================================
# Dashboard
# ==========================================
@app.get("/api/statistics", tags=["Dashboard"])
def statistics():
    """Get aggregate statistics for dashboard display"""
    stats = get_statistics()
    stats['seo'] = {
        "site_name": SITE_CONFIG['site_name'],
        "site_url": SITE_CONFIG['site_url'],
        "total_indexed_pages": stats['total_unique_tenders'] + len(CATEGORY_SEO) + 1,
        "sitemap_url": f"{SITE_CONFIG['site_url']}/sitemap.xml",
        "rss_url": f"{SITE_CONFIG['site_url']}/rss",
    }
    return stats

@app.get("/api/sources", tags=["Sources"])
def list_sources(
    priority: Optional[int] = Query(None, description="Filter by priority level 1/2/3"),
    type: Optional[str] = Query(None, description="Filter by source type: government/soe/ministry/municipal/university/private_aggregator/statutory")
):
    """List all registered tender sources"""
    sources = ALL_SOURCES
    if priority:
        sources = [s for s in sources if s.priority == priority]
    if type:
        sources = [s for s in sources if s.type == type]
    return {
        "total_sources": len(sources),
        "sources": [
            {
                "id": s.id,
                "name": s.name,
                "base_url": s.base_url,
                "tender_url": s.tender_url,
                "type": s.type,
                "priority": s.priority,
                "scraper_strategy": s.scraper_strategy
            } for s in sources
        ]
    }

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Sri Lanka Tender Hub API + SEO server on http://0.0.0.0:8000")
    print("📊 API Documentation: http://localhost:8000/docs")
    print("🗺️  Sitemap: http://localhost:8000/sitemap.xml")
    print("📡 RSS Feed: http://localhost:8000/rss")
    print("🤖 Robots.txt: http://localhost:8000/robots.txt")
    uvicorn.run(app, host="0.0.0.0", port=8000, workers=1, log_level="info")
