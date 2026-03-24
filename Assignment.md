# Forward Deployed Engineer - Task Details

Graph-Based Data Modeling and Query System

---

## Overview

In real-world business systems, data is spread across multiple tables : orders, deliveries, invoices, and payments, without a clear way to trace how they connect.

In this assignment, you will unify this fragmented data into a graph and build a system that allows users to explore and query these relationships using natural language.

---

## What You Are Building

You are building a **context graph system with an LLM-powered query interface**. Below is a sample interface for reference:

![image.png](attachment:d2115179-3451-4ea5-9a91-1a35308b5806:image.png)

![Query.png](attachment:d938e2e3-7204-4379-8a8a-738af3df53fd:Query.png)

At a high level:

- The dataset is converted into a **graph of interconnected entities**
- This graph is **visualized in a UI**
- A **chat interface sits alongside the graph**
- The user asks questions in natural language
- The system translates those questions into **structured queries (such as SQL) dynamically**
- The system executes those queries and returns **data-backed answers in natural language**

This is not a static Q&A system. The LLM should interpret user queries, generate structured queries dynamically, and return data-backed answers.

---

## Dataset

First, please download this dataset:

https://drive.google.com/file/d/1UqaLbFaveV-3MEuiUrzKydhKmkeC1iAL/view?usp=sharing

The dataset includes entities such as:

### Core Flow

- Orders
- Deliveries
- Invoices
- Payments

### Supporting Entities

- Customers
- Products
- Address

You are free to preprocess, normalize, or restructure the dataset as required.

---

## Functional Requirements

### 1. Graph Construction

Ingest the dataset and construct a graph representation.

You must define:

- Nodes representing business entities
- Edges representing relationships between entities

Examples of relationships:

- Purchase Order → Purchase Order Item
- Delivery → Plant
- Purchase Order Item → Material
- Customer → Delivery

The focus is on how you model the system, not just loading data.

---

### 2. Graph Visualization

Build an interface that allows users to explore the graph.

The interface should support:

- Expanding nodes
- Inspecting node metadata
- Viewing relationships between entities

A simple and clean implementation is sufficient.

You may use any visualization library of your choice.

---

### 3. Conversational Query Interface

Build a chat interface that allows users to query the system.

The system should:

- Accept natural language queries
- Translate queries into structured operations on the graph or underlying data
- Return accurate and relevant responses

The responses must be grounded in the dataset and not generated without data backing.

---

### 4. Example Queries

Your system should be capable of answering questions such as:

a. Which products are associated with the highest number of billing documents?

b. Trace the full flow of a given billing document (Sales Order → Delivery → Billing → Journal Entry)

c. Identify sales orders that have broken or incomplete flows (e.g. delivered but not billed, billed without delivery)

You are encouraged to go beyond these examples and explore additional meaningful queries based on your understanding of the dataset.

---

### 5. Guardrails

The system must restrict queries to the dataset and domain.

It should appropriately handle or reject unrelated prompts such as:

- General knowledge questions
- Creative writing requests
- Irrelevant topics

Example response:

"This system is designed to answer questions related to the provided dataset only."

This is an important evaluation criterion.

---

## Optional Extensions (Bonus)

- Natural language to SQL or graph query translation
- Highlighting nodes referenced in responses
- Semantic or hybrid search over entities
- Streaming responses from the LLM
- Conversation memory
- Graph clustering or advanced graph analysis

Depth in one or two functionalities is preferred over implementing many superficially.

---

# **LLM APIs : Use Free Tiers**

You don’t need to spend money on this.

Several providers offer free access with reasonable limits.

