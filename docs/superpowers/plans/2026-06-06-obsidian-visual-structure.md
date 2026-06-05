# Obsidian Visual Structure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve Obsidian's structured visualization value for stock research by adding visualization-ready Properties, cockpit-style dashboards, and explicit Excalidraw/Mind Map usage.

**Architecture:** Keep the vault as a local record DB and reuse existing Obsidian plugins. Templates define stable metadata, MOCs query and visualize that metadata, and `obsi.md` tells the recording agent how to populate fields consistently.

**Tech Stack:** Obsidian Markdown, YAML Properties, Dataview, Tasks, Mermaid, Excalidraw, Mind Map.

---

### Task 1: Extend Evidence Metadata

**Files:**
- Modify: `obsidian/stock_log/_templates/Evidence Record Template.md`
- Modify: `obsidian/stock_log/_templates/Market Radar Template.md`

- [x] **Step 1: Add visualization-ready Properties**

Add `ticker`, `name`, `theme`, `market_session`, `signal_type`, `risk_level`, `decision_state`, `linked_artifact`, and `related_notes` fields to the two templates.

- [x] **Step 2: Add visual link sections**

Add a short `Visual Links` section so each note can point to a theme map, ticker trail, source artifact, and related decision.

### Task 2: Upgrade Evidence Dashboard

**Files:**
- Modify: `obsidian/stock_log/_moc/Evidence Dashboard.md`

- [x] **Step 1: Add cockpit boards**

Add Dataview sections for today's decisions, risk hotlist, theme flow, ticker evidence trail, and after-close reconciliation tasks.

- [x] **Step 2: Keep existing evidence queries**

Preserve recent evidence and unverified evidence sections so the dashboard remains useful as an audit surface.

### Task 3: Add Market Radar Visual Flow

**Files:**
- Modify: `obsidian/stock_log/_moc/Market Radar MOC.md`

- [x] **Step 1: Add Mermaid evidence flow**

Show how `market_radar.json` moves into artifact, research facts, analysis, report, tasks, and decision journal notes.

- [x] **Step 2: Add session comparison**

Add a preopen/intraday/after-close comparison table and Dataview queries for radar signals and theme flow.

### Task 4: Update Obsi Agent Instructions

**Files:**
- Modify: `.claude/agents/obsi.md`

- [x] **Step 1: Add visual plugin responsibilities**

Document Excalidraw and Mind Map as first-class visualization tools.

- [x] **Step 2: Add visual metadata requirements**

Tell `obsi` to fill the new Properties when relevant and to link visual maps without turning them into trading instructions.

### Verification

- [x] Run `powershell -ExecutionPolicy Bypass -File .\scripts\validate_project.ps1`
- [x] Run `powershell -ExecutionPolicy Bypass -File .\tests\run_validation_tests.ps1`
