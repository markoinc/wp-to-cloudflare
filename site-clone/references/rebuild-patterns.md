# Rebuild Patterns

Common patterns for rebuilding contractor/local-business sites after cloning.

---

## What to Keep (Always)

- **Phone number** — critical for lead gen, put it in header AND hero
- **Service list** — exact services they offer, their words
- **Service area** — cities/counties they cover
- **Logo** — if decent; otherwise flag for replacement
- **Testimonials/reviews** — copy them verbatim, attributed
- **License/insurance numbers** — trust signals
- **Business address** — for local SEO schema

---

## What to Replace

- **All images** → re-optimize as WebP at max 1600px wide, quality 82
- **Background images** → compress but keep if they're photos of their work
- **Stock photos** → flag for replacement with real work photos if client provides
- **Fonts** → swap to Google Fonts (Montserrat + Open Sans is safe default)

---

## What to Remove

- **All tracking scripts** (GTM, GA, FB Pixel, Hotjar) — unless client asks
- **WordPress/Elementor bloat** — plugin CSS not used on page
- **Cookie consent banners** — static sites don't need them unless collecting data
- **Chat widgets** — slow, replace with click-to-call

---

## What to Add

- **Hero CTA** — "Get a Free Estimate" button + phone number above the fold
- **Trust bar** — "Licensed · Insured · Free Estimates · [City] area"
- **Before/after or gallery section** — even placeholders
- **Google Maps embed** — for local SEO
- **Contact form** → replace WP contact forms with Formspree embed
- **Schema markup** — LocalBusiness JSON-LD with address, phone, service area
- **tel: links** — every phone number should be a `<a href="tel:+1...">`

---

## Target Performance

| Metric | Target | Notes |
|---|---|---|
| Mobile PageSpeed | 85+ | Static with optimized images |
| LCP | <3.0s | Preload hero image |
| TBT | <200ms | No blocking JS |
| CLS | 0 | Set explicit img dimensions |

---

## Typical Stack for Rebuilt Site

For a simple rebuild that just needs to look good and load fast:
- **Raw HTML/CSS** — no framework, no JS unless needed
- **Tailwind via CDN** (optional) — fast prototyping
- **Formspree** — for contact forms
- **Google Fonts** — loaded async

For anything that needs Elementor-like flexibility:
- Keep the WordPress export and just optimize it (use wp-to-cloudflare skill)

---

## Folder Structure for Rebuilt Sites

```
~/prospects/{slug}/
├── raw/                  ← wget mirror from scrape_site.py
├── screenshots/          ← before screenshots
├── audit.json            ← extracted metadata
├── rebuild_brief.md      ← analysis from analyze_site.py
└── rebuild/              ← your new clean version
    ├── index.html
    ├── styles.css
    └── assets/
        └── images/
```

---

## Sales Pitch Context

The usual flow:

1. Scrape their site quietly (no login needed)
2. Run analysis → identify 3-5 obvious problems (slow, bad mobile, no CTA)
3. Build a quick rebuild (even 60% complete is enough for demo)
4. Send them: "I already rebuilt your site — here's the live preview"
5. Close on either hosting + management or one-time fee

The demo URL can be a Cloudflare Pages preview link (`*.pages.dev`) — no custom domain needed until they pay.
