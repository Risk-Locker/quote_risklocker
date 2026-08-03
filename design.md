# Contractor Insurance Johor Bahru (JB)

## Mission
Create implementation-ready, token-driven UI guidance for Contractor Insurance Johor Bahru (JB) that is optimized for consistency, accessibility, and fast delivery across dashboard web app.

## Brand
- Product/brand: Contractor Insurance Johor Bahru (JB)
- URL: https://www.risklocker.com/
- Audience: authenticated users and operators
- Product surface: dashboard web app

## Style Foundations
- Visual style: clean, functional, implementation-oriented
- Main font style: `font.family.primary=Be Vietnam Pro`, `font.family.stack=Be Vietnam Pro`, `font.size.base=16px`, `font.weight.base=400`, `font.lineHeight.base=normal`
- Typography scale: `font.size.xs=12px`, `font.size.sm=14px`, `font.size.md=16px`, `font.size.lg=18px`, `font.size.xl=22px`, `font.size.2xl=30px`, `font.size.3xl=36px`, `font.size.4xl=46px`
- Color palette: `color.text.primary=#454545`, `color.text.secondary=#1b1717`, `color.text.tertiary=#ffffff`, `color.surface.muted=#ed1c24`, `color.surface.base=#000000`, `color.surface.strong=#0084ff`
- Spacing scale: `space.1=1px`, `space.2=5px`, `space.3=8px`, `space.4=10px`, `space.5=11px`, `space.6=20px`, `space.7=35px`, `space.8=40px`
- Radius/shadow/motion tokens: `radius.xs=50px` | `shadow.1=rgb(255, 255, 255) 0px 0px 0px 2px inset`, `shadow.2=rgb(237, 28, 36) 0px 0px 0px 2px inset`, `shadow.3=rgba(77, 194, 71, 0.39) 0px 0px 0px 0.511673px`, `shadow.4=rgba(0, 132, 255, 0.004) 0px 0px 0px 19.8067px` | `motion.duration.instant=200ms`, `motion.duration.fast=300ms`, `motion.duration.normal=500ms`

## Accessibility
- Target: WCAG 2.2 AA
- Keyboard-first interactions required.
- Focus-visible rules required.
- Contrast constraints required.

## Writing Tone
Concise, confident, implementation-focused.

## Rules: Do
- Use semantic tokens, not raw hex values, in component guidance.
- Every component must define states for default, hover, focus-visible, active, disabled, loading, and error.
- Component behavior should specify responsive and edge-case handling.
- Interactive components must document keyboard, pointer, and touch behavior.
- Accessibility acceptance criteria must be testable in implementation.

## Rules: Don't
- Do not allow low-contrast text or hidden focus indicators.
- Do not introduce one-off spacing or typography exceptions.
- Do not use ambiguous labels or non-descriptive actions.
- Do not ship component guidance without explicit state rules.

## Guideline Authoring Workflow
1. Restate design intent in one sentence.
2. Define foundations and semantic tokens.
3. Define component anatomy, variants, interactions, and state behavior.
4. Add accessibility acceptance criteria with pass/fail checks.
5. Add anti-patterns, migration notes, and edge-case handling.
6. End with a QA checklist.

## Required Output Structure
- Context and goals.
- Design tokens and foundations.
- Component-level rules (anatomy, variants, states, responsive behavior).
- Accessibility requirements and testable acceptance criteria.
- Content and tone standards with examples.
- Anti-patterns and prohibited implementations.
- QA checklist.

## Component Rule Expectations
- Include keyboard, pointer, and touch behavior.
- Include spacing and typography token requirements.
- Include long-content, overflow, and empty-state handling.
- Include known page component density: links (113), tables (68), lists (6), inputs (5), buttons (3).


## Quality Gates
- Every non-negotiable rule must use "must".
- Every recommendation should use "should".
- Every accessibility rule must be testable in implementation.
- Teams should prefer system consistency over local visual exceptions.
