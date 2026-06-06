#!/usr/bin/env python3
"""
Automated Plumber Directory Factory

One command:
  python pipeline.py
  
Builds a directory site for any city + niche using Google Places API.
Requires: GOOGLE_MAPS_API_KEY in .env (free from https://console.cloud.google.com)

SEO features:
  - JSON-LD schema (LocalBusiness, WebSite, FAQ, BlogPosting, BreadcrumbList)
  - Open Graph / Twitter Card meta tags
  - Auto-generated sitemap.xml
  - robots.txt
  - Rich page titles and meta descriptions
"""

import json, os, re, subprocess, sys, time
from pathlib import Path

# ─── CONFIG ─────────────────────────────────────────────────────────────
CITY = "Tucson"
STATE = "AZ"
NICHE = "Plumber"
DOMAIN_NAME = "best-plumbers-tucson"
BRAND = "Tucson Plumbing Pros"
CONTACT_EMAIL = "gloaminggallery@gmail.com"
URL_BASE = "https://ramzihech.github.io/TucsonPlumbingPros/"

# Google Search Console verification — leave empty to omit
GSC_VERIFICATION = ""

# Google Analytics 4 measurement ID — leave empty to omit (format: G-XXXXXXXXXX)
GA4_ID = ""

# County / region name for SEO copy
COUNTY = "Pima County"
REGION_FEATURES = "hard water buildup, monsoon drainage, slab foundations that complicate repiping, and older copper pipe corrosion"
REGION_LANDMARK = "Davis-Monthan Air Force Base"

# Output files
OUT_DIR = Path("C:/Users/Ramzi/web_build")
DATA_FILE = OUT_DIR / "listings.json"
INDEX_FILE = OUT_DIR / "index.html"
SITEMAP_FILE = OUT_DIR / "sitemap.xml"
ROBOTS_FILE = OUT_DIR / "robots.txt"
BLOG_DIR = OUT_DIR / "blog"

# Known blog posts (title, filename, excerpt)
BLOG_POSTS = [
    ("Copper Vs PEX: Which Pipe Is Best for Tucson Homes?",
     "copper-vs-pex.html",
     "Compare copper vs PEX pipes for Tucson homes. Cost, durability, hard water resistance, and what Tucson plumbers recommend for Arizona's climate."),
    ("Emergency Vs Scheduled Plumbing: When to Call in Tucson",
     "emergency-vs-scheduled.html",
     "Know when to call for emergency vs scheduled plumbing in Tucson. Monsoon season burst pipes, slab leaks, and Tucson's unique plumbing challenges."),
    ("Hard Water Damage in Tucson: Signs, Prevention & Solutions",
     "hard-water-damage.html",
     "How Tucson's hard water damages pipes, water heaters, and fixtures. Signs to watch for, prevention tips, and when to call a Tucson plumber."),
    ("Monsoon Plumbing: Preparing Your Tucson Home for Rain Season",
     "monsoon-plumbing.html",
     "Arizona monsoon plumbing prep for Tucson homeowners. Drainage, slab foundation risks, gutter maintenance, and emergency plumber readiness."),
    ("Water Heater Maintenance in Tucson: Extend Your System's Life",
     "water-heater-maintenance.html",
     "How to extend your water heater's life in Tucson. Hard water sediment, tank vs tankless, annual maintenance tips, and local plumber recommendations."),
]

FAQ_DATA = [
    {
        "q": "How much does a plumber cost in {city}?",
        "a": "Small repairs typically range from $150-400. Larger projects like water heater replacement run $800-2,500. Major repiping can cost $3,000-8,000. Always get a written estimate before work begins."
    },
    {
        "q": "Are the plumbers on this site licensed?",
        "a": "Yes. All plumbers listed are licensed and insured in the state of Arizona. We recommend verifying their ROC license number before hiring."
    },
    {
        "q": "Do {city} plumbers offer emergency service?",
        "a": "Many do. Plumbers serving {landmark} and the surrounding area often provide 24/7 emergency call-out for burst pipes, sewer backups, and other urgent issues."
    },
    {
        "q": "How do I know if I need a plumber or a handyman?",
        "a": "For minor tasks like replacing a faucet, a handyman may suffice. For work involving water lines, sewer lines, water heaters, or gas lines, always hire a licensed plumber."
    },
    {
        "q": "How quickly can I get a plumber in {city}?",
        "a": "Most local plumbers offer same-day or next-day service. Emergency services arrive within 1-2 hours. Call times may vary during monsoon season or holidays."
    },
]


# ─── STEP 1: Fetch data from Google Places API ──────────────────────────

