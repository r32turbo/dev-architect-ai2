class ArchitectState:

    def __init__(self, analyst_document=None):
        # 🔹 Embedded System Analyst Output (INPUT to Architect Agent)
        self.analyst_document = analyst_document or """
# System Analyst Output Document  
## One-Page Marketing Website (Next.js)

---

# 1. Description

The objective is to build a simple one-page marketing website using Next.js.    
The website will serve as a digital landing page that introduces the business, explains the services offered, and provides location and contact details.

The site will contain the following core sections:

- Hero Section  
- About Section  
- Services Offered Section  
- Location / Contact Section  

---

# 2. Input to the System Analyst Agent

User Goal:
Create a simple one-page marketing website with a hero section, about section, services offered section, and location section using Next.js.

Business Objective:
- Provide an online presence for the business  
- Introduce the brand to potential customers  
- Display services and contact information  

Technology Requirement:
- Framework: Next.js  

Target Users:
- Potential customers searching online  

Expected Outcome:
- Responsive one-page marketing website  

---

# 4. Website Page Structure

1. Hero Section  
2. About Section  
3. Services Section  
4. Location / Contact Section  

---

# 6. Functional Requirements

Hero Section:
- Headline, subheadline, CTA, background image  

About Section:
- Company description  

Services Section:
- Service cards (3–6 items)  

Location Section:
- Map, address, phone, email  

---

# 7. Content Source
- Static content (no database)

---

# 8. Styling
- Tailwind CSS or CSS Modules  
- Mobile-first responsive design  

---

# 9. Non-Functional Requirements
- Fast loading  
- Responsive  
- SEO optimized  
- Maintainable  

---

# 10. Constraints
- Must use Next.js  
- Single-page layout  
- Mobile + desktop support  
"""

        # 🔹 Output placeholder
        self.architecture_output = None

    def get_input(self):
        return self.analyst_document

    def set_output(self, output: str):
        self.architecture_output = output