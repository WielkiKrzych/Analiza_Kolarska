"""Klient REST API dla Intervals.icu z cachowaniem i obsługą rate limitów."""

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

API_BASE = "https://intervals.icu/api/v1"
# Secret is read from the environment / .env only — never hardcoded.
# Get your key at intervals.icu -> Settings -> Developer Settings -> API Key.
API_KEY = os.environ.get("INTERVALS_ICU_API_KEY", "")
ATHLETE_ID = os.environ.get("INTERVALS_ICU_ATHLETE_ID", "39505110")
CACHE_DIR = Path(__file__).parent.parent.parent / ".cache" / "intervals_icu"

USER_AGENT = "Mozilla/5.0 TriDashboard/1.0"


class IntervalsClient:
    """Klient API Intervals.icu z wbudowanym cachowaniem."""

    def __init__(self, cache_ttl_short: int = 300, cache_ttl_long: int = 3600):
        self.cache_ttl_short = cache_ttl_short  # 5 min
        self.cache_ttl_long = cache_ttl_long  # 1 godzina
        self.session = requests.Session()
        self.session.auth = ("API_KEY", API_KEY)
        self.session.headers.update({"User-Agent": USER_AGENT})
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _cache_key(self, url: str, params: Optional[dict] = None) -> str:
        raw = url + json.dumps(params or {}, sort_keys=True)
        return hashlib.md5(raw.encode(), usedforsecurity=False).hexdigest()[:16]

    def _cache_path(self, key: str) -> Path:
        return CACHE_DIR / f"{key}.json"

    def _cache_valid(self, path: Path, ttl: int) -> bool:
        if not path.exists():
            return False
        age = time.time() - path.stat().st_mtime
        return age < ttl

    def _get(self, endpoint: str, params: Optional[dict] = None, ttl: Optional[int] = None) -> dict:
        """Wykonaj GET z cachowaniem i retry."""
        if not API_KEY:
            raise RuntimeError(
                "Brak klucza API Intervals.icu. Ustaw INTERVALS_ICU_API_KEY w pliku .env "
                "(intervals.icu → Settings → Developer Settings → API Key)."
            )
        url = f"{API_BASE}{endpoint}"
        cache_key = self._cache_key(url, params)
        cache_path = self._cache_path(cache_key)
        ttl = ttl or self.cache_ttl_long

        if self._cache_valid(cache_path, ttl):
            try:
                with open(cache_path) as f:
                    logger.debug("Cache HIT: %s", endpoint)
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        for attempt in range(3):
            try:
                resp = self.session.get(url, params=params, timeout=30)
                remaining = resp.headers.get("X-RateLimit-Remaining", "?")
                logger.debug(
                    "API call: %s -> %s (remaining: %s)", endpoint, resp.status_code, remaining
                )

                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 30))
                    logger.warning("Rate limited, retrying in %ss", retry_after)
                    time.sleep(retry_after)
                    continue

                # Auth problems must surface clearly so the user fixes the key.
                if resp.status_code in (401, 403):
                    resp.raise_for_status()

                # Other client errors (e.g. 404/422 for an endpoint whose params
                # this athlete/plan doesn't support) should NOT crash the tab —
                # degrade gracefully to "no data" instead of a red error.
                if 400 <= resp.status_code < 500:
                    logger.warning(
                        "Intervals API %s -> %s (pomijam): %s",
                        endpoint,
                        resp.status_code,
                        resp.text[:200],
                    )
                    return {}

                resp.raise_for_status()  # 5xx -> retry below
                data = resp.json()
                with open(cache_path, "w") as f:
                    json.dump(data, f)
                return data
            except requests.RequestException as e:
                if attempt < 2:
                    wait = 2**attempt
                    logger.warning("Retry %d/%d in %ss: %s", attempt + 1, 3, wait, e)
                    time.sleep(wait)
                else:
                    logger.error("Intervals API nieosiągalne dla %s: %s", endpoint, e)
                    return {}

        return {}

    # ── Wellness ──────────────────────────────────────────────

    def get_wellness(self, days_back: int = 90) -> pd.DataFrame:
        """Pobierz dane wellness z ostatnich N dni."""
        oldest = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        newest = datetime.now().strftime("%Y-%m-%d")
        data = self._get(
            f"/athlete/{ATHLETE_ID}/wellness",
            {"oldest": oldest, "newest": newest},
            ttl=self.cache_ttl_short,
        )
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        if "id" in df.columns:
            df["date"] = pd.to_datetime(df["id"])
        return df

    # ── Activities ────────────────────────────────────────────

    def get_activities(self, days_back: int = 90) -> pd.DataFrame:
        """Pobierz listę aktywności (podsumowania)."""
        oldest = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%dT00:00:00")
        newest = datetime.now().strftime("%Y-%m-%dT23:59:59")
        data = self._get(
            f"/athlete/{ATHLETE_ID}/activities",
            {"oldest": oldest, "newest": newest},
            ttl=self.cache_ttl_short,
        )
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        if "start_date_local" in df.columns:
            df["date"] = pd.to_datetime(df["start_date_local"]).dt.date
        return df

    def get_activity_details(self, activity_id: str) -> dict:
        """Pobierz pełne szczegóły aktywności z interwałami."""
        return self._get(f"/activity/{activity_id}", {"intervals": "true"}, ttl=self.cache_ttl_long)

    # ── Power / Pace Curves ───────────────────────────────────

    def get_power_curves(self, sport: str = "Ride", days_back: int = 180) -> dict:
        """Pobierz krzywą mocy (power-duration curve).

        Endpoint intervals.icu oczekuje `type` (typ aktywności) i `curves`
        (okres w formacie `<n>d`), nie `sport`/`days`.
        """
        # Known-valid period tokens (per intervals.icu API example: 1y,42d,all).
        return self._get(
            f"/athlete/{ATHLETE_ID}/power-curves",
            {"type": sport, "curves": "1y,90d,42d"},
            ttl=self.cache_ttl_short,
        )

    def get_pace_curves(self, sport: str = "Run", days_back: int = 180) -> dict:
        """Pobierz krzywą tempa (pace-duration curve)."""
        return self._get(
            f"/athlete/{ATHLETE_ID}/pace-curves",
            {"type": sport, "curves": "1y,90d,42d"},
            ttl=self.cache_ttl_short,
        )

    # ── Calendar / Events ─────────────────────────────────────

    def get_calendar_events(self, days_ahead: int = 90, days_back: int = 30) -> pd.DataFrame:
        """Pobierz zaplanowane eventy z kalendarza."""
        oldest = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        newest = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        data = self._get(
            f"/athlete/{ATHLETE_ID}/events",
            {"oldest": oldest, "newest": newest},
            ttl=self.cache_ttl_short,
        )
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        if "start_date_local" in df.columns:
            df["date"] = pd.to_datetime(df["start_date_local"]).dt.date
        return df

    # ── Fitness ───────────────────────────────────────────────

    def get_fitness(self) -> dict:
        """Pobierz aktualne CTL/ATL/TSB."""
        return self._get(f"/athlete/{ATHLETE_ID}/fitness", ttl=self.cache_ttl_short)

    # ── Profile ───────────────────────────────────────────────

    def get_athlete_profile(self) -> dict:
        """Pobierz profil zawodnika (FTP, strefy, etc.)."""
        return self._get(f"/athlete/{ATHLETE_ID}", ttl=self.cache_ttl_long)


# Singleton dla Streamlit
_client_instance: Optional[IntervalsClient] = None


def get_client() -> IntervalsClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = IntervalsClient()
    return _client_instance
