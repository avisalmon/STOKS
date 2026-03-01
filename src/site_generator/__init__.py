"""
Static site generator package.

Generates index.html + per-ticker detail pages + methodology page.
All output is self-contained HTML/CSS/JS for GitHub Pages.
"""

from src.site_generator.generator import generate_site

__all__ = ["generate_site"]