| **Provider** | **Link** |
| --- | --- |
| Google Gemini | [https://ai.google.dev](https://ai.google.dev/) |
| Groq | [https://console.groq.com](https://console.groq.com/) |
| OpenRouter | [https://openrouter.ai](https://openrouter.ai/) |
| HuggingFace | https://huggingface.co/inference-api |
| Cohere | [https://cohere.com](https://cohere.com/) |

---

# **Submission Requirements**

In order to record your submission

- A **working demo link**
- A **public GitHub repository**
- A **README** explaining architecture decisions, database choice, LLM prompting strategy, and guardrails
- **AI coding session logs** from tools such as Cursor, Claude Code, Copilot, etc.
- The UI can be simple.
- **No authentication is required.** Ensure the implementation is accessible via the provided link.

> We will be evaluating your architectural decisions, your reasoning, and how effectively you use AI to arrive at them.
> 

---

# **Share Your AI Coding Sessions**

We expect candidates to actively use AI tools as part of this assignment.

We’re interested in understanding **how you work with AI**, not just the final output.

If you’re using tools such as:

- Cursor
- Claude Code
- GitHub Copilot
- Windsurf
- Continue.dev

Please include your **session logs or transcripts**.

### **Examples:**

**Cursor →** Export your **Composer / chat history / Export Transcript** as markdown

**Claude Code** → Include transcripts from: **~/.claude/projects/**

**Other tools** → Provide any logs in a markdown / .txt format

*Note: If you’re using multiple tools, **provide the transcripts for each** of them and bundle them in to a .ZIP file*

We’re evaluating:

- prompt quality
- debugging workflow
- iteration patterns

---

## Evaluation Criteria

| Area | What We Are Evaluating |
| --- | --- |
| Code quality and architecture | Structure, readability, and maintainability |
| Graph modelling | Quality and clarity of entities and relationships |
| Database / storage choice | Architectural decisions and tradeoffs |
| LLM integration and prompting | How natural language is translated into useful queries |
| Guardrails | Ability to restrict misuse and off-topic prompts |

---

## Timeline

The submission deadline is **26 March, 11:59 PM IST**.

We do consider **speed of execution** as part of the evaluation.

As a rough benchmark, strong submissions usually come from candidates who are able to put in **~3-4 hours of focused work per day** and move quickly.

---

### Submission

> Please fill the following form with link to the **working demo link and GitHub repository:** 
https://forms.gle/sPDBUvA45cUM3dyc8
> 

---

Thanks!




# Forward Deployed Engineer @ Dodge AI

## The Mission

Dodge AI is building the enterprise automation platform for ERP. Every year, over $100B is spent on consultants to maintain legacy ERP systems. We are starting by helping enterprise IT/AMS (Application Managed Services) teams automate incident management and configuration across complex SAP landscapes, enabling them to reduce maintenance costs and improve system reliability at scale. This is our first wedge toward a broader vision of enterprise-wide, AI-powered ERP automation.

Today, our platform automates L1/L2 ERP support, helping reduce resolution times and consulting hours, while also auditing configs and accelerating service delivery.

We're Tier-1 VC-backed, live with customers (Fortune 500s), and moving fast. If you're excited to build with real users, solve hard technical problems, and shape the future of ERP, we’d like to chat.

## About The Role

![image.png](attachment:dbe33b3e-087e-4d5a-a6f5-65578cdf672c:image.png)

End-to-end ownership of customer-critical ERP projects, embedded close to real ERP environments, with direct impact on product direction.

This is not a traditional support or consulting role. Forward deployed engineering is about shipping inside the customer’s ecosystem, then feeding what you learn back into the core platform so it scales beyond a single account.

You will be the tip of the spear, and your work will directly shape the product.

You will embed close to customer ERP teams to understand incident flows, operational constraints, and how work actually happens, then own deployments end to end from discovery and integration to rollout and expansion, including the messy last mile. You will build secure, reliable integrations that connect complex ERP landscapes to our platform, create structure in ambiguous ticket flows by defining triage logic and repeatable resolution playbooks, and partner with SAP SMEs and IT stakeholders to turn high-level goals into execution. 

If you like high ownership, fast feedback loops, and building systems that actually hold up in production, this role will feel natural.

## What We’re Looking For

- You’re a full-stack 0-to-1 builder who has shipped to production.
- You enjoy being customer-facing, and you can earn trust by being the person who delivers.
- You have a genuine curiosity about agentic product experiences and are excited about understanding the impact of AI on Systems of Record.
- You have strong judgement under ambiguity. You know when to hack a workaround, and when to fix the root cause.
- You communicate clearly and directly. You can explain tradeoffs to both engineers and ops stakeholders.
- You have grit. You should be accustomed to picking between hard options and pushing through it.
- We care more about trajectory, ownership and bias to action than specific labels on your resume.

## Non-Negotiable Skills

- Owning customer deployments end to end: discovery, integration, rollout, and expansion
- Writing clean, maintainable code across backend, frontend, and data layers
- Designing APIs and data models that are simple, robust, and easy to extend
- Debugging ambiguous, high stakes issues across customer systems and our stack, using logs, traces, and structured incident response to get to root cause fast
- Instrumenting systems with logs, metrics, and traces to understand behavior in production
- Building customer enablement tooling: deployment runbooks, rollout checklists, triage consoles, and lightweight dashboards that make adoption and operations repeatable
- Working with production data stores and writing non trivial queries to diagnose issues, validate outcomes, and measure impact in customer environments
- Using modern Git workflows, CI, and automated tests as part of your everyday practice
- Working comfortably with cloud infrastructure, containers, and basic networking concepts
- Participating in code reviews and raising the standard for code quality on the team

## Good To Have Skills

- Experience working with ERP support, AMS teams, or IT operations workflows
- Familiarity with SAP landscapes and the realities of enterprise change management
- Building secure integrations and data pipelines in regulated environments
- Translating messy, customer-specific workflows into repeatable product primitives
- Designing human-in-the-loop workflows that combine automation with expert feedback
- Designing practical data flows and instrumentation needed to support deployments, incident forensics, and product feedback loops
- Comfort operating in systems that need strong compliance posture (we are SOC 2 Type 1 and working toward Type 2).

## Ideal Profile

We’re looking for people who picked something hard, went all in on it, and ended up somewhere most others do not (Top 1%).

Some Examples (*none of these are requirements*):

- Founder or founding engineer at an early stage startup with real users, revenue, or venture backing
- Standout open source contributions (for example GSoC, LFX, or widely used projects)
- Someone who has built complex systems from scratch that people actually pay for.

Share something you have done that makes you feel exceptional. The examples above are only suggestions and not the only ways to stand out.

## This *IS NOT* For You If

- You're not based in HSR, Bengaluru (or you’re not willing to relocate)
- You’re not willing to work 6 days per week (we take Sundays off)
- You’re not excited about using code-gen tools like Cursor, Codex, Claude Code, etc.
- You’re not comfortable deleting 80% to 90% of the code that you write
- You’re not comfortable being deeply customer-facing and context switching hard
- You don’t like candour, receiving and giving direct, honest feedback
- You need a well defined structure or career ladder

## Compensation

📍 On-site Role (HSR, Bengaluru)

💼 6 days a week (Monday-Saturday)

- Internship (Pre-Final Year or Final Year)
    - ₹80k–₹1L/month stipend (*on-site, negotiable for exceptional candidates*)
    
- Full-Time (0-2 YoE)
    - ₹15L-30L CTC (*on-site*)

## Benefits

- **Competitive Pay & Early Equity:** Be rewarded for the value you create as we grow.
- **Founding Team Impact:** Help define our culture, product, and technology from the ground up.
- **Work on Real AI Automation:** Build a platform that solves meaningful problems with cutting-edge AI and automation.
- **Customer-first Ownership:** See your work used and loved by real users from day one.
- **In-person Collaboration:** We believe the best teams build faster together. We work in person in Bengaluru (India) & San Francisco (USA).

## Life at Dodge AI

- Meal subscription so you do not have to worry about food on busy days
- Gym subscription to make it easier to stay healthy while you build
- Monthly team lunches to get out of the office and reset together
- Regular team socials and outings to keep the team close and have fun outside work

## Apply Here