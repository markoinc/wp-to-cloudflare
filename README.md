# OpenClaw Skills

A collection of reusable OpenClaw agent skills for automating business workflows.

## Skills

| Skill | What it does |
|---|---|
| [wp-to-cloudflare](./wp-to-cloudflare/) | Migrate any WordPress site to free Cloudflare Pages static hosting |
| [site-clone](./site-clone/) | Scrape, analyze, and rebuild a prospect's website as a fast static demo |

## What are OpenClaw Skills?

Skills are self-contained packages that extend OpenClaw agents with specialized workflows, scripts, and domain knowledge. Each skill has a `SKILL.md` (loaded into agent context when triggered) plus optional scripts and reference files.

## Installation

Install a skill by dropping the folder into your OpenClaw workspace's `skills/` directory, or use the `.skill` package file with `openclaw skills install`.

## Contributing

Skills should contain no credentials, site-specific data, or hardcoded values. Scripts should use argparse, validate input paths, and never use `shell=True`.
