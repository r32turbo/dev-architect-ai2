from typing import TypedDict


class LLDAgentState(TypedDict):
    lld_input: str
    requirement_doc: str
    architecture_doc: str
    sections: str
    architecture_analysis: str
    final_report: str


LLD_INPUT = """# Low Level Design (LLD) Document
## Introduction
This document provides a detailed Low Level Design (LLD) for a one-page marketing website built using Next.js. The website will function as a digital landing page for a business, presenting key information such as services offered, company background, and contact details.

## Module & Component Specifications
The website will consist of the following modules and components:

* **Presentation Layer (User Interface)**
    + Navigation Component
    + Hero Component
    + About Component
    + Services Component
    + Location / Contact Component
    + Footer Component
* **Content Management Layer**
    + Content Store (static data)
* **Styling and UI Framework Layer**
    + Responsive Layouts
    + Typography and Spacing
    + Mobile-first Styling
* **Optimization and Performance Layer**
    + Image Optimization
    + Metadata Management
    + SEO Tags
    + Performance Optimization

## Component Hierarchy
The component hierarchy for the website is as follows:

* **App**
    + **Navigation**
    + **Hero**
    + **About**
    + **Services**
    + **Location / Contact**
    + **Footer**
* **Services**
    + **Service Card** (minimum 3, maximum 6)

## TypeScript Interfaces
The following TypeScript interfaces will be used to define the structure of the data:

* **Service**
```typescript
interface Service {
  id: number;
  title: string;
  description: string;
}
```
* **Company**
```typescript
interface Company {
  name: string;
  description: string;
  address: string;
}
```
* **Contact**
```typescript
interface Contact {
  email: string;
  phone: string;
  address: string;
}
```
* **Metadata**
```typescript
interface Metadata {
  title: string;
  description: string;
  keywords: string[];
}
```

## Data Models
The following data models will be used to store data:

* **Content Store**
    + Services: array of Service objects
    + Company: Company object
    + Contact: Contact object
    + Metadata: Metadata object

## Logic and Algorithms
The following logic and algorithms will be used:

* **Image Optimization**: images will be optimized using a library such as `sharp` to reduce file size and improve page load times.
* **Metadata Management**: metadata will be generated dynamically based on the content of the page.
* **SEO Tags**: SEO tags will be added to the page to improve search engine optimization.
* **Performance Optimization**: the website will be optimized for performance using techniques such as code splitting, lazy loading, and caching.

## API Design
The following APIs will be used:

* **Google Maps Embed API**: used to embed a map on the location/contact page.

## Styling System
The following styling system will be used:

* **Tailwind CSS**: used to create responsive, mobile-first layouts.
* **Typography and Spacing**: typography and spacing will be consistent throughout the website.

## Error Handling
The following error handling mechanisms will be used:

* **Try/Catch Blocks**: used to catch and handle errors in the code.
* **Error Boundaries**: used to catch and handle errors in the React components.
* **Logging**: errors will be logged to the console for debugging purposes.

## Technology Stack
The following technology stack will be used:

* **Next.js**: used as the main web framework.
* **React**: used as the UI component library.
* **TypeScript**: used for type safety and maintainability.
* **Tailwind CSS**: used for responsive styling.
* **Node.js**: used as the runtime environment.
* **Google Maps Embed API**: used for location map integration.
* **Vercel**: used as the deployment platform.

## Conclusion
This Low Level Design document provides a detailed overview of the architecture and design of the one-page marketing website. It covers the module and component specifications, component hierarchy, TypeScript interfaces, data models, logic and algorithms, API design, styling system, and error handling mechanisms. The technology stack used for the project is also outlined.
"""