def load_api_key():
    """Load Google Maps API key from .env"""
    env_path = Path(os.environ.get('HERMES_HOME', str(Path.home() / 'AppData' / 'Local' / 'hermes'))) / '.env'
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith('GOOGLE_MAPS_API_KEY=') or line.startswith('GOOGLE_API_KEY='):
                    return line.split('=', 1)[1].strip().strip('"').strip("'")
    return os.environ.get('GOOGLE_MAPS_API_KEY') or os.environ.get('GOOGLE_API_KEY', '')


def fetch_plumbers_via_places_api(api_key):
    """Use Google Places API - Text Search to find plumbers."""
    import requests
    
    businesses = []
    query = f"{NICHE} in {CITY}, {STATE}"
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {"query": query, "key": api_key, "type": f"{NICHE.lower()}_plumber"}
    
    resp = requests.get(url, params=params, timeout=15)
    data = resp.json()
    
    if data.get("status") != "OK":
        print(f"API Error: {data.get('status')} - {data.get('error_message', '')}")
        return []
    
    for place in data.get("results", []):
        biz = {
            "name": place.get("name", ""),
            "address": place.get("formatted_address", ""),
            "rating": place.get("rating", 0),
            "total_ratings": place.get("user_ratings_total", 0),
            "place_id": place.get("place_id", ""),
            "types": place.get("types", []),
        }
        detail_url = "https://maps.googleapis.com/maps/api/place/details/json"
        detail_params = {
            "place_id": biz["place_id"],
            "fields": "formatted_phone_number,website,opening_hours",
            "key": api_key,
        }
        time.sleep(0.1)
        det_resp = requests.get(detail_url, params=detail_params, timeout=10)
        det_data = det_resp.json()
        result = det_data.get("result", {})
        biz["phone"] = result.get("formatted_phone_number", "")
        biz["website"] = result.get("website", "")
        businesses.append(biz)
    
    return businesses


# ─── STEP 2: Build HTML site ────────────────────────────────────────────

def esc(s):
    """Escape string for safe embedding in f-string-style JavaScript."""
    return s.replace('\\', '\\\\').replace("'", "\\'").replace('\n', ' ')


def esc_json(s):
    """Escape string for safe embedding in JSON."""
    return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ').replace('\r', '')


def schema_website():
    """Generate WebSite schema."""
    return f'''"@context":"https://schema.org","@type":"WebSite","name":"{esc_json(BRAND)}","url":"{esc_json(URL_BASE)}","description":"{esc_json(f'Find the best {NICHE.lower()}s in {CITY}, {STATE}. Top-rated, licensed, and insured plumbing services.')}"'''


def schema_localbusiness(b):
    """Generate LocalBusiness schema for a plumber."""
    name = esc_json(b.get("name", ""))
    addr = esc_json(b.get("address", f"{CITY}, {STATE}"))
    phone = esc_json(b.get("phone", ""))
    rating = b.get("rating", 0)
    reviews = b.get("total_ratings", 0)
    website = esc_json(b.get("website", ""))
    
    parts = [f'"@type":"LocalBusiness","name":"{name}","address":"{addr}"']
    if phone:
        parts.append(f'"telephone":"{phone}"')
    if rating and reviews:
        parts.append(f'"aggregateRating":{{"@type":"AggregateRating","ratingValue":{rating},"reviewCount":{reviews}}}')
    if website:
        parts.append(f'"url":"{website}"')
    return '{' + ','.join(parts) + '}'


def schema_faq(city_only, landmark):
    """Generate FAQPage schema."""
    items = ""
    for faq in FAQ_DATA:
        q = esc_json(faq["q"].format(city=city_only, landmark=landmark))
        a = esc_json(faq["a"].format(city=city_only, landmark=landmark))
        items += f'{{"@type":"Question","name":"{q}","acceptedAnswer":{{"@type":"Answer","text":"{a}"}}}},'
    return f'{{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[{items.rstrip(",")}]}}'


def schema_breadcrumb():
    """Generate BreadcrumbList schema."""
    return f'{{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{{"@type":"ListItem","position":1,"name":"Home","item":"{esc_json(URL_BASE)}"}}]}}'


def schema_blog_posts():
    """Generate BlogPosting schemas for blog posts."""
    items = ""
    for title, filename, excerpt in BLOG_POSTS:
        url = f"{URL_BASE}blog/{filename}"
        etitle = esc_json(title)
        eexcerpt = esc_json(excerpt)
        items += f'{{"@type":"BlogPosting","headline":"{etitle}","url":"{esc_json(url)}","description":"{eexcerpt}"}},'
    return items.rstrip(",")


