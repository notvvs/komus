from contextlib import asynccontextmanager
from playwright.async_api import async_playwright
from src.core.settings import settings


@asynccontextmanager
async def get_page():
    """Контекстный менеджер для получения страницы с настройками из .env"""

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=settings.headless_mode,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-extensions",
                "--disable-plugins",
                "--disable-images",
                "--memory-pressure-off",
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",
                "--disable-blink-features=AutomationControlled",
            ],
        )

        context = await browser.new_context(
            viewport={"width": settings.viewport_width, "height": settings.viewport_height},
            user_agent=settings.user_agent,
            ignore_https_errors=True,
            java_script_enabled=True,
            bypass_csp=True,
            locale="ru-RU",
            timezone_id="Europe/Moscow",
            extra_http_headers={
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            },
        )

        page = await context.new_page()

        # Настройки страницы из .env
        page.set_default_timeout(settings.page_timeout)
        page.set_default_navigation_timeout(settings.navigation_timeout)

        # Эмуляция реального браузера
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            window.chrome = {
                runtime: {},
            };

            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );

            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });

            Object.defineProperty(navigator, 'languages', {
                get: () => ['ru-RU', 'ru', 'en-US', 'en'],
            });
        """)

        try:
            yield page
        finally:
            await context.close()
            await browser.close()