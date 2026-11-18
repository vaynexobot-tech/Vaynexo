from app.config import settings
from app.providers.base import DonateProvider, ProviderResult

_provider: DonateProvider | None = None


def get_provider() -> DonateProvider:
    global _provider
    if settings.donate_provider.startswith("ypk_"):  # kalit adashib DONATE_PROVIDER ga yozilgan — ishlatmaymiz
        import logging

        logging.getLogger(__name__).error("DONATE_PROVIDER ga kalit yozilgan: u DONATE_PROVIDER_KEY ga, DONATE_PROVIDER ga esa 'yupay' yozilishi kerak")
    if _provider is None:
        if settings.donate_provider == "yupay" and settings.donate_provider_key:
            from app.providers.yupay import YupayProvider

            _provider = YupayProvider(settings.donate_provider_key, settings.donate_provider_url)
        elif settings.donate_provider == "http":
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
