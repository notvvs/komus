import httpx
import asyncio
import time
import random
from playwright.async_api import async_playwright
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


async def make_request(
        url: str,
        cookies: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        method: str = "GET",
        max_retries: int = 3,
        params: Optional[Dict] = None,
        **kwargs
):
    """
    Асинхронно выполняет HTTP запрос с автоматическим обновлением сессии при 503

    Args:
        url: URL для запроса
        cookies: Словарь с cookies (если None, получит из session manager)
        headers: Словарь с заголовками (если None, получит из session manager)
        method: HTTP метод (GET, POST и т.д.)
        max_retries: Максимальное количество попыток при 503 ошибке
        params: Параметры URL (query string)
        **kwargs: Дополнительные параметры для httpx

    Returns:
        httpx.Response: Ответ сервера
    """

    # Если cookies/headers не переданы, получаем из session manager
    if cookies is None or headers is None:
        from src.utils.session_manager import session_manager
        session_data = await session_manager.get_session()
        cookies = cookies or session_data['cookies']
        headers = headers or session_data['headers']

    for attempt in range(max_retries):
        try:
            # Базовые заголовки
            default_headers = {
                'accept': 'application/json',
                'accept-language': 'ru,en;q=0.9',
                'priority': 'u=1, i',
                'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "YaBrowser";v="25.4", "Yowser";v="2.5"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"macOS"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 YaBrowser/25.4.0.0 Safari/537.36',
                'x-requested-with': 'XMLHttpRequest'
            }

            if headers:
                default_headers.update(headers)

            async with httpx.AsyncClient(
                    timeout=30.0,
                    cookies=cookies if cookies else {}
            ) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=default_headers,
                    params=params,
                    follow_redirects=True,
                    **kwargs
                )

            # Проверяем статус код
            if response.status_code == 503:
                if attempt < max_retries - 1:  # Если не последняя попытка
                    logger.warning(f"⚠️ 503 ошибка, обновляем сессию (попытка {attempt + 1}/{max_retries})")

                    # Обновляем сессию через session manager
                    from src.utils.session_manager import session_manager
                    session_data = await session_manager.refresh_session_on_error()
                    cookies = session_data['cookies']
                    headers = session_data['headers']

                    # Небольшая задержка перед повтором
                    await asyncio.sleep(2 ** attempt)  # Экспоненциальная задержка
                    continue
                else:
                    logger.error(f"❌ Исчерпаны попытки обновления сессии (503)")
                    return response
            else:
                # Успешный ответ или другая ошибка
                if attempt > 0:
                    logger.info(f"✅ Запрос успешен после {attempt + 1} попыток")
                return response

        except Exception as e:
            if attempt < max_retries - 1:
                logger.error(f"❌ Ошибка запроса (попытка {attempt + 1}): {e}")

                # При ошибке тоже пытаемся обновить сессию
                if "503" in str(e) or "Forbidden" in str(e) or "blocked" in str(e).lower():
                    logger.warning("🔄 Обновляем сессию из-за ошибки...")
                    from src.utils.session_manager import session_manager
                    session_data = await session_manager.refresh_session_on_error()
                    cookies = session_data['cookies']
                    headers = session_data['headers']

                await asyncio.sleep(2 ** attempt)
                continue
            else:
                logger.error(f"❌ Критическая ошибка после {max_retries} попыток: {e}")
                raise e

    # Этот код не должен выполняться, но на всякий случай
    raise Exception("Неожиданное завершение цикла retry")