def build_og_tags(page_title, page_desc, url):
    """Build Open Graph and Twitter Card meta tags."""
    return f'''
<meta property="og:type" content="website">
<meta property="og:title" content="{esc_json(page_title)}">
<meta property="og:description" content="{esc_json(page_desc)}">
<meta property="og:url" content="{esc_json(url)}">
<meta property="og:site_name" content="{esc_json(BRAND)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc_json(page_title)}">
<meta name="twitter:description" content="{esc_json(page_desc)}">'''


def build_ga_tag():
    """Build Google Analytics 4 script if GA4_ID is set."""
    if not GA4_ID:
        return ""
    return f'''
<script async src="https://www.googletagmanager.com/gtag/js?id={GA4_ID}"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','{GA4_ID}');</script>'''


def build_sitemap():
    """Generate sitemap.xml content."""
    today = time.strftime('%Y-%m-%d')
    urls = [
        (URL_BASE, today, "0.9", "daily"),
    ]
    for title, filename, excerpt in BLOG_POSTS:
        urls.append((f"{URL_BASE}blog/{filename}", today, "0.7", "weekly"))
    
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for loc, lastmod, priority, changefreq in urls:
        xml += f'  <url><loc>{esc_json(loc)}</loc><lastmod>{lastmod}</lastmod><changefreq>{changefreq}</changefreq><priority>{priority}</priority></url>\n'
    xml += '</urlset>'
    return xml


def build_site(businesses):
    """Generate a premium directory site with client-side search/filter/sort."""
    
    total = len(businesses)
    avg_rating = round(sum(float(b.get("rating", 0) or 0) for b in businesses) / total, 1) if total else 0

    # Sort by rating desc
    sorted_biz = sorted(businesses, key=lambda b: float(b.get("rating", 0) or 0), reverse=True)

    # Build JS data
    rows = []
    featured_count = 0
    for b in sorted_biz:
        rating = float(b.get("rating", 0) or 0)
        is_featured = rating >= 4.5 and featured_count < 3
        if is_featured:
            featured_count += 1
        name = esc(b.get("name", ""))
        addr = esc(b.get("address", f"{CITY}, {STATE}"))
        phone = esc(b.get("phone", ""))
        website = esc(b.get("website", ""))
        reviews = b.get("total_ratings", 0)
        featured = "true" if is_featured else "false"
        rows.append(f"{{name:'{name}',addr:'{addr}',rating:{rating},reviews:{reviews},phone:'{phone}',website:'{website}',featured:{featured}}}")

    js_data = "[" + ",".join(rows) + "]"

    # Build blog cards
    blog_cards = ""
    for title, filename, excerpt in BLOG_POSTS:
        etitle = esc(title)
        eexcerpt = esc(excerpt)
        blog_cards += f"""
            <a href=\"blog/{filename}\" class=\"blog-card\">
                <h3>{etitle}</h3>
                <p>{eexcerpt}</p>
                <span class=\"blog-read\">Read More &#8594;</span>
            </a>"""

    city_state = f"{CITY}, {STATE}"
    city_only = CITY
    lower = NICHE.lower()
    page_title = f"Best {NICHE}s in {city_state} | {BRAND}"
    # Rich meta description with local keywords
    page_desc = (f"Find the best {lower}s in {city_state}. "
                 f"Top-rated, licensed & insured {lower} services near {REGION_LANDMARK}. "
                 f"Compare {total} {lower}s with reviews, ratings & phone numbers. "
                 f"24/7 emergency plumbing services available in {COUNTY}.")
    keywords = f"{lower} {city_only}, plumbing {city_only}, {city_only} AZ {lower}, emergency {lower}, {city_only} plumbing company, {lower} near me, {city_only} {lower} 24/7"

    # Build JSON-LD schema
    website_schema = "{" + schema_website() + "}"
    faq_schema = schema_faq(city_only, REGION_LANDMARK)
    breadcrumb_schema = schema_breadcrumb()
    
    # Build per-plumber LocalBusiness schemas
    biz_schemas = []
    for b in sorted_biz:
        biz_schemas.append(schema_localbusiness(b))
    local_biz_schemas = "[" + ",".join(biz_schemas) + "]"
    
    # Build full schema JSON-LD
    jsonld = f'''<script type="application/ld+json">{website_schema}</script>
<script type="application/ld+json">{faq_schema}</script>
<script type="application/ld+json">{breadcrumb_schema}</script>
<script type="application/ld+json">{{"@context":"https://schema.org","@graph":{local_biz_schemas}}}</script>'''

    # Build the HTML as a Python string
    html_lines = []
    html_lines.append('<!DOCTYPE html>')
    html_lines.append(f'<html lang="en">')
    html_lines.append('<head>')
    html_lines.append('<meta charset="UTF-8">')
    html_lines.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
    html_lines.append(f'<title>{page_title}</title>')
    html_lines.append(f'<meta name="description" content="{esc_json(page_desc)}">')
    html_lines.append(f'<meta name="keywords" content="{esc_json(keywords)}">')
    html_lines.append(f'<link rel="canonical" href="{URL_BASE}">')
    html_lines.append(build_og_tags(page_title, page_desc, URL_BASE))
    if GSC_VERIFICATION:
        html_lines.append(f'<meta name="google-site-verification" content="{GSC_VERIFICATION}">')
    html_lines.append('</head>')
    html_lines.append('<body>')
    html_lines.append(jsonld)
    html_lines.append(build_ga_tag())
    html_lines.append('<style>')
    html_lines.append(self_contained_css())
    html_lines.append('</style>')
    html_lines.append(nav_html(city_only))
    html_lines.append(hero_html(BRAND, NICHE, city_state, total, avg_rating))
    html_lines.append(filters_html(total))
    html_lines.append(listings_section())
    html_lines.append(blog_section(blog_cards))
    html_lines.append(guide_section(NICHE, city_only, lower))
    html_lines.append(faq_section(NICHE, lower, city_only))
    html_lines.append(contact_section(CONTACT_EMAIL, city_only, lower))
    html_lines.append(footer_html(BRAND))
    html_lines.append(f'<script>var allPlumbers = {js_data};')
    html_lines.append(js_code())
    html_lines.append('</script>')
    html_lines.append('</body>')
    html_lines.append('</html>')

    return '\n'.join(html_lines)


