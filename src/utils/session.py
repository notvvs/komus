import ssl
import aiohttp


def create_komus_session():
    """Фабрика для создания сессии с настройками Komus"""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    connector = aiohttp.TCPConnector(
        ssl=ssl_context,
        limit=100,
        limit_per_host=10,
        ttl_dns_cache=300,
        use_dns_cache=True,
    )

    return aiohttp.ClientSession(connector=connector)