async def refresh_session_on_503():
    """
    Автоматически обновляет cookies и заголовки при получении 503 ошибки
    Комбинирует свежие cookies из Playwright с критическими cookies

    Returns:
        dict: Словарь с обновленными cookies и заголовками
    """
    # Базовые критические cookies, которые точно работают
    base_critical_cookies = {
        "ngenix_bcv_b52ab4": "1.7c185763b192e9c21ac5b9de56651b5e22c07ce40f89364f3506ef1372b97fa2.1750738864.a29tdXMucnU=.c2Vzc2lvbl9pZD1mNDdiYWU4Yy0yNWEwLTQ0MzYtYjgyOS1iMTM5OTE2OGRiZGImY3NzX3YzX29rPXRydWUmY29tcHV0ZV9vaz10cnVl",
        "popmechanic_sbjs_migrations": "popmechanic_1418474375998%3D1%7C%7C%7C1471519752600%3D1%7C%7C%7C1471519752605%3D1",
        "__ai_fp_uuid": "e97b1770a58127a9%3A1",
        "__upin": "qlPCFGZDCWAynqKR5vLPSQ",
        "uxs_uid": "11b681d0-504e-11f0-bc0c-899fecea2cbe",
        "mindboxDeviceUUID": "7e83c116-aba2-4244-861d-dfb7ed95af97",
        "directCrm-session": "%7B%22deviceGuid%22%3A%227e83c116-aba2-4244-861d-dfb7ed95af97%22%7D",
        "tmr_lvid": "0ae2fa030762e55b218232802099d956",
        "tmr_lvidTS": "1750695670453"
    }

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                    '--incognito'
                ]
            )

            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 YaBrowser/25.4.0.0 Safari/537.36'
            )

            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            page = await context.new_page()

            # Заходим на страницу товара для получения актуальной сессии
            product_url = "https://www.komus.ru/katalog/kantstovary/kalkulyatory/kalkulyatory-nastolnye/kalkulyator-nastolnyj-attache-af-888-12-razryadnyj-belyj-seryj-204x158x38-mm/p/1572674/?from=block-301-0_6&tabId=specifications"
            await page.goto(product_url)
            await asyncio.sleep(5)

            # Небольшое взаимодействие со страницей
            try:
                await page.mouse.wheel(0, 300)
                await asyncio.sleep(1)
            except:
                pass

            # Получаем свежие cookies
            fresh_cookies = await context.cookies()
            fresh_cookies_dict = {cookie['name']: cookie['value'] for cookie in fresh_cookies}

            await browser.close()

            # Комбинируем: берем свежие cookies, но добавляем критические если их нет
            final_cookies = fresh_cookies_dict.copy()

            for key, value in base_critical_cookies.items():
                if key not in final_cookies:
                    final_cookies[key] = value

            # Генерируем свежие заголовки
            timestamp = str(int(time.time() * 1000))
            random_chars = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=20))

            headers = {
                'accept': 'application/json',
                'accept-language': 'ru,en;q=0.9',
                'priority': 'u=1, i',
                'referer': product_url,
                'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "YaBrowser";v="25.4", "Yowser";v="2.5"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"macOS"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 YaBrowser/25.4.0.0 Safari/537.36',
                'x-dtpc': f'4${timestamp}_{random_chars}-0e0',
                'x-dtreferer': product_url.split('?')[0],
                'x-requested-with': 'XMLHttpRequest'
            }

            logger.info("✅ Сессия успешно обновлена через Playwright")
            return {
                'cookies': final_cookies,
                'headers': headers
            }

    except Exception as e:
        logger.error(f"❌ Ошибка обновления сессии: {e}")

        # Fallback: возвращаем проверенные рабочие cookies
        fallback_cookies = {
            "JSESSIONID": "9b75668b-c1ef-4419-9464-9faa9f11e20b.hybris11p.komus.net",
            "USER_ID": "2159808362",
            "CURRENT_REGION": "77",
            "ngx_s_id": "ZjQ3YmFlOGMtMjVhMC00NDM2LWI4MjktYjEzOTkxNjhkYmRiQDE3NTA2OTU2NjMzMTVAOTAwMDAwQDE3NTA2OTU2NjMzMTVANGNlNjM5YjQ5NTI5ZTAwMjZhODE4YjlhYjdjOGQ1MzQ0OTBmMzIyNjUxZmE4MzRiY2QyZTdiMzI2OTUzOTcyYg==",
            **base_critical_cookies
        }

        fallback_headers = {
            'accept': 'application/json',
            'x-dtpc': f'4${int(time.time() * 1000)}_{"".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=20))}-0e0',
            'x-requested-with': 'XMLHttpRequest'
        }

        logger.info("🔄 Используем fallback cookies")
        return {
            'cookies': fallback_cookies,
            'headers': fallback_headers
        }