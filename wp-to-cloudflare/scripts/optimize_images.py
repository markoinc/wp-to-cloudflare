#!/usr/bin/env python3
"""
optimize_images.py — Compress and deduplicate WordPress upload images for static deployment.

Usage:
    python3 optimize_images.py <uploads_dir> [--max-width 1600] [--quality 82] [--dry-run]

What it does:
1. Removes WordPress-generated scaled variants (*-scaled.*, *-NNNxNNN.*, *-scaled-N.*)
   that are NOT referenced in any HTML/CSS file in the site
2. Re-encodes remaining images >200KB as JPEG/WebP at reduced quality
3. Reports before/after size

Requires: Pillow  (pip install Pillow)
"""

import argparse
import os
import re
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow not installed. Run: pip install Pillow")
    sys.exit(1)


# WordPress auto-generates these suffix patterns — safe to remove if unreferenced
WP_SCALED_PATTERN = re.compile(
    r'-(\d+x\d+|scaled(-\d+)?)(\.(jpe?g|png|webp|gif))$',
    re.IGNORECASE
)

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp'}


def find_referenced_files(site_root: Path) -> set:
    """Scan all HTML/CSS files in site_root and return set of referenced filenames.

    Scans src=, href=, url(), AND srcset= attributes — critical for WordPress
    responsive images which use srcset for scaled variants.
    """
    refs = set()
    # Matches src=, href=, url(
    ATTR_RE = re.compile(r'(?:src|href|url)\s*[=\(]\s*["\']?([^"\')\s>]+)', re.IGNORECASE)
    # Matches srcset="url1 Xw, url2 Yw, ..."
    SRCSET_RE = re.compile(r'srcset\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
    SRCSET_URL_RE = re.compile(r'([^\s,]+\.(?:webp|jpe?g|png|gif|avif|svg))', re.IGNORECASE)

    for ext in ('*.html', '*.css', '*.js'):
        for f in site_root.rglob(ext):
            try:
                content = f.read_text(errors='ignore')
                # Standard attribute references
                for ref in ATTR_RE.findall(content):
                    refs.add(Path(ref).name)
                # srcset= attribute — each comma-separated URL
                for srcset_val in SRCSET_RE.findall(content):
                    for url in SRCSET_URL_RE.findall(srcset_val):
                        refs.add(Path(url.split('?')[0]).name)
            except Exception:
                pass
    return refs


def is_wp_variant(path: Path) -> bool:
    return bool(WP_SCALED_PATTERN.search(path.name))


def compress_image(path: Path, max_width: int, quality: int) -> int:
    """Compress image in-place. Returns bytes saved (negative = grew)."""
    original_size = path.stat().st_size
    try:
        img = Image.open(path)
        # Resize if wider than max_width
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.LANCZOS)

        # Convert RGBA → RGB for JPEG
        if img.mode in ('RGBA', 'P') and path.suffix.lower() in ('.jpg', '.jpeg'):
            img = img.convert('RGB')

        img.save(path, quality=quality, optimize=True)
        return original_size - path.stat().st_size
    except Exception as e:
        print(f"  SKIP {path.name}: {e}")
        return 0


def main():
    parser = argparse.ArgumentParser(description='Optimize WordPress upload images')
    parser.add_argument('uploads_dir', help='Path to wp-content/uploads/')
    parser.add_argument('--max-width', type=int, default=1600, help='Max image width px (default 1600)')
    parser.add_argument('--quality', type=int, default=82, help='JPEG/WebP quality 1-95 (default 82)')
    parser.add_argument('--size-threshold', type=int, default=200_000, help='Only compress files >N bytes (default 200000)')
    parser.add_argument('--dry-run', action='store_true', help='Report what would be done without making changes')
    parser.add_argument('--confirm', action='store_true',
                        help='Required to actually delete/modify files (prevents accidental runs)')
    args = parser.parse_args()

    if not args.dry_run and not args.confirm:
        print("ERROR: Pass --confirm to modify files, or --dry-run to preview changes.")
        print("       This protects against accidental image deletion.")
        sys.exit(1)

    uploads = Path(args.uploads_dir)
    if not uploads.exists():
        print(f"ERROR: {uploads} does not exist")
        sys.exit(1)

    # Find site root (parent of wp-content)
    site_root = uploads.parent.parent
    print(f"Scanning for references in: {site_root}")
    referenced = find_referenced_files(site_root)
    print(f"Found {len(referenced)} referenced asset filenames\n")

    all_images = [p for p in uploads.rglob('*') if p.suffix.lower() in IMAGE_EXTS]
    total_original = sum(p.stat().st_size for p in all_images)

    removed_count = 0
    removed_bytes = 0
    compressed_count = 0
    compressed_bytes = 0

    for img_path in sorted(all_images):
        # Step 1: Remove unreferenced WP variants
        if is_wp_variant(img_path) and img_path.name not in referenced:
            size = img_path.stat().st_size
            if args.dry_run:
                print(f"  [DRY] REMOVE variant: {img_path.relative_to(uploads)} ({size/1024:.0f}KB)")
            else:
                img_path.unlink()
                print(f"  REMOVED: {img_path.name} ({size/1024:.0f}KB)")
            removed_count += 1
            removed_bytes += size
            continue

        # Step 2: Compress large images
        if img_path.stat().st_size > args.size_threshold:
            if args.dry_run:
                print(f"  [DRY] COMPRESS: {img_path.relative_to(uploads)} ({img_path.stat().st_size/1024:.0f}KB)")
            else:
                saved = compress_image(img_path, args.max_width, args.quality)
                if saved > 0:
                    print(f"  COMPRESSED: {img_path.name} (saved {saved/1024:.0f}KB)")
                    compressed_bytes += saved
                    compressed_count += 1

    total_saved = removed_bytes + compressed_bytes
    print(f"\n{'='*50}")
    print(f"Original size:   {total_original/1_048_576:.1f}MB")
    print(f"Variants removed: {removed_count} files ({removed_bytes/1_048_576:.1f}MB)")
    print(f"Images compressed: {compressed_count} files ({compressed_bytes/1_048_576:.1f}MB)")
    print(f"Total saved:      {total_saved/1_048_576:.1f}MB")
    print(f"Final size:       {(total_original-total_saved)/1_048_576:.1f}MB")
    if args.dry_run:
        print("\n[DRY RUN — no files modified]")


if __name__ == '__main__':
    main()