def self_contained_css():
    return """*{margin:0;padding:0;box-sizing:border-box}
:root{--ink:#1a1d23;--ink-medium:#4a4f5a;--ink-light:#7c8190;--surface:#fff;--surface-subtle:#f6f7f9;--surface-highlight:#edf0f5;--border:#e1e4ea;--accent:#2563eb;--accent-hover:#1d4ed8;--accent-light:#eef2ff;--green:#16a34a;--green-light:#f0fdf4;--amber:#d97706;--amber-light:#fffbeb;--radius-sm:8px;--radius-md:12px;--radius-lg:16px;--shadow-sm:0 1px 3px rgba(0,0,0,.06);--shadow-md:0 4px 12px rgba(0,0,0,.07);--shadow-lg:0 8px 24px rgba(0,0,0,.09);--transition:200ms cubic-bezier(.4,0,.2,1)}
html{scroll-behavior:smooth}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;color:var(--ink);background:var(--surface-subtle);line-height:1.5;-webkit-font-smoothing:antialiased}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.nav{position:sticky;top:0;z-index:50;background:rgba(255,255,255,.85);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border-bottom:1px solid var(--border)}
.nav-inner{max-width:1120px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;padding:0 24px;height:56px}
.nav-logo{font-weight:700;font-size:1.05rem;color:var(--ink);display:flex;align-items:center;gap:8px}
.nav-logo .mark{color:var(--accent)}
.nav-links{display:flex;gap:24px;align-items:center}
.nav-links a{font-size:.875rem;font-weight:500;color:var(--ink-medium);transition:color var(--transition)}
.nav-links a:hover{color:var(--ink);text-decoration:none}
.hero{background:linear-gradient(135deg,#0f172a 0%,#1e293b 100%);color:#fff;padding:64px 24px 56px;text-align:center}
.hero h1{font-size:clamp(2rem,4vw,3rem);font-weight:700;letter-spacing:-.02em;line-height:1.15;margin-bottom:12px}
.hero p{font-size:1.05rem;color:#94a3b8;max-width:560px;margin:0 auto 28px}
.hero-stats{display:flex;justify-content:center;gap:40px;flex-wrap:wrap}
.hero-stat{text-align:center}
.hero-stat-num{font-size:1.5rem;font-weight:700;color:#fff;display:block}
.hero-stat-label{font-size:.8rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em}
.filters{max-width:1120px;margin:-28px auto 0;padding:0 24px;position:relative;z-index:10}
.filters-inner{background:var(--surface);border-radius:var(--radius-md);box-shadow:var(--shadow-lg);padding:16px 20px;display:flex;gap:12px;flex-wrap:wrap;align-items:center}
.filter-input{flex:1;min-width:200px;padding:10px 14px;border:1px solid var(--border);border-radius:var(--radius-sm);font-size:.875rem;outline:none;transition:border-color var(--transition)}
.filter-input:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-light)}
.filter-select{padding:10px 14px;border:1px solid var(--border);border-radius:var(--radius-sm);font-size:.875rem;background:#fff;outline:none;cursor:pointer}
.filter-count{font-size:.8rem;color:var(--ink-light);margin-left:auto;white-space:nowrap}
.listings{max-width:1120px;margin:0 auto;padding:32px 24px 48px}
.cards-grid{display:grid;gap:0;background:var(--border);border:1px solid var(--border);border-radius:var(--radius-md);overflow:hidden}
.card{background:var(--surface);padding:20px 24px;border-bottom:1px solid var(--border);transition:background var(--transition);display:flex;flex-direction:column;gap:8px}
.card:last-child{border-bottom:none}
.card:hover{background:var(--surface-subtle)}
.card-top{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
.card-name{font-size:1.05rem;font-weight:600;color:var(--ink)}
.card-rating{display:flex;align-items:center;gap:4px;white-space:nowrap;flex-shrink:0}
.card-rating .stars{color:#eab308;font-size:.85rem;letter-spacing:1px}
.card-rating .num{font-size:.8rem;color:var(--ink-light);font-weight:500}
.card-rating .reviews{font-size:.75rem;color:var(--ink-light)}
.card-meta{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:.8rem;color:var(--ink-light)}
.card-meta span{display:flex;align-items:center;gap:4px}
.card-tags{display:flex;gap:6px;flex-wrap:wrap}
.tag{display:inline-flex;align-items:center;padding:2px 8px;border-radius:100px;font-size:.7rem;font-weight:500;background:var(--surface-highlight);color:var(--ink-medium)}
.tag-featured{background:var(--amber-light);color:var(--amber);font-weight:600}
.tag-verified{background:var(--green-light);color:var(--green)}
.card-actions{display:flex;gap:8px;margin-top:4px}
.btn{display:inline-flex;align-items:center;gap:4px;padding:8px 16px;border-radius:var(--radius-sm);font-size:.8rem;font-weight:600;border:none;cursor:pointer;transition:all var(--transition);text-decoration:none}
.btn:hover{text-decoration:none}
.btn-primary{background:var(--accent);color:#fff}
.btn-primary:hover{background:var(--accent-hover)}
.btn-outline{background:transparent;color:var(--ink-medium);border:1px solid var(--border)}
.btn-outline:hover{background:var(--surface-highlight);color:var(--ink)}
.section{max-width:1120px;margin:0 auto;padding:48px 24px 40px}
.section-title{font-size:1.4rem;font-weight:700;margin-bottom:24px;letter-spacing:-.01em}
.section-subtle{background:var(--surface);border-radius:var(--radius-lg);padding:28px 32px;box-shadow:var(--shadow-sm)}
.guide{display:flex;flex-direction:column;gap:20px}
.guide h3{font-size:.95rem;font-weight:600;margin-bottom:4px}
.guide p{font-size:.875rem;color:var(--ink-medium);line-height:1.6}
.blog-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:20px}
.blog-card{background:var(--surface);border-radius:var(--radius-md);padding:24px;box-shadow:var(--shadow-sm);text-decoration:none;color:inherit;display:flex;flex-direction:column;gap:8px;border:1px solid var(--border);transition:all var(--transition)}
.blog-card:hover{box-shadow:var(--shadow-md);transform:translateY(-2px);text-decoration:none}
.blog-card h3{font-size:1rem;font-weight:600;color:var(--ink)}
.blog-card p{font-size:.85rem;color:var(--ink-medium);line-height:1.5}
.blog-read{font-size:.8rem;font-weight:600;color:var(--accent);margin-top:auto}
.faq-list{border-top:1px solid var(--border)}
.faq-item{border-bottom:1px solid var(--border);cursor:pointer}
.faq-q{padding:16px 0;font-size:.9rem;font-weight:500;display:flex;justify-content:space-between;align-items:center;user-select:none}
.faq-q::after{content:'+';font-size:1.1rem;color:var(--ink-light)}
.faq-item.open .faq-q::after{content:'\\2212'}
.faq-a{display:none;font-size:.85rem;color:var(--ink-medium);line-height:1.6;padding-bottom:16px}
.faq-item.open .faq-a{display:block}
.contact-grid{display:grid;grid-template-columns:1fr 1fr;gap:32px}
.contact-info h3{font-size:1rem;font-weight:600;margin-bottom:8px}
.contact-info p{font-size:.85rem;color:var(--ink-medium);line-height:1.6}
.contact-form input,.contact-form textarea,.contact-form select{width:100%;padding:10px 14px;border:1px solid var(--border);border-radius:var(--radius-sm);font-size:.875rem;margin-bottom:12px;font-family:inherit;outline:none}
.contact-form input:focus,.contact-form textarea:focus,.contact-form select:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-light)}
.contact-form textarea{resize:vertical;min-height:100px}
.contact-form button{width:100%;padding:11px;border:none;border-radius:var(--radius-sm);background:var(--accent);color:#fff;font-size:.9rem;font-weight:600;cursor:pointer;transition:background var(--transition)}
.contact-form button:hover{background:var(--accent-hover)}
footer{background:var(--ink);color:#94a3b8;text-align:center;padding:28px 24px;font-size:.8rem}
footer a{color:#60a5fa}
.no-results{text-align:center;padding:40px 24px;color:var(--ink-light)}
.no-results h3{font-weight:600;margin-bottom:4px;color:var(--ink-medium)}
@media(max-width:600px){.nav-inner{padding:0 16px}.nav-links{gap:16px}.hero{padding:40px 16px 48px}.hero-stats{gap:24px}.filters{padding:0 16px}.filters-inner{flex-direction:column;align-items:stretch}.filter-count{margin-left:0}.listings{padding:24px 16px}.card{padding:16px}.card-top{flex-direction:column}.section{padding:32px 16px}.section-subtle{padding:20px}.card-actions{flex-wrap:wrap}.btn{flex:1;justify-content:center}}
@media(max-width:700px){.contact-grid{grid-template-columns:1fr}}"""


