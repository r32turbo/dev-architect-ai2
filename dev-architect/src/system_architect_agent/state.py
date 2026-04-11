class ArchitectState:

    def __init__(self):
        # 🔹 System Analyst Output (INPUT)
        self.analyst_document = """
# System Analyst Output Document  
## One-Page Marketing Website (Next.js)

# Description
The objective is to build a simple one-page marketing website using Next.js.
The website will include Hero, About, Services, and Contact sections.

# Functional Requirements
- Hero section with CTA
- About section
- Services section (3–6 services)
- Location/contact section with map

# Non-Functional Requirements
- Fast loading
- Responsive design
- SEO optimized
- Maintainable

# Constraints
- Must use Next.js
- Single-page layout
"""

        # 🔹 Output
        self.architecture_output = None

    def get_input(self):
        return self.analyst_document

    def set_output(self, output: str):
        self.architecture_output = output