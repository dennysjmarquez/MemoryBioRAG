---
name: biorag-memory
description: Use BioRAG's persistent local memory through its configured MCP server or command-line interface when prior user or project context is relevant.
---

# BioRAG Memory Skill

## Purpose

BioRAG provides persistent, local memory tools to an AI agent. The host agent remains responsible for reasoning and composing the answer; BioRAG stores and retrieves context.

## Operating rules

1. Search memory when a request depends on earlier project decisions, durable facts, or user preferences and BioRAG is available.
2. Treat retrieved records as evidence, not as unquestionable truth. Check dates and conflicts, and tell the user when the memory is missing or ambiguous.
3. Store information only when the user asks or clearly approves a durable update. Do not save credentials, tokens, passwords, private databases, or unrelated personal information.
4. Create associations only when the relationship is meaningful. Do not run write or consolidation operations just to satisfy a routine.
5. If BioRAG is unavailable, continue without it and do not invent a memory result.

## MCP tools

When the BioRAG MCP server is configured, use the tools exposed by that server. Common operations include `recordar` or `buscar` for retrieval, `aprender` for an explicit durable write, `vincular` for a meaningful association, and `estado` for a status check. Tool names and arguments are defined by the server; inspect its current tool descriptions rather than guessing parameters.

## Command-line fallback

From the cloned Stable repository, run `python biorag.py help` for the full command reference. The CLI includes search, write, association, listing, status, and consolidation commands. Do not put secrets or private evaluation data into example memories.

## Installation location

The installer copies this file to supported agent skill directories. The source copy remains at `skills/biorag-memory/SKILL.md` in the repository. Common installed locations include `~/.claude/skills/biorag-memory/SKILL.md`, `~/.config/opencode/skills/biorag-memory/SKILL.md`, and `~/.agents/skills/biorag-memory/SKILL.md`.

This file is an agent instruction document; copying it does not run code or grant permission to read or write memory.
