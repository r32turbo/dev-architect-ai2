from typing import TypedDict


class FrontendLLDState(TypedDict):
    architecture_doc: str
    final_lld: str


ARCHITECTURE_DOC = """\
Architecture Document

Title: Technical Architecture Document – One-Page Marketing Website (Next.js)

Description:
This document describes the technical architecture for a one-page marketing
website built using Next.js. The website functions as a digital landing page
presenting services, company background, and contact details. It is a
single-page responsive application with sections: Hero, About, Services,
and Location/Contact. Focus: performance, SEO, maintainability, responsive design.

Architecture Pattern : Component-Based Modular Monolithic Architecture
Application Type     : Single-Page Application (SPA)
Rendering Strategy   : Static Site Generation (SSG)

Sub Systems:
1. Presentation Layer     – Navigation, Hero, About, Services, Location/Contact, Footer
2. Content Management     – static data stored inside the application
3. Styling / UI Framework – responsive layouts, typography, mobile-first (Tailwind CSS)
4. Optimization Layer     – image optimization, metadata, SEO tags

Technology Stack:
| Technology            | Version | Purpose                  |
|-----------------------|---------|--------------------------|
| Next.js               | ^15.0   | Main web framework       |
| React                 | ^19.0   | UI component library     |
| TypeScript            | ^5.0    | Type safety              |
| Tailwind CSS          | ^4.0    | Responsive styling       |
| Node.js               | ^20.x   | Runtime environment      |
| Google Maps Embed API | Latest  | Location map integration |
| Vercel                | Latest  | Deployment platform      |

Technical Constraints:
- Must use Next.js
- Single-page vertical layout
- Images must be optimized; fast page load required
- Must support mobile, tablet, and desktop
- All content initially static within the application
- Services section: minimum 3, maximum 6 items
- Proper HTML structure and metadata required for SEO
"""