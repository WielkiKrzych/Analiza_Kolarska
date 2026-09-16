"""Intervals.icu — moduł analizy danych treningowych online.

Pobiera dane z API Intervals.icu i dostarcza 7 analiz:
1. Wellness → Performance
2. Progresja Mocy/Tempa
3. Workout Compliance
4. Balans TSS Tri
5. Progresja Interwałów
6. Race Readiness
7. Adaptacja do Ciepła
"""

from modules.intervals_icu.client import IntervalsClient, get_client

__all__ = ["IntervalsClient", "get_client"]
