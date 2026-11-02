# Agents' memory

This repository contains the agent-memory work from the Paytm Hackathon.
Agent memory is the data that an AI agent keeps between conversations.
The three projects show how saved memory changes the behavior of an agent.

## Projects

| Folder | Content |
|---|---|
| [Demo-Day](Demo-Day/README.md) | A persistent user-memory service. It uses LangGraph, PostgreSQL with pgvector, and OpenAI. All four demonstration gates passed. |
| [memory-policy-lab](memory-policy-lab/README.md) | An experiment that applies read and write rules to agent memory. It includes an [interactive demo](memory-policy-lab/runs/demo.html). |
| [memory-checkpoint-demo](memory-checkpoint-demo/README.md) | A small chatbot. It compares one conversation with saved state and one conversation without saved state. |

## Start here

1. Read the [Demo-Day PRD](Demo-Day/spec-persistent-memory-prd.md). A PRD (product requirements document) gives the product requirements.
2. Read the [Demo-Day test plan](Demo-Day/eval-persistent-memory-test-plan.md).
3. Follow the [local setup guide](Demo-Day/docs/guide-local-setup.md).
4. Use the [four-demo guide](Demo-Day/docs/guide-four-demos.md) to run the demonstrations.

## Secrets

Each project reads its API key from a local `.env` file.
Copy `.env.example` to `.env` in the project folder.
Then add your own OpenAI API key.
Do not commit the `.env` file.

## Content that is not in this repository

The presentation and the design reference stay on the local computer.
The presentation contains personal photographs and third-party branding.
The Chapter 10 source notebooks belong to a third party.
The documents identify these notebooks by file name and cell number only.
