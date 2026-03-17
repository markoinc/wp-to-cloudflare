# Embed Compatibility in Static WP Sites

Simply Static captures the full rendered HTML, so most third-party embeds work fine.

## ✅ Works After Static Export

| Embed Type | Example | Notes |
|---|---|---|
| GHL / LeadConnector forms | `api.leadconnectorhq.com/widget/survey/...` | iframes render fine |
| Google Maps | `google.com/maps/embed?pb=...` | Works as-is |
| Google Business Profile widget | Embedded via iframe | Works |
| Reputation/review widgets | `reputationhub.site/...` | Works |
| Calendly | `calendly.com/widgets/...` | Works |
| YouTube embeds | `youtube.com/embed/...` | Works |
| Typeform | `embed.typeform.com/...` | Works |
| External chat widgets | Intercom, Drift, etc. | Works (JS snippet in HTML) |

## ❌ Does NOT Work After Static Export

| Feature | Why | Alternative |
|---|---|---|
| WooCommerce checkout | Requires PHP/session | Use Stripe Payment Links or embed |
| WP contact forms (CF7, WPForms) | POST handler is gone | Replace with GHL form iframe |
| Login/account pages | PHP session required | Remove or redirect to external |
| Search (native WP) | Requires WP query | Replace with Google CSE embed |
| Live preview of drafts | WP admin feature | N/A for production |

## Handling Contact Forms

If the site has WP contact forms, Simply Static exports the HTML form but the POST endpoint no longer works. Options:

1. **Best:** Replace with GHL form embed before running Simply Static — then the static export captures the working iframe
2. **Post-export patch:** Find `<form>` tags in the static HTML and swap for GHL iframe via find/replace script
3. **Acceptable for rank-and-rent:** Just leave the phone number as the CTA — most concrete leads call anyway

## Phone Number CTAs

All `<a href="tel:...">` links work perfectly in static sites. No changes needed.
