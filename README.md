<h1 align="center">🚴‍♂️ Analiza Kolarska</h1>

<p align="center">
  <em>Profesjonalny dashboard do analizy fizjologii i mocy w kolarstwie —<br/>
  od surowego pliku treningowego do progów, modeli i rekomendacji.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Streamlit-1.30%2B-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" alt="Streamlit">
  <img src="https://img.shields.io/badge/Testy-253%20passed-3FB950?style=for-the-badge&logo=pytest&logoColor=white" alt="Tests">
  <img src="https://img.shields.io/badge/Licencja-MIT-8957E5?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/macOS-Dock%20App-000000?style=for-the-badge&logo=apple&logoColor=white" alt="macOS app">
</p>

---

## 📑 Spis treści

- [Czym jest Analiza Kolarska](#-czym-jest-analiza-kolarska)
- [Mapa zakładek](#-mapa-zakładek)
- [Szybki start](#-szybki-start)
- [Aplikacja na Dock (macOS)](#-aplikacja-na-dock-macos)
- [Architektura](#-architektura)
- [Struktura projektu](#-struktura-projektu)
- [Stos technologiczny](#-stos-technologiczny)
- [Walidacja i jakość danych](#-walidacja-i-jakość-danych)
- [Testy](#-testy)
- [Changelog](#-changelog)
- [Licencja i autor](#-licencja-i-autor)

---

## 🎯 Czym jest Analiza Kolarska

**Analiza Kolarska** to samodzielna, kolarska część ekosystemu *Tri_Dashboard* — skupiona wyłącznie
na rowerze. Wczytujesz plik z treningu lub testu (CSV / TXT), a aplikacja:

- **rozpoznaje typ sesji** (test rampowy / schodkowy vs trening) i dobiera odpowiednią analizę,
- **wykrywa progi** wentylacyjne (VT1/VT2) i mięśniowe (SmO2) — jako *zakresy z pewnością detekcji*, nie pojedyncze punkty,
- **modeluje moc** (CP / W′, krzywa mocy, W′ balance i rekonstytucja),
- **ocenia fizjologię** (HRV, hemodynamika, wentylacja, obciążenie cieplne),
- **planuje i prognozuje** (predykcja mocy wyścigowej, periodyzacja, model Banistera, VLaMax),
- **eksportuje** wyniki (FIT / TCX / CSV) i generuje raporty.

> 💡 Wszystkie wykresy są interaktywne (Plotly) — z zoomem, hover i zaznaczaniem przeciągnięciem (box-select).

---

## 🗺️ Mapa zakładek

Interfejs dzieli się na **pięć grup**:

### 📊 Overview
| Zakładka | Zawartość |
|---|---|
| 📋 Raport z KPI | Kluczowe wskaźniki sesji, dekopling, dryf Z2 |
| 📊 Podsumowanie | Przegląd metryk, krzywa mocy, VO₂max z CI95%, walidacja danych |

### ⚡ Performance
| Zakładka | Opis |
|---|---|
| 🔋 Power | NP, IF, TSS, MMP, strefy mocy |
| 🦵 Biomech | Kadencja, balans, moment obrotowy, Gross Efficiency |
| 📐 Model | Critical Power (CP) i W′ (W Prime) |
| ❤️ HR | Strefy tętna, decay, dryf w Z2 |
| 🧬 Hematology | THb, Hct, estymacje hemodynamiczne |
| 📈 Drift Maps | Mapy dryfu fizjologicznego |
| ⏱️ TTE | Time To Exhaustion na zadanej intensywności |
| 🔗 W′bal Recon | Mapa wyczerpania/odnowy W′, cykle regeneracji (Caen 2021) |
| 🛡️ Durability | Durability Index, analiza sezonowa, rekomendacje |

### 🧠 Intelligence
| Zakładka | Opis |
|---|---|
| 🍎 Nutrition | Estymacja spalania kalorii / węglowodanów |
| 🚧 Limiters | Identyfikacja ograniczników wydolności |
| 🏁 Race Predictor | Predykcja mocy na zawody z korektami wiatr / temperatura / trasa |
| 📊 Training Distribution | Time-in-Zone (power / HR / SmO2), balance score |

### 🫀 Physiology
| Zakładka | Opis |
|---|---|
| 💓 HRV | RMSSD, pNN50, DFA-α1 |
| 🩸 SmO2 | Saturacja mięśniowa, dekonwolucja, progi |
| 🫁 Ventilation | VT1, VT2, RER, breathing power |
| 🌡️ Thermal | Temperatura centralna/peryferyjna |
| 🔥 Heat Strain | PSI/HSI z korektami środowiskowymi, ocena ryzyka |

### 🚴 Cycling
| Zakładka | Opis |
|---|---|
| 🎯 MPA | Modeled Power Availability (dostępna moc z W′bal) |
| 🧪 VLaMax | Profil beztlenowy, wkład systemów energetycznych |
| ♻️ Aerobic Efficiency | Efektywność tlenowa i jej trend w czasie |
| 📈 Training Impact | Wpływ treningu, klasyfikacja intensywności |
| 🗓️ Banister | Model fitness–fatigue, prognoza formy, okna szczytu |
| 📅 Periodization | Bloki treningowe, plan tygodniowy, PMC (CTL/ATL/TSB) |

---

## 🚀 Szybki start

```bash
# 1. Klonowanie
git clone https://github.com/WielkiKrzych/Analiza_Kolarska.git
cd Analiza_Kolarska

# 2. Zależności (zalecane venv)
pip install -e .
# opcjonalnie narzędzia deweloperskie i testy:
pip install -e ".[dev,test]"

# 3. Uruchomienie
streamlit run app.py
```

Aplikacja wystartuje na `http://localhost:8501` (lub `8502`, jeśli uruchamiasz ją z aplikacji Dock).

**Wymagania:** Python 3.10+, zależności z `pyproject.toml`.

---

## 🍎 Aplikacja na Dock (macOS)

Jednym poleceniem zbudujesz natywną aplikację `.app` z własną ikoną, która uruchamia dashboard
kliknięciem z Docka:

```bash
cd ~/Documents/Analiza_Kolarska && bash build_app.sh
```

Skrypt tworzy **`Analiza Kolarska.app`** w `/Applications` (lub `~/Applications`, jeśli brak uprawnień):

- ▸ aplet AppleScript uruchamia `launcher.sh` w tle → Streamlit na porcie `8502` → przeglądarka,
- ▸ własna ikona (`icon.png`) osadzana przez `NSWorkspace` — plik `make_icon.py` generuje grafikę,
- ▸ automatyczne odświeżenie cache ikon (`lsregister` + `killall Dock`).

Po zbudowaniu przeciągnij aplikację z `/Applications` na Dock. Log startu: `/tmp/analiza_kolarska_launch.log`.

> 🔧 Po każdej przebudowie: jeśli Dock pokazuje pustą ikonę, usuń pozycję z Docka i przeciągnij ją ponownie
> (przebudowa podmienia bundle, przez co przypięty element „osierocieje").

---

## 🏗️ Architektura

```
┌──────────────────────────────────────────────────────────────┐
│                          📱  app.py                            │
│                    Streamlit + TabRegistry                     │
└───────────────┬──────────────────────────────────────────────┘
                │
   ┌────────────┼────────────┬────────────┬────────────┐
   ▼            ▼            ▼            ▼            ▼
 📊 Overview  ⚡ Perf.   🧠 Intel.   🫀 Physio.   🚴 Cycling
   └────────────┴────────────┴────────────┴────────────┘
                │
                ▼
        🧮  modules/calculations/      ← NumPy · SciPy · Numba
        (moc, W′, progi, SmO2, HRV, termika, VLaMax, Banister…)
                │
   ┌────────────┼────────────┐
   ▼            ▼            ▼
 💾 db/       📈 reporting/   📤 export/
 SQLite       PDF / figures   FIT · TCX · CSV
```

---

## 📁 Struktura projektu

```
Analiza_Kolarska/
├── app.py                     🚀 Główna aplikacja Streamlit (TabRegistry)
├── build_app.sh               🍎 Builder aplikacji na Dock (macOS)
├── launcher.sh                ▶️  Lifecycle Streamlita dla aplikacji .app
├── make_icon.py / icon.png    🎨 Generator i grafika ikony
├── pyproject.toml             📦 Konfiguracja i zależności
│
├── modules/
│   ├── calculations/          🧮 Silnik obliczeniowy
│   │   ├── power.py · w_prime.py · w_prime_reconstitution.py
│   │   ├── mpa.py · vlamax_profile.py · aerobic_efficiency.py
│   │   ├── banister.py · pmc.py · periodization.py · training_impact.py
│   │   ├── race_predictor.py · training_distribution.py · durability.py
│   │   ├── thresholds.py · ventilatory.py · smo2/ · heat_strain.py · hrv.py …
│   ├── ui/                     🎨 Zakładki interfejsu (+ shared.py: chart/metric)
│   ├── db/                     💾 SQLite: sesje + profile zawodnika
│   ├── reporting/              📈 Raporty PDF i figury
│   └── export/                 📤 FIT / TCX / CSV
│
├── services/                  🔄 Orkiestracja analizy sesji
├── models/ · signals/         📋 Modele danych · przetwarzanie sygnałów
├── tests/                     🧪 253 testy
└── data/                      💾 Baza SQLite
```

---

## 🛠️ Stos technologiczny

| Warstwa | Technologie |
|---|---|
| **Rdzeń** | Python 3.10+ · Streamlit · Pandas · NumPy |
| **Obliczenia** | SciPy · Numba (JIT) · Polars · NeuroKit2 |
| **Wizualizacja** | Plotly (interaktywne, box-select) · Matplotlib · Kaleido |
| **Dane** | SQLite (sesje + profile zawodnika) |
| **Jakość** | Pytest (253) · Ruff · Black |

---

## 🔬 Walidacja i jakość danych

Każda analiza rampy/schodków przechodzi automatyczną kontrolę jakości:

- ✅ minimalny czas trwania i liczba stopni,
- ✅ monotoniczność wzrostu mocy,
- ✅ detekcja przerw w zapisie i stabilności kadencji.

**Progi jako zakresy z pewnością** — każdy próg (VT1/VT2, SmO2) zawiera: pewność detekcji (0–100%),
zakres wartości, użytą metodę i wizualny wskaźnik wiarygodności.

---

## 🧪 Testy

```bash
python -m pytest tests/ -q
# ── 253 passed ──
```

---

## 🔧 Changelog

### 🆕 v0.6.0 — Uspójnienie z Tri_Dashboard, poprawki UI i aplikacja Dock

**Naprawy migracyjne**
- `plots.py` — dodane `CHART_CONFIG`, `CHART_HEIGHT_MAIN/SUB` (7 zakładek znikało po cichu przez `ImportError`).
- `thresholds.py` — przywrócone obliczanie **histerezy** i **wrażliwości** VT w `analyze_step_test` (regres migracyjny).
- `shared.py` — `chart()` z trybem **box-select** (zaznaczanie przeciągnięciem jak w Tri); `metric()` bez `delta_color=None`.

**Nowa grupa 🚴 Cycling (6 zakładek)** — MPA, VLaMax, Aerobic Efficiency, Training Impact, Banister, Periodization
(+ moduły `mpa`, `vlamax_profile`, `aerobic_efficiency`, `training_impact`, `banister`, `pmc`, `periodization`, `column_aliases`).

**Podłączone zakładki kolarskie** — TTE, W′bal Recon, Durability, Race Predictor, Training Distribution, Heat Strain.

**Parametry domyślne** — sidebar wyrównany do Tri_Dashboard (waga 97, CP 380, W′ 15600, VT1 310, VT2 360, VT1/VT2 wentylacyjne 73/105).

**Aplikacja na Dock (macOS)** — `build_app.sh` (aplet AppleScript + własna ikona `NSWorkspace`), `launcher.sh`, `make_icon.py`.

> ℹ️ Integracja **intervals.icu** została świadomie usunięta z tej wersji.

**Testy:** 253 passed, 0 regresji.

<details>
<summary><strong>Wcześniejsze wersje (v0.5.0 – v0.3.1)</strong></summary>

### v0.5.0 — Migracja funkcji kolarskich z Tri_Dashboard
Port modułów mocy/SmO2/termiki, tabela profili zawodnika (`db/athlete_profiles.py`),
eksport TCX/CSV, benchmarki referencyjne, `calculate_w_prime_biexp` (Caen 2021).

### v0.4.0 — Bezpieczeństwo i jakość kodu
Usunięcie `eval()` (RCE) z `polars_adapter.py`, ochrona XSS (`html.escape`), zapobieganie path traversal
w `notes.py`, kopiowanie DataFrame przed mutacją, 40+ `print()` → `logger`.

### v0.3.1 — Poprawki fizjologii
Korekta frakcji CHO (30/70/90%), korekcja GE w VO₂max, wykładniczy model rekonstytucji W′ (Skiba),
walidacja VT1 < VT2, HSI z wagami 70/30, próg VT1 slope 0.05 → 0.07.

</details>

---

## 📝 Licencja i autor

**Licencja:** MIT — zobacz [LICENSE](LICENSE).
**Autor:** **Wielki Krzych** — [GitHub](https://github.com/WielkiKrzych)

<p align="center">
  <sub>Zbudowane z ❤️ na Streamlit · Pandas · NumPy · Plotly</sub>
</p>
