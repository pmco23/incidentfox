#!/usr/bin/env python3
"""Get the full content of a Confluence page.

Usage:
    python get_page.py --page-id PAGE_ID
    python get_page.py --title "Page Title" --space SPACE_KEY

Examples:
    python get_page.py --page-id 123456789
    python get_page.py --title "Payment Service Runbook" --space SRE
"""

import argparse
import json
import sys
from html.parser import HTMLParser

from confluence_client import get_page_by_id, search_content


class HTMLToText(HTMLParser):
    """Simple HTML to text converter."""

    def __init__(self):
        super().__init__()
        self.text = []

    def handle_data(self, data):
        self.text.append(data)

    def get_text(self):
        return "".join(self.text)


def html_to_text(html: str) -> str:
    """Convert HTML to plain text."""
    parser = HTMLToText()
    parser.feed(html)
    return parser.get_text()


def main():
    parser = argparse.ArgumentParser(
        description="Get the full content of a Confluence page"
    )
    parser.add_argument(
        "--page-id",
        help="Page ID",
    )
    parser.add_argument(
        "--title",
        help="Page title (requires --space)",
    )
    parser.add_argument(
        "--space",
        help="Space key (required with --title)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    parser.add_argument(
        "--raw-html",
        action="store_true",
        help="Show raw HTML content instead of plain text",
    )
    args = parser.parse_args()

    if not args.page_id and not (args.title and args.space):
        print(
            "❌ Error: Must provide --page-id or (--title and --space)",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        # Get page
        if args.page_id:
            page = get_page_by_id(args.page_id)
        else:
            # Search by title and space
            cql = f'title = "{args.title}" AND space = "{args.space}" AND type = page'
            results = search_content(cql=cql, limit=1)

            if not results.get("results"):
                print(
                    f"❌ Error: Page not found: {args.title} in space {args.space}",
                    file=sys.stderr,
                )
                sys.exit(1)

            page_id = results["results"][0]["id"]
            page = get_page_by_id(page_id)

        # Extract content
        body = page.get("body", {})
        storage = body.get("storage", {})
        html_content = storage.get("value", "")

        # Convert to text unless raw HTML requested
        if args.raw_html:
            content = html_content
        else:
            content = html_to_text(html_content)

        # Output
        if args.json:
            output = {
                "id": page.get("id"),
                "title": page.get("title"),
                "space": page.get("spaceId"),
                "content": content,
                "url": page.get("_links", {}).get("webui"),
                "version": page.get("version", {}).get("number"),
                "created": page.get("createdAt"),
                "updated": page.get("lastUpdated"),
            }
            print(json.dumps(output, indent=2))
        else:
            print(f"\n📄 {page.get('title')}")
            print(f"   ID: {page.get('id')}")
            if page.get("spaceId"):
                print(f"   Space: {page.get('spaceId')}")
            if page.get("_links", {}).get("webui"):
                print(f"   URL: {page.get('_links', {}).get('webui')}")
            if page.get("version", {}).get("number"):
                print(f"   Version: {page.get('version', {}).get('number')}")
            if page.get("lastUpdated"):
                print(f"   Last Updated: {page.get('lastUpdated')}")
            print("\n" + "=" * 80)
            print(content)
            print("=" * 80 + "\n")

    except Exception as e:
        print(f"❌ Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
