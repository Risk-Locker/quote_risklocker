# Risklocker v7 Project Map

This is the current whole-system view. Authentication redesign and Resend remain deliberately outside the active core checkpoint.

```mermaid
flowchart TD
    U[Authenticated Staff] --> UP[Upload one PDF]
    UP --> API[FastAPI under same-origin /api]
    API --> J[(Postgres job queue)]
    J --> W[One bounded extraction/render worker]
    W --> SCAN[Validate, scan, native extraction, OCR only when needed]
    SCAN --> SRC[(Private source PDF + extraction evidence)]
    SCAN --> WS[Canonical quotation workspace]

    WS --> RV[Check Values]
    RV --> FD[Explicit scalar and source-line decisions]
    RV --> TS[Choose published template revision]
    TS --> IMP[Preview impact and confirm]
    IMP --> PIN[Pin exact revision and clear foreign layout override]
    FD --> SAVE[Optimistic dirty-operation save]
    PIN --> SAVE

    SAVE --> PV[Preview]
    PV --> CTX[Build one immutable render context]
    CTX --> HTML[Deterministic fixed-page HTML]
    HTML --> PRE[Authorized preview]
    HTML --> PDF[Playwright/Chromium PDF]
    PDF --> VER[(Immutable version + private PDF)]
    VER --> DL[Authorized download; never generates]

    subgraph Template system
      TB[Template Builder draft]
      PP[A4 or explicit custom fixed page]
      G1[At most one Current Benefits grid]
      G2[At most one Available Add-ons grid]
      TB --> PP
      TB --> G1
      TB --> G2
      G1 --> SHRINK[Rows/columns recompute; every card shrinks uniformly]
      G2 --> SHRINK
      TB --> PUB[Validate and publish with base revision]
      PUB --> TR[(Immutable content-hashed template revision)]
      TR --> TS
    end

    subgraph Business data
      CO[(Dynamic legal entities, brands, aliases, products, tiers)]
      CAT[(Verified revisioned catalogs, packages, typed benefits, relations)]
      AS[(Authorized logos and benefit assets)]
      CO --> WS
      CAT --> WS
      AS --> CTX
    end

    subgraph Access
      ST[Staff: shared quotations and approved business setup]
      AD[Admin: Staff plus users, security, audit, IP, operations]
      PA[Primary Admin: exclusive ownership and emergency controls]
    end

    subgraph Storage and lifecycle
      DB[(Supabase/Postgres source of truth)]
      OBJ[(Private Supabase Storage)]
      MAN[Manual archive/trash/restore/reference-aware purge]
      DB --> MAN
      OBJ --> MAN
      MAN --> NODEL[No automatic PDF expiry or trash purge]
    end

    subgraph Delivery boundary
      CORE[Core workflow, security, templates, rendering, operations]
      AUTH[WP13 account onboarding, password plus email OTP]
      RESEND[WP14 Resend integration]
      CORE --> APPROVAL{Owner approves core}
      APPROVAL --> AUTH --> RESEND
    end
```

Compatibility adapters keep legacy batches, drafts, manual benefit elements, templates, assets, and generated versions readable. New uploads are single-file, new benefit content uses dynamic grids, and destructive cleanup waits for reference checks.
