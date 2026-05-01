#!/usr/bin/env python3
"""
deploy.py — Push a prepared static-site directory to GitHub + Cloudflare Pages.

Usage:
    python3 deploy.py <site-slug> <domain> <github-org> [--static-dir PATH]

Credentials required (JSON files):
    ~/.config/cloudflare/credentials.json  → {"api_token": "...", "account_id": "..."}
    ~/.config/github/credentials.json      → {"token": "..."}

Example:
    python3 deploy.py my-site mysite.com my-github-org
    python3 deploy.py my-site mysite.com my-github-org --static-dir ./export
"""

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests

# Allowlist patterns — prevent injection via user-supplied args
SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9\-]{0,62}$')
DOMAIN_RE = re.compile(r'^[a-z0-9][a-z0-9\-\.]{1,253}[a-z0-9]$')
ORG_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9\-]{0,38}$')


def validate_inputs(slug, domain, org):
    if not SLUG_RE.match(slug):
        print(f"ERROR: Invalid slug '{slug}' — must be lowercase letters, digits, hyphens only")
        sys.exit(1)
    if not DOMAIN_RE.match(domain):
        print(f"ERROR: Invalid domain '{domain}'")
        sys.exit(1)
    if not ORG_RE.match(org):
        print(f"ERROR: Invalid GitHub org/user '{org}'")
        sys.exit(1)


def load_json(path):
    p = Path(path).expanduser()
    if not p.exists():
        print(f"ERROR: Credentials not found at {p}")
        sys.exit(1)
    return json.loads(p.read_text())


def run(args_list, cwd=None, check=True, env=None):
    """Run a subprocess safely using list form (no shell=True, no injection risk)."""
    merged_env = {**os.environ, **(env or {})}
    result = subprocess.run(
        args_list, cwd=cwd, capture_output=True, text=True, env=merged_env
    )
    if check and result.returncode != 0:
        # Never print the full command — may contain tokens in env
        print(f"ERROR in subprocess (exit {result.returncode}):\n{result.stderr[:500]}")
        sys.exit(1)
    return result.stdout.strip()


def create_github_repo(slug, token, org):
    """Create private GitHub repo. Returns clone URL."""
    headers = {"Authorization": f"token {token}", "Content-Type": "application/json"}
    r = requests.post(
        "https://api.github.com/user/repos",
        headers=headers,
        json={"name": slug, "private": True, "description": f"Static site — {slug}"}
    )
    data = r.json()
    if r.status_code == 201:
        print(f"  Created repo: {org}/{slug}")
        return data["clone_url"]
    elif r.status_code == 422 and "already exists" in str(data):
        print(f"  Repo {org}/{slug} already exists — using it")
        return f"https://github.com/{org}/{slug}.git"
    else:
        print(f"ERROR creating repo (status {r.status_code}) — check token permissions")
        sys.exit(1)


def push_to_github(static_dir, slug, token, org):
    """Init git repo and push to GitHub.

    Token is passed via GIT_ASKPASS helper — never embedded in the remote URL
    and never stored in .git/config.
    """
    create_github_repo(slug, token, org)
    remote_url = f"https://github.com/{org}/{slug}.git"

    git_dir = Path(static_dir) / ".git"
    if git_dir.exists():
        print("  Git repo exists — resetting remote")
        run(["git", "remote", "remove", "origin"], cwd=static_dir, check=False)
    else:
        run(["git", "init"], cwd=static_dir)

    run(["git", "remote", "add", "origin", remote_url], cwd=static_dir)
    run(["git", "add", "-A"], cwd=static_dir)
    run(["git", "commit", "-m", "Initial static export", "--allow-empty"], cwd=static_dir)
    run(["git", "branch", "-M", "main"], cwd=static_dir)

    # Write the askpass helper to a tempfile *outside* the git tree (so a stray
    # `git add` can never commit it) and create it 0o600 from the start. The
    # token is shlex-quoted so a future token format with shell metacharacters
    # can't break out of the echo. The `finally` block unlinks; if the process
    # is SIGKILLed before that runs, the file is in the system temp dir and
    # not reachable by other users (mode 0o600 + dir 0o700 on macOS/Linux).
    fd, helper_path_str = tempfile.mkstemp(prefix="git-askpass-", suffix=".sh")
    helper_path = Path(helper_path_str)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(f"#!/bin/sh\nprintf '%s\\n' {shlex.quote(token)}\n")
        helper_path.chmod(0o700)

        run(
            ["git", "push", "-u", "origin", "main"],
            cwd=static_dir,
            env={"GIT_ASKPASS": str(helper_path), "GIT_USERNAME": "x-token"}
        )
    finally:
        try:
            helper_path.unlink()
        except FileNotFoundError:
            pass

    print(f"  Pushed to github.com/{org}/{slug}")
    return org


