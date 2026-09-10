#!/usr/bin/env python3
"""
SEO Setup Helper - Run this once to configure your domain for SEO.
Usage: python setup_seo.py https://yourdomain.com
"""
import sys
import re

def setup_domain(domain: str):
    if not domain.startswith('http'):
        domain = 'https://' + domain
    domain = domain.rstrip('/')

    # Update SITE_CONFIG in seo.py
    with open('seo.py', 'r') as f:
        content = f.read()

    content = re.sub(
        r'"site_url":\s*os\.getenv\("SITE_URL",\s*"[^"]*"\)',
        f'"site_url": os.getenv("SITE_URL", "{domain}")',
        content
    )

    with open('seo.py', 'w') as f:
        f.write(content)

    print(f"✅ Site URL set to: {domain}")
    print(f"📝 Next steps:")
    print(f"   1. Submit {domain}/sitemap.xml to Google Search Console")
    print(f"   2. Add Google Analytics / Search Console verification tag")
    print(f"   3. Update your frontend to call /api/seo/* endpoints for meta tags")
    print(f"   4. Restart API server to apply changes")
    print()
    print(f"SEO URLs ready:")
    print(f"   Homepage:  {domain}/")
    print(f"   Sitemap:   {domain}/sitemap.xml")
    print(f"   RSS Feed:  {domain}/rss")
    print(f"   Robots:    {domain}/robots.txt")
    print(f"   API Docs:  {domain}/docs")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python setup_seo.py https://yourdomain.com")
        print("Example: python setup_seo.py https://sltenders.lk")
        sys.exit(1)
    setup_domain(sys.argv[1])
