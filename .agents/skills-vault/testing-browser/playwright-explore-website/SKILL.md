---
name: playwright-explore-website
description: >-
  Use when exploring site structure, mapping accessible routes, finding
  interactive controls, and auditing links.
disable-model-invocation: true
---

# Playwright Website Exploration

Guide for automated exploration of web applications.

## Strategy

1. **Route Discovery**: Crawl internal navigation links from the AppShell / sidebar.
2. **Interactive States**: Inspect dialogs, tabs, accordions, and dropdown menus.
3. **Form Detection**: Identify inputs, validation triggers, and submission buttons.
4. **Console/Network Monitoring**: Capture console errors and failed HTTP requests during exploration.
