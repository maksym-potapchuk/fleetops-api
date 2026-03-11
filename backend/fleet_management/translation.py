import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging

from deep_translator import GoogleTranslator

logger = logging.getLogger(__name__)

LANG_MAP = {
    "uk": "uk",
    "pl": "pl",
    "en": "en",
}

_executor = ThreadPoolExecutor(max_workers=3)


def _translate_one(text: str, src: str, tgt: str) -> str:
    try:
        return GoogleTranslator(source=src, target=tgt).translate(text) or text
    except Exception:
        logger.warning(
            "Translation %s→%s failed for '%s'", src, tgt, text, exc_info=True
        )
        return text


async def translate_text_async(
    text: str, source_lang: str, target_langs: list[str]
) -> dict[str, str]:
    """Translate *text* from *source_lang* to each *target_langs* concurrently."""
    src = LANG_MAP.get(source_lang, "uk")
    loop = asyncio.get_event_loop()

    tasks = {}
    for lang in target_langs:
        tgt = LANG_MAP.get(lang, lang)
        if tgt == src:
            continue
        tasks[lang] = loop.run_in_executor(_executor, _translate_one, text, src, tgt)

    results: dict[str, str] = {source_lang: text}
    for lang, task in tasks.items():
        results[lang] = await task

    return results
