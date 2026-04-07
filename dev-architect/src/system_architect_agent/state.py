ARCH_INPUT = """
# System Analyst Output Document
## One-Page Marketing Website (Next.js)

Description:
Simple one-page marketing website.

Sections:
- Hero
- About
- Services
- Contact

Constraints:
- Next.js
- Static content
"""

class ArchitectState:

    def __init__(self, analyst_document):
        self.analyst_document = analyst_document
        self.architecture_output = None
