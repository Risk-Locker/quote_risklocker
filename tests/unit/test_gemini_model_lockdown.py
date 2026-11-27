import pytest
from app.extraction import ai_sharded_pool
from app.services import gemini_account_service
from app.core.config import get_settings


def test_verified_active_models_strictly_locked_to_lite_pair():
    """Verify that both ai_sharded_pool and gemini_account_service ONLY allow gemini-3.1-flash-lite and gemini-3.5-flash-lite."""
    expected_models = ("gemini-3.1-flash-lite", "gemini-3.5-flash-lite")
    
    assert ai_sharded_pool.VERIFIED_ACTIVE_MODELS == expected_models, (
        f"ai_sharded_pool.VERIFIED_ACTIVE_MODELS must be strictly {expected_models}, "
        f"got {ai_sharded_pool.VERIFIED_ACTIVE_MODELS}"
    )
    
    assert gemini_account_service.PARALLEL_MODELS == expected_models, (
        f"gemini_account_service.PARALLEL_MODELS must be strictly {expected_models}, "
        f"got {gemini_account_service.PARALLEL_MODELS}"
    )


def test_gemini_38_flash_is_strictly_forbidden():
    """Verify that gemini-3.8-flash is purged from candidate models and cannot be used in slot acquisition."""
    assert "gemini-3.8-flash" not in ai_sharded_pool.VERIFIED_ACTIVE_MODELS
    assert "gemini-3.8-flash" not in gemini_account_service.PARALLEL_MODELS

    # Instantiating or acquiring with gemini-3.8-flash must be rejected
    manager = gemini_account_service.GeminiAccountManager(keys=("AIzaSyFakeKeyForTest1234567890",))
    with pytest.raises(ValueError, match="Forbidden model tier"):
        manager.acquire_parallel_slot(requested_model="gemini-3.8-flash")


def test_safe_limits_enforced_for_google_ai_studio_survival():
    """Verify that RPM <= 13, RPD <= 480, and TPM <= 220,000 to prevent permanent account bans."""
    assert ai_sharded_pool.SAFE_RPM_LIMIT_PER_SLOT <= 13
    assert ai_sharded_pool.SAFE_RPD_LIMIT_PER_SLOT <= 480
    assert getattr(ai_sharded_pool, "SAFE_TPM_LIMIT_PER_SLOT", 0) <= 220_000

    settings = get_settings()
    assert settings.gemini_max_rpm_per_key <= 13
    assert settings.gemini_max_rpd_per_key <= 480
    assert settings.gemini_max_tpm_per_key <= 220_000

