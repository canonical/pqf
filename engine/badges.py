"""
Badge generator: produces shields.io-compatible SVG badges for each product.

Usage:
    python engine/badges.py \
        --portfolio public/portfolio.json \
        --output-dir public/badges/
"""

import argparse
import json
import sys
from pathlib import Path

_COLORS: dict[str, str] = {
    "gold": "#FFB700",
    "silver": "#9E9E9E",
    "bronze": "#CD7F32",
    "unrated": "#9F9F9F",
    "below_minimum": "#9F9F9F",
    "insufficient_data": "#9F9F9F",
    "not_applicable": "#9F9F9F",
}


def badge_state(product_entry: dict) -> str:
    """Return the display state for a product's badge."""
    return product_entry.get("current_result", product_entry.get("current_medal", "unrated"))


def generate_badge(product_entry: dict) -> str:
    """Generate a shields.io-compatible SVG badge for a product."""
    state = badge_state(product_entry)
    color = _COLORS.get(state, _COLORS["unrated"])
    label = "quality"
    value = state

    label_width = 55
    value_width = max(len(value) * 7 + 10, 40)
    total_width = label_width + value_width
    label_mid = label_width // 2
    value_mid = label_width + value_width // 2

    svg_content = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="20" '
        f'role="img" aria-label="{label}: {value}">\n'
        f"  <title>{label}: {value}</title>\n"
        f'  <linearGradient id="s" x2="0" y2="100%">\n'
        f'    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>\n'
        f'    <stop offset="1" stop-opacity=".1"/>\n'
        f"  </linearGradient>\n"
        f'  <clipPath id="r">\n'
        f'    <rect width="{total_width}" height="20" rx="3" fill="#fff"/>\n'
        f"  </clipPath>\n"
        f'  <g clip-path="url(#r)">\n'
        f'    <rect width="{label_width}" height="20" fill="#555"/>\n'
        f'    <rect x="{label_width}" width="{value_width}" height="20" fill="{color}"/>\n'
        f'    <rect width="{total_width}" height="20" fill="url(#s)"/>\n'
        f"  </g>\n"
        f'  <g fill="#fff" text-anchor="middle" '
        f'font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">\n'
        f'    <text x="{label_mid}" y="15" fill="#010101" fill-opacity=".3">{label}</text>\n'
        f'    <text x="{label_mid}" y="14">{label}</text>\n'
        f'    <text x="{value_mid}" y="15" fill="#010101" fill-opacity=".3">{value}</text>\n'
        f'    <text x="{value_mid}" y="14">{value}</text>\n'
        f"  </g>\n"
        f"</svg>"
    )
    return svg_content


def main() -> int:
    parser = argparse.ArgumentParser(description="PQF badge generator")
    parser.add_argument("--portfolio", required=True, help="Path to active public/portfolio.json")
    parser.add_argument("--output-dir", required=True, help="Directory for badge SVG files")
    args = parser.parse_args()

    portfolio = json.loads(Path(args.portfolio).read_text())
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for product in portfolio.get("products", []):
        product_id = product["id"]
        svg = generate_badge(product)
        out_path = output_dir / f"{product_id}-medal.svg"
        out_path.write_text(svg)
        print(f"wrote {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