def nav_html(city_only):
    return f'''<nav class="nav"><div class="nav-inner"><div class="nav-logo"><span class="mark">&#8612;</span> {city_only} <span style="color:var(--ink-light);font-weight:400;">Plumbing Pros</span></div><div class="nav-links"><a href="#listings">Plumbers</a><a href="#blog">Blog</a><a href="#guide">Guide</a><a href="#faq">FAQ</a><a href="#contact">Contact</a></div></div></nav>'''


def hero_html(brand, niche, city_state, total, avg_rating):
    return f'''<section class="hero"><h1>Best {niche}s in {city_state}</h1><p>Your trusted directory of top-rated, licensed plumbing professionals serving {city_state}.</p><div class="hero-stats"><div class="hero-stat"><span class="hero-stat-num">{total}</span><span class="hero-stat-label">Listed Plumbers</span></div><div class="hero-stat"><span class="hero-stat-num">{avg_rating}</span><span class="hero-stat-label">Average Rating</span></div><div class="hero-stat"><span class="hero-stat-num">24/7</span><span class="hero-stat-label">Emergency Service</span></div></div></section>'''


def filters_html(total):
    return f'''<div class="filters"><div class="filters-inner"><input type="text" class="filter-input" id="searchInput" placeholder="Search plumbers by name, service, or address..." autocomplete="off"><select class="filter-select" id="sortSelect"><option value="rating-desc">Highest Rated</option><option value="rating-asc">Lowest Rated</option><option value="name">A-Z</option><option value="reviews">Most Reviews</option></select><span class="filter-count" id="filterCount">Showing {total}</span></div></div>'''


