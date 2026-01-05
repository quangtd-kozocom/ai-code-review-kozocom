"""Tests for config module __init__."""


def test_imports() -> None:
    """Test that all public exports are importable."""
    from src.core.config import (
        AutoReviewConfig,
        ChatConfig,
        ConfigCache,
        ConfigCreate,
        ConfigLoader,
        ConfigModel,
        ConfigRead,
        ConfigRepository,
        ConfigService,
        ConfigUpdate,
        PathInstruction,
        ReviewerConfig,
        ReviewProfile,
        ReviewsConfig,
        create_config_service,
    )

    # Verify they are not None
    assert ReviewerConfig is not None
    assert ReviewProfile is not None
    assert PathInstruction is not None
    assert ReviewsConfig is not None
    assert AutoReviewConfig is not None
    assert ChatConfig is not None
    assert ConfigModel is not None
    assert ConfigCreate is not None
    assert ConfigUpdate is not None
    assert ConfigRead is not None
    assert ConfigService is not None
    assert ConfigCache is not None
    assert ConfigRepository is not None
    assert ConfigLoader is not None
    assert create_config_service is not None
