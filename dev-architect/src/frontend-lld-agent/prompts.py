import importlib
from configuration import register_agent_adk

register_agent_adk()

PromptBuilder = importlib.import_module("reusableagents.prompts.base").PromptBuilder


LLD_PROMPT = (
    PromptBuilder()
    .add_system(
        "You are a senior frontend software architect and technical writer.\n"
        "Generate a detailed, developer-ready Low-Level Design (LLD) document.\n"
        "Use markdown with clear headings, tables, and TypeScript code blocks.\n"
        "Be specific and actionable — no vague statements.",
        name="persona",
    )
    .add_user("{task}", name="task")
)

LLD_TASK = """\
Generate a complete Low-Level Design (LLD) document for the architecture below.
The document MUST contain exactly these 6 sections:

### 1. Module & Component Specifications
- Architecture pattern: Component-Based Modular Monolithic
- Component hierarchy:
  - Root Layout (layout.tsx)
    - Navbar Component (Fixed position)
    - Main Page (page.tsx)
      - Hero Section
      - About Section
      - Services Section → ServiceCard (x3-6)
      - Location Section → MapDisplay, ContactDetails
    - Footer Component
- TypeScript interfaces: NavItem, ServiceCardProps, ContactProps
- State: isMenuOpen (boolean), useActiveSection hook (Intersection Observer)

### 2. Data Models & Schema
- SITE_DATA constant in src/constants/siteData.ts
- Static asset path: /public/images/, naming: section-name-description.webp
- Icons: lucide-react

### 3. Detailed Logic & Algorithms
- Smooth scrolling: CSS scroll-behavior: smooth
- Navbar offset via JS scroll calculation
- Next.js Image: priority on Hero (LCP), width/height on icons (CLS)
- SSG pre-rendering at build time

### 4. API & Integration Design
- Google Maps Embed: iframe + geo: URI for mobile click-to-navigate
- Optional contact form: POST /api/contact with name, email, message

### 5. Visual & Styling System
- Tailwind CSS 4.0, mobile-first
- Breakpoints table: sm 640px, md 768px, lg 1024px
- Design tokens: Geist font, high-contrast Hero overlays

### 6. Error Handling & Edge Cases
- 404: custom not-found.tsx
- Map loading: SVG skeleton loader
- Image fallback: onError in ServiceCard
- SEO: metadata in layout.tsx (title, description, openGraph)

Architecture Document:
{architecture_doc}

Write every section in full with TypeScript code blocks and tables.
"""