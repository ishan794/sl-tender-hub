# Sri Lanka Tender Hub - Advanced SEO Architecture

Comprehensive search engine optimization (SEO) architecture designed to maximize organic visibility and Google indexing for Sri Lankan public and private procurement opportunities.

## System Features

| SEO Feature | Description | Status |
|---|---|---|
| Per-Page Metadata | Dynamic meta titles and descriptions tailored per notice | Active |
| Category Keywords | Category-specific keyword targeting for high-volume searches | Active |
| Canonical URLs | Canonical link tags across all notice and category routes | Active |
| Open Graph Protocol | Facebook, LinkedIn, and messaging link previews | Active |
| Twitter Cards | Large summary card previews | Active |
| Schema.org JSON-LD | Structured data markup for Google Rich Snippets | Active |
| BreadcrumbList | Structured breadcrumb hierarchy | Active |
| XML Sitemap | Automated sitemap generation (`/sitemap.xml`) | Active |
| Robots Directives | Crawler configuration directives (`/robots.txt`) | Active |
| RSS 2.0 Feed | Syndication feed for procurement feeds (`/rss.xml`) | Active |
| Clean Slugs | SEO-friendly URL slugs derived from tender titles | Active |
| Multilingual Tags | `hreflang` alternates for English, Sinhala, and Tamil | Active |

## Setup & Configuration

1. **Configure Production Domain:**
```bash
cd /opt/tenderhub/sl-tender-hub
python setup_seo.py https://tenderhub.lk
```
This updates sitemap generation, canonical bases, and XML outputs to match the production domain.

2. **Frontend Metadata Integration (Next.js):**

### Notice Detail Page
```tsx
export async function generateMetadata({ params }: { params: { slug: string } }) {
  const tender = await getTenderBySlug(params.slug);
  return {
    title: `${tender.title} | TenderHub Sri Lanka`,
    description: tender.summary || `Official procurement notice: ${tender.reference}`,
    alternates: {
      canonical: `https://tenderhub.lk/tenders/${tender.slug}`,
    },
    openGraph: {
      title: tender.title,
      description: tender.summary,
      url: `https://tenderhub.lk/tenders/${tender.slug}`,
      siteName: 'TenderHub Sri Lanka',
    },
  };
}
```

3. **Search Engine Verification:**
   - Submit sitemap endpoint `https://tenderhub.lk/sitemap.xml` to Google Search Console and Bing Webmaster Tools.

## Target Keywords

Primary Search Phrases:
- `sri lanka tenders`
- `government tenders sri lanka`
- `ceb tenders`
- `construction tenders sri lanka`
- `procurement notices sri lanka`

Sector-Level Keywords:
- `Ceylon Electricity Board procurement`
- `Water Supply and Drainage Board tenders`
- `Mahaweli Authority bids`
- `ICT and software tenders Sri Lanka`
- `Ministry of Health medical equipment procurement`
- `Road Development Authority highway contracts`

## Architecture Performance
- Lightweight index caching (<50MB memory footprint).
- Fast generation with zero database bottlenecks.