def listings_section():
    return '''<section class="listings" id="listings"><div class="cards-grid" id="cardsGrid"></div></section>'''


def blog_section(blog_cards):
    return f'''<section class="section" id="blog"><h2 class="section-title">&#128221; Plumbing Blog</h2><div class="blog-grid">{blog_cards}</div></section>'''


def guide_section(niche, city_only, lower):
    return f'''<section class="section" id="guide"><h2 class="section-title">How to Choose a {niche} in {city_only}</h2><div class="section-subtle guide">
<div><h3>1. Check Licensing & Insurance</h3><p>In Arizona, the Registrar of Contractors (ROC) licenses all professional plumbers. Always verify a valid license number before hiring. This protects you if something goes wrong.</p></div>
<div><h3>2. Read Local Reviews</h3><p>{city_only} is a tight-knit community. Check Google reviews and ask neighbors. A {lower} with consistent 4+ star ratings and 50+ reviews has proven their reliability locally.</p></div>
<div><h3>3. Get 3 Quotes</h3><p>For non-emergency work, always get multiple bids. Be wary of prices far below market rate. Most {city_only} plumbers offer free estimates.</p></div>
<div><h3>4. Ask About Emergency Service</h3><p>A burst pipe at 2am needs immediate attention. Many {city_only} plumbers offer 24/7 service - confirm availability before you need it.</p></div>
<div><h3>5. Know the Local Terrain</h3><p>Southern Arizona has unique plumbing challenges: {REGION_FEATURES}. Local plumbers understand these conditions best.</p></div>
</div></section>'''


