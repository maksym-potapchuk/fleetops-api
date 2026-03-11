from django.db import models


class RegulationNotificationStatus(models.TextChoices):
    PENDING = "Pending", "Pending"
    SENT = "Sent", "Sent"
    FAILED = "Failed", "Failed"


class EventType(models.TextChoices):
    PERFORMED = "performed", "Service Performed"
    KM_UPDATED = "km_updated", "KM Updated"
    NOTIFIED = "notified", "Notification Sent"


# ---------------------------------------------------------------------------
# Default seed data — single source of truth
# ---------------------------------------------------------------------------

DEFAULT_EQUIPMENT = [
    "Вогнегасник",
    "Аптечка",
    "Трикутник",
    "Жилет",
    "Буксирувальний трос",
    "Запасне колесо",
    "Домкрат",
]

DEFAULT_REGULATION_SCHEMA = {
    "title": "РЕГЛАМЕНТ ОБСЛУГОВУВАННЯ",
    "title_pl": "REGULAMIN SERWISOWY",
    "title_uk": "РЕГЛАМЕНТ ОБСЛУГОВУВАННЯ",
    "title_en": "MAINTENANCE REGULATION",
    "items": [
        {
            "title": "Заміна моторного масла та масляного фільтра",
            "title_pl": "Wymiana oleju silnikowego i filtra oleju",
            "title_uk": "Заміна моторного масла та масляного фільтра",
            "title_en": "Engine oil and oil filter replacement",
            "every_km": 10_000,
            "notify_before_km": 500,
        },
        {
            "title": "Заміна фільтра газової системи",
            "title_pl": "Wymiana filtra instalacji gazowej",
            "title_uk": "Заміна фільтра газової системи",
            "title_en": "Gas system filter replacement",
            "every_km": 10_000,
            "notify_before_km": 500,
        },
        {
            "title": "Заміна повітряного фільтра двигуна",
            "title_pl": "Wymiana filtra powietrza silnika",
            "title_uk": "Заміна повітряного фільтра двигуна",
            "title_en": "Engine air filter replacement",
            "every_km": 20_000,
            "notify_before_km": 1_000,
        },
        {
            "title": "Заміна салонного фільтра",
            "title_pl": "Wymiana filtra kabinowego",
            "title_uk": "Заміна салонного фільтра",
            "title_en": "Cabin filter replacement",
            "every_km": 20_000,
            "notify_before_km": 1_000,
        },
        {
            "title": "Перевірка стану підвіски",
            "title_pl": "Kontrola stanu zawieszenia",
            "title_uk": "Перевірка стану підвіски",
            "title_en": "Suspension condition check",
            "every_km": 20_000,
            "notify_before_km": 1_000,
        },
        {
            "title": "Заміна гальмівної рідини",
            "title_pl": "Wymiana płynu hamulcowego",
            "title_uk": "Заміна гальмівної рідини",
            "title_en": "Brake fluid replacement",
            "every_km": 30_000,
            "notify_before_km": 2_000,
        },
        {
            "title": "Заміна гальмівних колодок",
            "title_pl": "Wymiana klocków hamulcowych",
            "title_uk": "Заміна гальмівних колодок",
            "title_en": "Brake pad replacement",
            "every_km": 30_000,
            "notify_before_km": 2_000,
        },
        {
            "title": "Перевірка електросистеми та компонентів двигуна",
            "title_pl": "Kontrola układu elektrycznego i podzespołów silnika",
            "title_uk": "Перевірка електросистеми та компонентів двигуна",
            "title_en": "Electrical system and engine components check",
            "every_km": 20_000,
            "notify_before_km": 1_000,
        },
        {
            "title": "Заміна рідини гідропідсилювача керма",
            "title_pl": "Wymiana płynu wspomagania kierownicy",
            "title_uk": "Заміна рідини гідропідсилювача керма",
            "title_en": "Power steering fluid replacement",
            "every_km": 50_000,
            "notify_before_km": 2_000,
        },
        {
            "title": "Заміна охолоджуючої рідини",
            "title_pl": "Wymiana płynu chłodniczego",
            "title_uk": "Заміна охолоджуючої рідини",
            "title_en": "Coolant replacement",
            "every_km": 60_000,
            "notify_before_km": 3_000,
        },
        {
            "title": "Заміна помпи інвертора",
            "title_pl": "Wymiana pompy cieczy chłodzącej inwertera",
            "title_uk": "Заміна помпи інвертора",
            "title_en": "Inverter coolant pump replacement",
            "every_km": 120_000,
            "notify_before_km": 5_000,
        },
        {
            "title": "Заміна помпи охолодження",
            "title_pl": "Wymiana pompy cieczy chłodzącej silnika",
            "title_uk": "Заміна помпи охолодження",
            "title_en": "Engine coolant pump replacement",
            "every_km": 120_000,
            "notify_before_km": 5_000,
        },
        {
            "title": "Заміна масла коробки передач",
            "title_pl": "Wymiana oleju w skrzyni biegów",
            "title_uk": "Заміна масла коробки передач",
            "title_en": "Transmission oil replacement",
            "every_km": 70_000,
            "notify_before_km": 3_000,
        },
        {
            "title": "Заміна паливного фільтра",
            "title_pl": "Wymiana filtra paliwa",
            "title_uk": "Заміна паливного фільтра",
            "title_en": "Fuel filter replacement",
            "every_km": 70_000,
            "notify_before_km": 3_000,
        },
    ],
}
