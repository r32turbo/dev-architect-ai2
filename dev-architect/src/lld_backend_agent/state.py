"""
state.py – Input state for Backend LLD Agent
"""

from typing import TypedDict


class BackendLLDState(TypedDict, total=False):
    lld_input: str
    backend_output: str


# ---------- FINAL INPUT FOR LLD AGENT ----------
LLD_INPUT = """
### USER INPUT:
Create a one-page marketing website using Next.js with:
- Hero section
- About section
- Services section
- Location/contact section


### REQUIREMENTS:

- Functional Requirements:
  - Hero section with headline and CTA
  - About section (company description)
  - Services section (3–6 services)
  - Location/contact section with map

- Non-Functional Requirements:
  - Fast loading
  - Responsive design
  - SEO optimized
  - Maintainable code

- Constraints:
  - Use Next.js
  - Single-page layout
  - Static content (no DB)


### ARCHITECTURE:

- Architecture Type: Single Page Application (SPA)
- Frontend: Next.js
- Styling: Tailwind CSS
- External Integration: Google Maps API

- Subsystem:
  - Frontend handles UI rendering and navigation

- Constraints:
  - Load under 3 seconds
  - Mobile responsiveness
"""
 