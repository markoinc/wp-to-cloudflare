#!/usr/bin/env python3
"""
switch_dns.py — Switch domain DNS to Namecheap BasicDNS and point to Cloudflare Pages.

Usage:
    python3 switch_dns.py <domain> <cf-pages-slug>

Example:
    python3 switch_dns.py mysite.com my-pages-slug

Requires: ~/.config/namecheap/credentials.json
    {"api_user": "...", "api_key": "...", "username": "...", "client_ip": "..."}

Security note: Namecheap API sends credentials as GET query params (their design).
Run only on trusted networks — API key will appear in server/proxy access logs.
The client_ip must be whitelisted in Namecheap → Profile → Tools → API Access.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

import requests

DOMAIN_RE = re.compile(r'^[a-z0-9][a-z0-9\-\.]{1,253}[a-z0-9]$')
SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9\-]{0,62}$')


def validate_inputs(domain, slug):
    if not DOMAIN_RE.match(domain.lower()):
        print(f"ERROR: Invalid domain '{domain}'")
        sys.exit(1)
    if not SLUG_RE.match(slug.lower()):
        print(f"ERROR: Invalid CF slug '{slug}'")
        sys.exit(1)


def load_json(path):
    p = Path(path).expanduser()
    if not p.exists():
        print(f"ERROR: Credentials not found at {p}")
        sys.exit(1)
    return json.loads(p.read_text())


def nc_request(nc, command, extra_params=None):
    base = "https://api.namecheap.com/xml.response"
    params = {
        "ApiUser": nc["api_user"],
        "ApiKey": nc["api_key"],
        "UserName": nc["username"],
        "ClientIp": nc["client_ip"],
        "Command": command,
    }
    if extra_params:
        params.update(extra_params)
    r = requests.get(base, params=params)
    tree = ET.fromstring(r.text)
    status = tree.get("Status")
    errors = tree.findall(".//{http://api.namecheap.com/xml.response}Error")
    return status, errors, tree, r.text


def split_domain(domain):
    """Split domain into SLD/TLD, handling common multi-part TLDs."""
    # Common two-part TLDs — extend as needed
    TWO_PART_TLDS = {
        'co.uk', 'co.nz', 'co.za', 'co.jp', 'co.in', 'co.au',
        'com.au', 'com.br', 'com.mx', 'com.ar', 'com.sg',
        'org.uk', 'net.au', 'net.nz',
    }
    parts = domain.lower().split('.')
    if len(parts) >= 3:
        possible_two_part = '.'.join(parts[-2:])
        if possible_two_part in TWO_PART_TLDS:
            return '.'.join(parts[:-2]), possible_two_part
    if len(parts) >= 2:
        return '.'.join(parts[:-1]), parts[-1]
    print(f"ERROR: Cannot parse domain '{domain}'")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description='Switch domain DNS to Cloudflare Pages via Namecheap')
    parser.add_argument('domain', help='Domain name (e.g. example.com)')
    parser.add_argument('cf_slug', help='Cloudflare Pages project slug (e.g. example)')
    parser.add_argument('--skip-ns-switch', action='store_true',
                        help='Skip switching to Namecheap BasicDNS (if already on Namecheap)')
    args = parser.parse_args()

    validate_inputs(args.domain, args.cf_slug)

    nc = load_json("~/.config/namecheap/credentials.json")
    sld, tld = split_domain(args.domain)

    print(f"\nDomain: {args.domain}  (SLD={sld}, TLD={tld})")
    print(f"CF Pages target: {args.cf_slug}.pages.dev\n")

    # Step 1: Check current NS
    status, errors, tree, raw = nc_request(nc, "namecheap.domains.dns.getList",
                                           {"SLD": sld, "TLD": tld})
    ns_result = tree.find(".//{http://api.namecheap.com/xml.response}DomainDNSGetListResult")
    using_own = ns_result.get("IsUsingOurDNS") if ns_result is not None else "unknown"
    print(f"Using Namecheap DNS: {using_own}")

    # Step 2: Switch to BasicDNS if needed
    if using_own == "false" and not args.skip_ns_switch:
        print("→ Switching to Namecheap BasicDNS...")
        status, errors, _, _ = nc_request(nc, "namecheap.domains.dns.setDefault",
                                          {"SLD": sld, "TLD": tld})
        if status == "OK":
            print("  Switched ✓")
        else:
            for e in errors:
                print(f"  ERROR: {e.text}")
            sys.exit(1)
    else:
        print("  Already on Namecheap BasicDNS — skipping NS switch")

    # Step 3: Set DNS records
    print(f"\n→ Setting DNS records...")
    print(f"  www CNAME → {args.cf_slug}.pages.dev")
    print(f"  @   URL   → https://www.{args.domain}")

    status, errors, _, raw = nc_request(nc, "namecheap.domains.dns.setHosts", {
        "SLD": sld,
        "TLD": tld,
        "HostName1": "www",
        "RecordType1": "CNAME",
        "Address1": f"{args.cf_slug}.pages.dev",
        "TTL1": "300",
        "HostName2": "@",
        "RecordType2": "URL",
        "Address2": f"https://www.{args.domain}",
        "TTL2": "300",
    })

    if status == "OK":
        print("  DNS records set ✓")
    else:
        for e in errors:
            print(f"  ERROR: {e.text}")
        sys.exit(1)

    # Step 4: Verify — using list form to prevent injection
    result = subprocess.run(
        ["dig", f"www.{args.domain}", "CNAME", "+short"],
        capture_output=True, text=True
    )
    cname = result.stdout.strip()
    if cname:
        print(f"\n✅ DNS propagating: www.{args.domain} → {cname}")
    else:
        print(f"\n⏳ DNS not yet propagated (normal — can take 1–30 min)")
        print(f"   Run: dig www.{args.domain} CNAME +short")

    print(f"\nNext: verify SSL at https://www.{args.domain}")


if __name__ == '__main__':
    main()
