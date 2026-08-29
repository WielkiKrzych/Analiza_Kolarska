"""
Intervals.ICU — zintegrowany moduł UI dla analiz online.

Renderuje sekcję z 7 zakładkami analitycznymi pobierającymi dane
bezpośrednio z konta Intervals.icu (bez konieczności wgrywania plików).
"""

import streamlit as st

from modules.intervals_icu import (
    compliance,
    heat_adaptation,
    interval_progression,
    power_progression,
    race_readiness,
    wellness_performance,
)
from modules.intervals_icu.client import IntervalsClient


@st.cache_resource
def _get_client() -> IntervalsClient:
    """Singleton klienta API (cache'owany przez Streamlit)."""
    return IntervalsClient()


def render_intervals_icu_section():
    """Główny punkt wejścia — renderuje całą sekcję Intervals.ICU."""

    st.markdown("## 🌐 Intervals.ICU — Analiza Danych Online")
    st.caption(
        "Dane pobierane bezpośrednio z Twojego konta (athlete 39505110). "
        "Odświeżanie co 5 minut dla danych bieżących, co 1h dla historycznych."
    )

    # Przycisk odświeżania
    col_refresh, _ = st.columns([1, 5])
    with col_refresh:
        if st.button("🔄 Odśwież dane", use_container_width=True):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.rerun()

    client = _get_client()

    tabs = st.tabs(
        [
            "🏥 Wellness → Wydajność",
            "📈 Progresja Mocy",
            "📋 Compliance",
            "🔍 Interwały",
            "🏁 Race Readiness",
            "🌡️ Heat Adapt",
        ]
    )

    with tabs[0]:
        _render_wellness(client)

    with tabs[1]:
        _render_power(client)

    with tabs[2]:
        _render_compliance(client)

    with tabs[3]:
        _render_intervals(client)

    with tabs[4]:
        _render_race(client)

    with tabs[5]:
        _render_heat(client)

    st.markdown("---")
    st.caption(
        "💡 Dane z Intervals.icu API. Cache: 5 min (dane bieżące) / 1h (historyczne). "
        "Rate limit: 5000 req/dzień."
    )


@st.cache_data(ttl=300, show_spinner=False)
def _load_wellness(_client):
    return wellness_performance.compute(_client)


def _render_wellness(client):
    """Renderuj Wellness → Performance."""
    with st.spinner("Pobieranie danych wellness..."):
        result = _load_wellness(client)
    wellness_performance.render(result)


@st.cache_data(ttl=3600, show_spinner=False)
def _load_power(_client):
    return power_progression.compute(_client)


def _render_power(client):
    """Renderuj Progresja Mocy."""
    with st.spinner("Pobieranie krzywych mocy..."):
        result = _load_power(client)
    power_progression.render(result)


@st.cache_data(ttl=300, show_spinner=False)
def _load_compliance(_client):
    return compliance.compute(_client)


def _render_compliance(client):
    """Renderuj Workout Compliance."""
    with st.spinner("Pobieranie danych compliance..."):
        result = _load_compliance(client)
    compliance.render(result)


@st.cache_data(ttl=3600, show_spinner=False)
def _load_intervals(_client):
    return interval_progression.compute(_client)


def _render_intervals(client):
    """Renderuj Progresja Interwałów."""
    with st.spinner("Analiza interwałów między aktywnościami..."):
        result = _load_intervals(client)
    interval_progression.render(result)


@st.cache_data(ttl=300, show_spinner=False)
def _load_race(_client):
    return race_readiness.compute(_client)


def _render_race(client):
    """Renderuj Race Readiness."""
    with st.spinner("Pobieranie danych fitness..."):
        result = _load_race(client)
    race_readiness.render(result)


@st.cache_data(ttl=3600, show_spinner=False)
def _load_heat(_client):
    return heat_adaptation.compute(_client)


def _render_heat(client):
    """Renderuj Heat Adaptation."""
    with st.spinner("Analiza danych temperaturowych..."):
        result = _load_heat(client)
    heat_adaptation.render(result)
