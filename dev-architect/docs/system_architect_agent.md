# System Architect Agent

## Overview
Overview
The System Architect Agent converts functional and non-functional requirements into a high-level technical blueprint. It defines the structural "skeleton" of the application, serving as the bridge between the System Analyst Agent (Requirements) and the System Design Agent (Detailed implementation).
Input
The agent consumes the Software Requirement Specification (SRS) from the System Analyst.

## Detailed Input Requirements:

User Personas: Who is using the system (e.g., Admin, Customer).

Core Feature Set: Functional requirements (e.g., Real-time chat, Auth).

Non-Functional Requirements (NFRs): Latency limits, expected concurrent users, and security compliance (e.g., GDPR).

Business Constraints: Budget, preferred cloud providers, or legacy system integrations.

## Goal of the Agent
To establish a scalable, secure, and cost-effective structural design. The agent is responsible for:

Selecting the Architectural Pattern (e.g., Microservices vs. Monolith).

Defining the Technology Stack (Languages, Frameworks, Databases).

Mapping High-Level Data Flow between services.

Ensuring the system can meet the NFRs defined by the Analyst.

## Output
The agent produces a System Architecture Definition, providing the Design Agent with:

Architectural Style: (e.g., "Event-Driven Microservices").

Tech Stack: Specific versions (e.g., "Python 3.12 with FastAPI", "PostgreSQL 16").

Communication Interface: (e.g., "RESTful APIs with JWT Authentication").

Infrastructure Strategy: (e.g., "Containerized via Docker, orchestrated by Kubernetes on AWS").

External Integrations: (e.g., "Stripe for payments", "OpenAI for LLM").

## Pipeline Position
System Analyst Agent (The "What")

↓

System Architect Agent (The "How - High Level")

↓

System Design Agent (The "How - Low Level/Detailed")