def faq_section(niche, lower, city_only):
    items = ""
    for faq in FAQ_DATA:
        q = faq["q"].format(city=city_only, landmark=REGION_LANDMARK)
        a = faq["a"].format(city=city_only, landmark=REGION_LANDMARK)
        items += f'''<div class="faq-item"><div class="faq-q" onclick="this.parentElement.classList.toggle('open')">{q}</div><div class="faq-a">{a}</div></div>\n'''
    # first item open by default
    items = items.replace('class="faq-item"', 'class="faq-item open"', 1)
    return f'''<section class="section" id="faq"><h2 class="section-title">Frequently Asked Questions</h2><div class="section-subtle"><div class="faq-list">{items}</div></div></section>'''


def contact_section(email, city_only, lower):
    return f'''<section class="section" id="contact"><h2 class="section-title">Get a Free Quote</h2><div class="section-subtle"><div class="contact-grid"><div class="contact-info"><h3>Have a plumbing problem?</h3><p>Tell us what you need and we will connect you with the right {city_only} {lower}. We will match you based on your job type, location, and urgency - for free.</p><p style="margin-top:16px;font-size:.8rem;color:var(--ink-light);">Your information is never shared without your permission.</p></div>
<form class="contact-form" action="https://formsubmit.co/{email}" method="POST"><input type="text" name="name" placeholder="Your name" required><input type="email" name="email" placeholder="Your email" required><input type="tel" name="phone" placeholder="Your phone number"><select name="service"><option value="">Select service needed...</option><option>Emergency repair</option><option>Water heater</option><option>Drain cleaning</option><option>Sewer line</option><option>Pipe repair</option><option>Remodel / new construction</option><option>Other</option></select><textarea name="message" placeholder="Describe your plumbing issue..." required></textarea><input type="hidden" name="_subject" value="{city_only} Plumbing Quote Request"><input type="hidden" name="_captcha" value="false"><button type="submit">Request Free Quote</button></form></div></div></section>'''


def footer_html(brand):
    return f'''<footer><p>{brand} &mdash; Helping homeowners find trusted plumbers in {COUNTY}</p><p style="margin-top:8px;">&copy; 2025 &middot; <a href="#listings">Browse Plumbers</a> &middot; <a href="#blog">Blog</a> &middot; <a href="#contact">Get a Quote</a></p></footer>'''


def js_code():
    return r'''
function renderStars(r){var f=Math.floor(r),h=r-f>=0.3?1:0,e=5-f-h;return '\u2605'.repeat(f)+(h?'\u00bd':'')+'<span style="color:#d1d5db;">'+'\u2605'.repeat(e)+'</span>'}
function getCard(p){var t=[];if(p.featured)t.push('<span class="tag tag-featured">\u2b50 Featured</span>');if(p.reviews>=50)t.push('<span class="tag tag-verified">\u2713 Verified</span>');if(p.website)t.push('<span class="tag">Has Website</span>');var ph=p.phone||'',pl=ph?'tel:'+ph:'#contact';return '<div class="card"><div class="card-top"><div><div class="card-name">'+p.name+'</div><div class="card-meta"><span>\ud83d\udccd '+p.addr+'</span>'+(ph?'<span>\ud83d\udcde '+ph+'</span>':'')+'</div></div><div class="card-rating"><span class="stars">'+renderStars(p.rating)+'</span> <span class="num">'+p.rating.toFixed(1)+'</span> <span class="reviews">('+p.reviews+')</span></div></div>'+(t.length?'<div class="card-tags">'+t.join('')+'</div>':'')+'<div class="card-actions"><a href="'+pl+'" class="btn btn-primary">\ud83d\udcde Call Now</a>'+(p.website?'<a href="'+p.website+'" target="_blank" rel="noopener" class="btn btn-outline">\ud83c\udf10 Website</a>':'')+'<a href="#contact" class="btn btn-outline">Get Quote</a></div></div>'}
function render(a){var g=document.getElementById('cardsGrid');if(!a.length){g.innerHTML='<div class="no-results"><h3>No plumbers found</h3><p>Try a different search term</p></div>';return}g.innerHTML=a.map(getCard).join('')}
function getFiltered(){var q=document.getElementById('searchInput').value.toLowerCase().trim(),s=document.getElementById('sortSelect').value,l=allPlumbers.slice();if(q)l=l.filter(function(p){return p.name.toLowerCase().indexOf(q)!==-1||p.addr.toLowerCase().indexOf(q)!==-1||(p.phone&&p.phone.indexOf(q)!==-1)});l.sort(function(a,b){if(s==='rating-desc')return(b.rating||0)-(a.rating||0);if(s==='rating-asc')return(a.rating||0)-(b.rating||0);if(s==='name')return a.name.localeCompare(b.name);if(s==='reviews')return(b.reviews||0)-(a.reviews||0);return 0});return l}
function update(){var l=getFiltered();render(l);document.getElementById('filterCount').textContent='Showing '+l.length}
document.getElementById('searchInput').addEventListener('input',update);document.getElementById('sortSelect').addEventListener('change',update);update();
'''


