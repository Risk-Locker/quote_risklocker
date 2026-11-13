---
name: playwright-automation-fill-in-form
description: >-
  Use when automating form input sequences, multi-step wizards, file uploads,
  and validating form error feedback.
---

# Playwright Form Automation

Patterns for automating complex web forms and file uploads.

## Workflow

1. **Target Inputs**: Locate inputs via labels (`getByLabel`) or placeholders (`getByPlaceholder`).
2. **Fill Values**: Clear and fill text, trigger change events, and select dropdown options.
3. **File Uploads**: Use `setInputFiles` to upload test PDFs or images from `sample_upload/`.
4. **Submit & Verify**: Click submit, wait for response, and assert on toast messages or navigation.
