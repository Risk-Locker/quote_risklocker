# Operations & Runtime Configuration

## 1. Environment Variables

| Variable | Required | Default | Purpose |
| :--- | :--- | :--- | :--- |
| `APP_ENV` | Yes | `local` | Environment mode (`local`, `staging`, `production`) |
| `DATABASE_URL` | Yes | - | PostgreSQL / Database connection string |
| `PORT` | No | `3000` / `8000` | Application HTTP server listening port |
| `AUTH_SECRET` | Yes | - | Session signing key / JWT secret |

## 2. Common Operational Commands

```bash
# Start development server
npm run dev

# Run migrations
npm run db:migrate # or python commands/apply-migrations.py

# Run test suite
npm test # or pytest

# Verify documentation integrity
python commands/verify-brain.py

# Update codebase map
python commands/update-code-map.py --write
```

## 3. Database Migrations & Backup Policy

- **Migration Policy**: Always use versioned migration scripts. Never apply un-tracked schema changes in production.
- **Backup & Retention**: Automated periodic database snapshots and log rotation policy.
