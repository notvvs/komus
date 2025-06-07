import asyncio


async def fetch(session, url):
    """Универсальный fetch для любых сайтов"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0',
    }

    try:
        async with session.get(url, headers=headers, timeout=30) as response:
            if response.status == 200:
                return await response.text()
            elif response.status == 403:
                print(f"Доступ запрещен (403) для {url}")
                return None
            else:
                print(f"Статус {response.status} для {url}")
                return None
    except asyncio.TimeoutError:
        print(f"Timeout для {url}")
        return None
    except Exception as e:
        print(f"Ошибка при запросе {url}: {e}")
        return None