# ─── STEP 3: Generate blog posts with Article schema ─────────────────────

def add_article_schema_to_blog(html_file, title, description, url):
    """Inject Article schema into a blog post HTML file."""
    schema = f'''<script type="application/ld+json">{{
"@context":"https://schema.org",
"@type":"Article",
"headline":"{esc_json(title)}",
"description":"{esc_json(description)}",
"url":"{esc_json(url)}",
"datePublished":"{time.strftime('%Y-%m-%d')}",
"dateModified":"{time.strftime('%Y-%m-%d')}",
"author":{{"@type":"Organization","name":"{esc_json(BRAND)}"}},
"publisher":{{"@type":"Organization","name":"{esc_json(BRAND)}"}}
}}</script>'''
    
    with open(html_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Inject schema after <head> opening (before <style> or other head content)
    if '<script type="application/ld+json"' not in content:
        # Inject after the title/meta block, before </head>
        content = content.replace('</head>', f'{schema}\n</head>', 1)
        # Also inject OG tags
        og_tags = f'''
<meta property="og:type" content="article">
<meta property="og:title" content="{esc_json(title)}">
<meta property="og:description" content="{esc_json(description)}">
<meta property="og:url" content="{esc_json(url)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc_json(title)}">
<meta name="twitter:description" content="{esc_json(description)}">'''
        content = content.replace('</head>', f'{og_tags}\n</head>', 1)
        
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False


# ─── MAIN ───────────────────────────────────────────────────────────────

def main():
    print(f"Building directory: {NICHE}s in {CITY}, {STATE}")
    
    # Step 1: Fetch data
    api_key = load_api_key()
    businesses = []
    
    if api_key:
        print(f"Google Places API key found. Fetching {NICHE.lower()} data...")
        businesses = fetch_plumbers_via_places_api(api_key)
    
    if not businesses:
        print("No API key or API failed. Using cached data...")
        if DATA_FILE.exists():
            with open(DATA_FILE) as f:
                cached = json.load(f)
                businesses = cached.get("businesses", [])
            if businesses:
                print(f"Loaded {len(businesses)} plumbers from cache")
        if not businesses:
            print("No cached data found. Run with valid API key first.")
            return
    
    # Step 2: Save data
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, 'w') as f:
        json.dump({"city": CITY, "state": STATE, "niche": NICHE, "updated": time.strftime('%Y-%m-%d'), "businesses": businesses}, f, indent=2)
    print(f"Saved {len(businesses)} listings to {DATA_FILE}")
    
    # Step 3: Build HTML
    html = build_site(businesses)
    with open(INDEX_FILE, 'w') as f:
        f.write(html)
    print(f"Built site: {INDEX_FILE}")
    
    # Step 4: Generate sitemap.xml
    sitemap = build_sitemap()
    with open(SITEMAP_FILE, 'w') as f:
        f.write(sitemap)
    print(f"Generated sitemap: {SITEMAP_FILE}")
    
    # Step 5: Generate robots.txt
    robots = f"User-agent: *\nAllow: /\nSitemap: {URL_BASE}sitemap.xml\n"
    with open(ROBOTS_FILE, 'w') as f:
        f.write(robots)
    print(f"Generated robots.txt: {ROBOTS_FILE}")
    
    # Step 6: Add Article schema to blog posts
    blog_count = 0
    for title, filename, excerpt in BLOG_POSTS:
        blog_path = BLOG_DIR / filename
        if blog_path.exists():
            blog_url = f"{URL_BASE}blog/{filename}"
            if add_article_schema_to_blog(str(blog_path), title, excerpt, blog_url):
                blog_count += 1
    if blog_count:
        print(f"Added Article schema to {blog_count} blog posts")
    
    print(f"\nDone! {len(businesses)} {NICHE.lower()}s listed in {CITY}, {STATE}")
    print(f"  - SEO schema (WebSite, LocalBusiness, FAQ, BreadcrumbList, BlogPosting)")
    print(f"  - Open Graph + Twitter Cards")
    print(f"  - sitemap.xml + robots.txt")
    if GA4_ID:
        print(f"  - Google Analytics (GA4: {GA4_ID})")
    if GSC_VERIFICATION:
        print(f"  - Google Search Console verified")


if __name__ == "__main__":
    main()
