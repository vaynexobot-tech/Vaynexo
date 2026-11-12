from app.config import settings
from app.providers.base import DonateProvider, ProviderResult

_provider: DonateProvider | None = None


def get_provider() -> DonateProvider:
    global _provider
    if _provider is None:
        if settings.donate_provider == "http":
            from app.providers.http import HttpProvider

            _provider = HttpProvider(settings.donate_provider_url, settings.donate_provider_key)
        elif settings.donate_provider == "mock" and settings.dev_mode:
            from app.providers.mock import MockProvider

            _provider = MockProvider()
        else:  # API ulanmaguncha — admin qo'lda bajaradi (mock jonli serverda hech qachon ishlamaydi)
            from app.providers.manual import ManualProvider

            _provider = ManualProvider()
    return _provider


def set_provider(provider: DonateProvider) -> None:
    global _provider
    _provider = provider


__all__ = ["DonateProvider", "ProviderResult", "get_provider", "set_provider"]
