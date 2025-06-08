from contextlib import asynccontextmanager
from playwright.async_api import async_playwright




@asynccontextmanager
async def get_page(headless: bool = True):
    """Контекстный менеджер для получения страницы"""

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                # Основные для стабильности
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",

                # Отключение ненужных функций
                "--disable-gpu",
                "--disable-web-security",  # нужно для кросс-доменных запросов
                "--disable-features=IsolateOrigins,site-per-process",

                # Производительность
                "--disable-extensions",
                "--disable-plugins",
                "--disable-images",  # не загружаем картинки

                # Уменьшение использования памяти
                "--memory-pressure-off",
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",

                # Антидетект
                "--disable-blink-features=AutomationControlled",
            ],
        )

        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            ignore_https_errors=True,
            java_script_enabled=True,  # JS нужен для работы сайта
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

        # Настройки страницы
        page.set_default_timeout(10000)
        page.set_default_navigation_timeout(10000)

        # Эмуляция реального браузера
        await page.add_init_script("""
            // Переопределяем webdriver
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Chrome 
            window.chrome = {
                runtime: {},
            };

            // Permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );

            // Plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });

            // Languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['ru-RU', 'ru', 'en-US', 'en'],
            });
        """)

        try:
            yield page
        finally:
            await context.close()
            await browser.close()