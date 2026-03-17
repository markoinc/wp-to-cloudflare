# Image Optimization Reference

## The Problem

WordPress auto-generates multiple scaled variants of every uploaded image:
- `photo.jpg` — original (may be 4–10MB)
- `photo-scaled.jpg` — WP's "big image" threshold resize
- `photo-2048x1365.jpg`, `photo-1024x683.jpg`, `photo-300x200.jpg` — responsive sizes
- `photo-scaled-1.jpg`, `photo-scaled-2.jpg` — if re-uploaded

A typical site with 50 source images becomes 300–500 files and 200–800MB. Most of these variants are never referenced in the static HTML.

## What optimize_images.py Does

**Pass 1 — Remove unreferenced WP variants:**
Scans all `.html`, `.css`, `.js` files for filename references. Any image matching the WP variant pattern (`-NNNxNNN`, `-scaled`, `-scaled-N`) that is NOT referenced anywhere gets deleted.

**Pass 2 — Compress large remaining images:**
Any image >200KB (configurable) gets resampled at max 1600px wide and re-encoded at quality 82. This is lossless in practice for web display while cutting file size 50–80%.

## Recommended Settings

```bash
# Standard site (Elementor/WP)
python3 optimize_images.py static-site/wp-content/uploads/ --max-width 1600 --quality 82

# Hero-image heavy site (large backgrounds)
python3 optimize_images.py static-site/wp-content/uploads/ --max-width 2000 --quality 85

# Dry run first to see impact
python3 optimize_images.py static-site/wp-content/uploads/ --dry-run
```

## Expected Results

| Site type | Before | After | Reduction |
|---|---|---|---|
| Simple service site (5–10 pages) | 80–200MB | 15–40MB | 70–80% |
| Multi-page Elementor (20+ pages) | 400–900MB | 50–120MB | 75–85% |

## PageSpeed Impact

The #1 mobile PageSpeed killer for migrated WP sites is uncompressed images. After optimization:
- Sites that score 30–50 before → typically 85–95 after
- LCP (Largest Contentful Paint) improves most — hero images often drop from 4MB to 150KB

## What It Does NOT Touch

- Images actually referenced in HTML (only removes unreferenced variants)
- GIF files (animation preservation)
- SVG files
- Files already under the size threshold (default 200KB)
