# API Contracts & Endpoints

## 1. Authentication & Base Rules

- **Base URL**: `/api/v1` (or relevant prefix)
- **Auth Header / Cookies**: `Bearer <token>` or `Session-Cookie`
- **Error Response Format**:
```json
{
  "error": {
    "code": "BAD_REQUEST",
    "message": "Human readable description",
    "details": []
  }
}
```

## 2. Route Endpoints

### Authentication & Users
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/auth/login` | User login & session creation | No |
| `POST` | `/auth/logout` | Invalidate active session | Yes |
| `GET` | `/auth/me` | Current authenticated user context | Yes |

### Resource Endpoints
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/items` | List items with pagination & filters | Yes |
| `POST` | `/items` | Create new item | Yes |
| `GET` | `/items/{id}` | Get item by ID | Yes |
| `PATCH` | `/items/{id}` | Update item fields | Yes |
| `DELETE` | `/items/{id}` | Soft-delete / remove item | Yes |
