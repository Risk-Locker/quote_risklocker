"""Shared enum values stored as strings for Postgres/Supabase compatibility."""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    STAFF = "staff"
    DEV = "dev"


class AccountStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    INVITED = "invited"


class NotificationEventType(StrEnum):
    INVITATION = "invitation"
    ROLE_CHANGE = "role_change"
    STATUS_CHANGE = "status_change"


class DeliveryState(StrEnum):
    SENT = "sent"
    FAILED = "failed"


class RecordStatus(StrEnum):
    UPLOADED = "Uploaded"
    PREPARING = "Preparing"
    READY = "Ready"
    CHECK_NEEDED = "Check Needed"
    CANNOT_READ = "Cannot Read"
    GENERATED = "Generated"
    DELETED = "Deleted"


class FieldStatus(StrEnum):
    READY = "ready"
    CHECK_NEEDED = "check_needed"
    CANNOT_READ = "cannot_read"


class StorageStatus(StrEnum):
    AVAILABLE = "available"
    ARCHIVE_PENDING = "archive_pending"
    ARCHIVED = "archived"
    ARCHIVE_FAILED = "archive_failed"
    EXPIRED = "expired"
    DELETED = "deleted"


class InsuranceType(StrEnum):
    MOTOR = "Motor"
    PROPERTY = "Property"
    CONSTRUCTION = "Construction"
    FIRE = "Fire"
    OTHER = "Other"