def create_cf_pages(slug, org, token, account_id):
    """Create Cloudflare Pages project linked to GitHub repo."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    base = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/pages/projects"

    payload = {
        "name": slug,
        "production_branch": "main",
        "source": {
            "type": "github",
            "config": {
                "owner": org,
                "repo_name": slug,
                "production_branch": "main",
                "pr_comments_enabled": False,
                "deployments_enabled": True
            }
        },
        "build_config": {"build_command": "", "destination_dir": "", "root_dir": "/"}
    }

    r = requests.post(base, headers=headers, json=payload)
    data = r.json()
    if data.get("success"):
        print(f"  Cloudflare Pages project created: {slug}.pages.dev")
    elif "already exists" in str(data):
        print(f"  Project {slug} already exists — continuing")
    else:
        print(f"ERROR creating CF Pages project (HTTP {r.status_code})")
        sys.exit(1)

    # Trigger deployment
    r2 = requests.post(f"{base}/{slug}/deployments", headers=headers)
    if r2.json().get("success"):
        print("  Deployment triggered")
    else:
        print(f"  Deployment trigger: {r2.status_code} (may already be building)")

    return headers, base


def add_custom_domains(slug, domain, headers, base):
    """Add apex and www as custom domains."""
    for d in [domain, f"www.{domain}"]:
        r = requests.post(f"{base}/{slug}/domains", headers=headers, json={"name": d})
        status = r.json().get("result", {}).get("status", "unknown")
        print(f"  Custom domain {d}: {status}")
    time.sleep(1)


def main():
    parser = argparse.ArgumentParser(description='Deploy static site to GitHub + Cloudflare Pages')
    parser.add_argument('slug', help='Site slug (used as repo name and Pages project name)')
    parser.add_argument('domain', help='Production domain (e.g. example.com)')
    parser.add_argument('org', help='GitHub org or username')
    parser.add_argument('--static-dir', default=None,
                        help='Path to static-site directory (default: ./migrations/{slug}/static-site)')
    args = parser.parse_args()

    validate_inputs(args.slug, args.domain, args.org)

    static_dir = args.static_dir or str(
        Path.home() / "clawd" / "concrete" / "migrations" / args.slug / "static-site"
    )
    if not Path(static_dir).exists():
        print(f"ERROR: Static site directory not found: {static_dir}")
        sys.exit(1)

    gh = load_json("~/.config/github/credentials.json")
    cf = load_json("~/.config/cloudflare/credentials.json")

    print(f"\n{'='*50}")
    print(f"Deploying: {args.slug} ({args.domain})")
    print(f"Source:    {static_dir}")
    print(f"{'='*50}\n")

    print("→ Pushing to GitHub...")
    push_to_github(static_dir, args.slug, gh["token"], args.org)

    print("\n→ Creating Cloudflare Pages project...")
    headers, base = create_cf_pages(args.slug, args.org, cf["api_token"], cf["account_id"])

    print("\n→ Adding custom domains...")
    add_custom_domains(args.slug, args.domain, headers, base)

    print(f"\n✅ Done!")
    print(f"   Preview: https://{args.slug}.pages.dev")
    print(f"   Domain:  https://www.{args.domain}  (DNS switch still needed)")
    print(f"\nNext: switch DNS in Namecheap — see scripts/switch_dns.py")


if __name__ == '__main__':
    main()
