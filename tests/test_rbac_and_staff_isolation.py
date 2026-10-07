"""Hermetic tests for RBAC permissions and staff isolation invariants."""

from unittest.mock import MagicMock
import pytest
from app.core.errors import AppError
from app.models.enums import Role
from app.models.tables import User
from app.services.auth_service import (
    _require_user_management_permission,
    delete_user,
)


def _make_user(user_id: str, email: str, role: Role) -> User:
    u = User()
    u.id = user_id
    u.email = email
    u.role = role.value
    u.status = "active"
    return u


def test_staff_cannot_manage_users():
    staff = _make_user("staff-1", "staff@risklocker.com", Role.STAFF)
    target = _make_user("staff-2", "staff2@risklocker.com", Role.STAFF)

    with pytest.raises(AppError) as exc:
        _require_user_management_permission(staff, target)
    assert "permission to manage users" in exc.value.message


def test_dev_can_manage_staff():
    dev = _make_user("dev-1", "dev@risklocker.com", Role.DEV)
    staff = _make_user("staff-1", "staff@risklocker.com", Role.STAFF)

    # Should not raise
    _require_user_management_permission(dev, staff)
    _require_user_management_permission(dev, None)


def test_dev_cannot_modify_or_delete_admin():
    dev = _make_user("dev-1", "dev@risklocker.com", Role.DEV)
    admin = _make_user("admin-1", "admin@risklocker.com", Role.ADMIN)
    super_admin = _make_user("sa-1", "system@risklocker.com", Role.SUPER_ADMIN)
    other_dev = _make_user("dev-2", "dev2@risklocker.com", Role.DEV)

    for target in [admin, super_admin, other_dev]:
        with pytest.raises(AppError) as exc:
            _require_user_management_permission(dev, target)
        assert exc.value.status_code == 403
        assert "Developers cannot delete or modify administrators or developers" in exc.value.message


def test_admin_cannot_delete_super_admin():
    admin = _make_user("admin-1", "admin@risklocker.com", Role.ADMIN)
    super_admin = _make_user("sa-1", "system@risklocker.com", Role.SUPER_ADMIN)

    with pytest.raises(AppError) as exc:
        _require_user_management_permission(admin, super_admin)
    assert exc.value.status_code == 403
    assert "You do not have permission to manage the super administrator" in exc.value.message


def test_cannot_delete_self():
    admin = _make_user("admin-1", "admin@risklocker.com", Role.ADMIN)
    with pytest.raises(AppError) as exc:
        _require_user_management_permission(admin, admin)
    assert "cannot modify your own account" in exc.value.message


def test_delete_user_service_flow():
    db = MagicMock()
    dev = _make_user("dev-1", "dev@risklocker.com", Role.DEV)
    staff = _make_user("staff-1", "staff@risklocker.com", Role.STAFF)
    admin = _make_user("admin-1", "admin@risklocker.com", Role.ADMIN)

    # Mock audit and revoke sessions
    db.query.return_value.filter.return_value.delete.return_value = 0

    # Dev deleting staff succeeds
    delete_user(db, dev, staff)
    assert db.delete.called
    assert db.commit.called

    # Dev deleting admin fails hermetically
    with pytest.raises(AppError) as exc:
        delete_user(db, dev, admin)
    assert exc.value.status_code == 403
