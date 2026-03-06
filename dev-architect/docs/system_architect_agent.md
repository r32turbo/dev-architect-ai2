# System Architect Agent

## Overview
The System Architect Agent converts system requirements into a high-level technical architecture.  
It acts as the bridge between the **System Analyst Agent** and the **System Design Agent**.

---

## Input

The agent receives system requirements from the System Analyst Agent.

Example input:

{
  "project": "AI Chatbot",
  "users": ["customer", "admin"],
  "features": ["chat", "knowledge search"],
  "non_functional_requirements": ["scalable", "secure"]
}

---

## Goal of the Agent

The goal of the System Architect Agent is to design the overall system architecture by selecting:

- Technology stack
- Backend framework
- Frontend framework
- Database
- Deployment infrastructure
- Integration services

---

## Output

The agent produces a structured architecture plan.

Example output:

Frontend: React.js  
Backend: FastAPI  
Database: PostgreSQL  
AI Services: LLM API + Vector Database  
Deployment: Docker + Google Cloud Platform

---

## Pipeline Position

System Analyst Agent  
↓  
System Architect Agent  
↓  
System Design Agent