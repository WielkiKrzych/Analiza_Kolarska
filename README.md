# 🚴 Analiza Kolarska

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Streamlit-1.30%2B-red?style=for-the-badge&logo=streamlit" alt="Streamlit">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/Tests-157%20passed-brightgreen?style=for-the-badge&logo=pytest" alt="Tests">
</p>

Profesjonalna aplikacja do analizy danych treningowych kolarskich z zaawansowaną wizualizacją i modelowaniem fizjologicznym.

---

## ⭐ Kluczowe Funkcje

| Moduł | Funkcje |
|-------|----------|
| **📊 Overview** | Raport KPI, Podsumowanie sesji, Krzywa mocy |
| **⚡ Performance** | Power, Biomech, Model (CP/W'), HR, Hematologia, Drift Maps, **Race Predictor**, **Durability**, **Training Distribution**, **TTE**, **Intervals** |
| **🧠 Intelligence** | Nutrition, Limiters |
| **🫀 Physiology** | HRV, SmO2, Ventilation, Thermal, **W' Reconstitution**, **Heat Strain**, **SmO2 Thresholds** |

---

## 🏗️ Architektura

```
┌─────────────────────────────────────────────────────────────────┐
│                         📱 app.py                                │
│                    (Streamlit Interface)                          │
└─────────────────────┬───────────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
   ┌─────────┐   ┌─────────┐   ┌─────────┐
   │  📊    │   │   ⚡    │   │   🫀    │
   │Overview│   │Performance│  │Physiology│
   └─────────┘   └─────────┘   └─────────┘
        │             │             │
        └─────────────┴─────────────┘
                      ▼
          ┌───────────────────────┐
          │    🧮 calculations/   │
          │  (NumPy, SciPy, Numba)│
          └───────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
   ┌─────────┐   ┌─────────┐   ┌─────────┐
   │   💾    │   │  📈     │   │  📤     │
   │   db/   │   │ reporting│   │ export/ │
   │ SQLite  │   │         │   │FIT/TCX  │
   └─────────┘   └─────────┘   └─────────┘
```

---

## 🛠️ Technologie

### Core
- **Python** 3.10+ — Główny język
- **Streamlit** — Interfejs webowy
- **Pandas** — Przetwarzanie danych
- **NumPy** — Obliczenia numeryczne

### Data Processing & ML
- **SciPy** — Analiza statystyczna
- **Numba** — JIT compilation
- **Plotly** — Interaktywne wykresy
- **NeuroKit2** — Analiza sygnałów biologicznych

### Storage & Tools
- **SQLite** — Baza danych sesji + profile zawodnika
- **Pytest** — Testy (157 passed)

---

## 🚀 Uruchomienie

```bash
# Klonowanie repozytorium
git clone https://github.com/WielkiKrzych/Analiza_Kolarska.git
cd Analiza_Kolarska

# Instalacja zależności (zalecane użycie venv)
pip install -e .

# Opcjonalnie: instalacja zależności deweloperskich i testowych
pip install -e ".[dev,test]"

# Uruchomienie aplikacji
streamlit run app.py
```

### Wymagania
- Python 3.10+
- SQLite3
- Wszystkie zależności w `pyproject.toml`

---

## 📁 Struktura Projektu

```
Analiza_Kolarska/
├── app.py                      🚀 Główna aplikacja Streamlit
├── pyproject.toml              📦 Konfiguracja projektu
├── README.md                   📖 Ten plik
│
├── modules/
│   ├── calculations/           🧮 Silnik obliczeniowy
│   │   ├── power.py            ⚡ Metryki mocy (NP, IF, TSS)
│   │   ├── w_prime.py          🔋 W' Balance (Skiba + Caen bi-exp)
│   │   ├── w_prime_reconstitution.py 🔋 Mapa rekonstytucji W'
│   │   ├── race_predictor.py   🏁 Predykcja mocy wyścigowej
│   │   ├── training_distribution.py 📊 Time-in-Zone
│   │   ├── durability.py       🛡️ Durability Index
│   │   ├── heat_strain.py      🌡️ Heat Strain Index
│   │   ├── smo2_thresholds.py  🩸 Progi SmO2
│   │   ├── smo2_analysis.py    🩸 Zaawansowana analiza SmO2
│   │   ├── smo2/               🩸 Pakiet SmO2 (classifier, calculator)
│   │   ├── plateau_detector.py  📈 Detekcja плато
│   │   ├── alert_engine.py     🚨 Silnik alertów fizjologicznych
│   │   ├── hrv.py              💓 Analiza HRV
│   │   ├── smo2_advanced.py    🩸 SmO2 + dekonwolucja
│   │   ├── ventilatory.py      🫁 VT1/VT2 detection
│   │   ├── thresholds.py       📐 Wykrywanie progów
│   │   ├── stamina.py          💪 Stamina Score, VLaMax
│   │   ├── nutrition.py        🍎 Spalanie węglowodanów
│   │   └── ...
│   ├── ui/                     🎨 Komponenty interfejsu
│   │   ├── race_predictor_ui.py    🏁 Zakładka Race Predictor
│   │   ├── durability_ui.py        🛡️ Zakładka Durability
│   │   ├── heat_strain_ui.py       🌡️ Zakładka Heat Strain
│   │   ├── w_prime_reconstitution_ui.py 🔋 Zakładka W' Reconstitution
│   │   ├── training_distribution_ui.py 📊 Zakładka Training Distribution
│   │   ├── tte_ui.py               ⏱️ Zakładka TTE
│   │   ├── intervals_ui.py         🔴 Zakładka Intervals
│   │   ├── smo2_thresholds.py      🩸 Zakładka SmO2 Thresholds
│   │   ├── alerts.py               🚨 Zakładka Alerts
│   │   └── ...
│   ├── db/                     💾 SQLite stores
│   │   ├── session_store.py        💾 Sesje treningowe
│   │   ├── athlete_profiles.py     👤 Profile zawodnika (CP, W', VT)
│   │   └── base.py                 🔧 Baza abstrakcyjna DB
│   ├── reporting/              📈 Generowanie raportów
│   ├── export/                 📤 Eksport danych
│   │   ├── fit_exporter.py         📤 FIT (Garmin/Strava/TP)
│   │   ├── tcx_generator.py        📤 TCX
│   │   ├── zone_exporter.py        📤 Strefy CSV
│   │   └── workout_exporter.py     📤 TrainingPeaks CSV
│   └── social/                 🌍 Dane referencyjne
│       └── reference_data.py       📊 Benchmarki percentylowe
│
├── services/
│   ├── session_analysis.py     🔄 Analiza sesji
│   └── session_orchestrator.py 🎭 Koordynacja
│
├── models/                    📋 Modele danych
├── signals/                  🔬 Przetwarzanie sygnałów
├── tests/                    🧪 Testy (157 passed)
└── data/                     💾 Baza danych SQLite
```

---

## 📊 Funkcje Szczegółowe

### 📊 Overview
- **📋 Raport z KPI** — Kompleksowy raport z kluczowymi wskaźnikami
- **📊 Podsumowanie** — Przegląd metryk sesji, krzywa mocy

### ⚡ Performance
| Funkcja | Opis |
|---------|------|
| 🔋 Power | NP, IF, TSS, MMP, strefy mocy |
| 🦵 Biomech | Kadencja, balans, Torque, Gross Efficiency |
| 📐 Model | CP (Critical Power), W' (W Prime) |
| ❤️ HR | Strefy tętna, decay, Z2 drift |
| 🧬 Hematology | THb, Hct, Fe |
| 📈 Drift Maps | Mapy dryfu fizjologicznego |
| 🏁 **Race Predictor** | **Predykcja mocy na zawody (CP/W') z korektami wiatr/temperatura/trasa, pacing** |
| 🛡️ **Durability** | **Durability Index, sezonowa analiza zmęczenia, rekomendacje treningowe** |
| 📊 **Training Distribution** | **Time-in-Zone (power/HR/SmO2), balance score, rozkład intensywności** |
| ⏱️ **TTE** | **Time To Exhaustion — estymacja czasu do wyczerpania na zadanej intensywności** |
| 🔴 **Intervals** | **Detekcja i klasyfikacja interwałów, Pulse Power, Gross Efficiency** |

### 🧠 Intelligence
| Funkcja | Opis |
|---------|------|
| 🍎 Nutrition | Estymacja spalania kalorii/węglowodanów |
| 🚧 Limiters | Identyfikacja ograniczników wydolności |

### 🫀 Physiology
| Funkcja | Opis |
|---------|------|
| 💓 HRV | RMSSD, pNN50, DFA-a1 |
| 🩸 SmO2 | Saturacja mięśniowa, dekonwolucja |
| 🫁 Ventilation | VT1, VT2, RER, breathing power |
| 🌡️ Thermal | Temperatura centralna/peryferyjna |
| 🔋 **W' Reconstitution** | **Mapa wyczerpania/odnowy W', detekcja cykli, tempo regeneracji (Caen 2021)** |
| 🌡️ **Heat Strain** | **PSI/HSI z korektami środowiskowymi, ocena ryzyka, strategie chłodzenia** |
| 🩸 **SmO2 Thresholds** | **Detekcja progów SmO2 (LT1/LT2), analiza Feldmann 4-phase, Exp-Dmax** |

---

## 🔬 Walidacja Danych

Aplikacja automatycznie waliduje jakość danych:

- ✅ Minimalny czas trwania testu (5 min)
- ✅ Minimalna liczba stopni (3+)
- ✅ Monotoniczność wzrostu mocy
- ✅ Detekcja przerw w danych
- ✅ Stabilność kadencji

**Confidence Scores** — Każdy próg zawiera:
- Pewność detekcji (0-100%)
- Zakres wartości zamiast punktu
- Metodę detekcji
- Wizualny wskaźnik pewności

---

## 🧪 Testy

```bash
# Uruchomienie testów
python -m pytest tests/ -v

# Wynik
# ====================== 157 passed, 8 warnings ======================
```

---

## ⚡️ Optymalizacje Wydajnościowe

| Technika | Lokalizacja | Zysk |
|----------|-------------|------|
| NumPy vectorization | `biomech.py`, `session_analysis.py` | 10-50x |
| Numba JIT | `hrv.py`, `w_prime.py` | 5-20x |
| Polars CSV parsing | `utils.py` | 3-5x vs Pandas |
| @lru_cache | `stamina.py`, `power.py` | Cache hits |
| SQLite indexes | `session_store.py` | Query speed |
| Pre-ekstrakcja arrays | `fit_exporter.py` | 3-5x |

---

## 🔒 Bezpieczeństwo i Jakość Kodu (v0.4.0)

### Krytyczne Poprawki Bezpieczeństwa
- **RCE Elimination** — Usunięto `eval()` z `polars_adapter.py`, zastąpiono typowanym API `filter(col, op, value)`
- **XSS Protection** — `html.escape()` dla wszystkich user inputs w UI (`components.py`, `app.py`)
- **Path Traversal Prevention** — Sanitizacja nazw plików w `notes.py` (usuwanie `../`, `/`, `\`)
- **Input Mutation Prevention** — Kopiowanie DataFrame przed modyfikacją w `pipeline.py`, `utils.py`

### Stabilność Kodu
- **NameError Fix** — Dodano brakujący `import logging` + `logger` w `data_processing.py`
- **Dead Code Removal** — Usunięto duplikaty kodu w `ml_logic.py`, `utils.py`, `persistence.py`
- **Unreachable Code** — Naprawiony nieosiągalny `except` block w `data_processing.py`
- **Logging** — Zamieniono 40+ wywołań `print()` na `logger.info/warning/error` w modułach raportowania
- **Error Handling** — Dodano `try/except` w `notes.py` (`load_notes`, `save_notes`)
- **File Identity** — `hashlib.md5` zamiast `hash()` dla deterministic file hashing w `app.py`

### Dependency Management
- **Version Constraints** — `mlx>=0.5.0,<1.0.0`, `kaleido>=0.2.1`
- **Optional Dependencies** — pytest przeniesiony do `[project.optional-dependencies]`
- **Proper .gitignore** — Wykluczenia dla danych wrażliwych (`*.db`, `*.npz`, `user_settings.json`)

---

## 🔧 Changelog

### 🆕 v0.5.0 — Migracja funkcji kolarskich z Tri_Dashboard

**Nowe zakładki (10):**
| Zakładka | Sekcja | Opis |
|----------|--------|------|
| 🏁 Race Predictor | ⚡ Performance | Predykcja mocy wyścigowej z korektami środowiskowymi |
| 🛡️ Durability | ⚡ Performance | Durability Index, analiza sezonowa, rekomendacje |
| 📊 Training Distribution | ⚡ Performance | Time-in-Zone (power/HR/SmO2), balance score |
| ⏱️ TTE | ⚡ Performance | Time To Exhaustion na zadanej intensywności |
| 🔴 Intervals | ⚡ Performance | Detekcja i analiza interwałów |
| 🔋 W' Reconstitution | 🫀 Physiology | Mapa wyczerpania/odnowy W', cykle regeneracji |
| 🌡️ Heat Strain | 🫀 Physiology | PSI/HSI z korektami środowiskowymi |
| 🩸 SmO2 Thresholds | 🫀 Physiology | Detekcja progów SmO2, Exp-Dmax, Feldmann 4-phase |
| 🚨 Alerts | 🫀 Physiology | Alerty fizjologiczne (cardiac drift, SmO2 crash, HRV) |

**Nowe moduły obliczeniowe (10):**
- `w_prime_reconstitution.py` — Mapa rekonstytucji W' (Skiba + Caen bi-exponential)
- `race_predictor.py` — Predykcja mocy wyścigowej z korektami wiatr/temperatura/trasa
- `training_distribution.py` — Time-in-Zone dla power/HR/SmO2
- `durability.py` — Durability Index + analiza sezonowa + rekomendacje
- `heat_strain.py` — Enhanced Heat Strain Index z korektami środowiskowymi
- `smo2_thresholds.py` — Detekcja progów SmO2 (Moxy, Exp-Dmax)
- `smo2_analysis.py` — Zaawansowana analiza SmO2 (Feldmann 4-phase, HR coupling)
- `smo2/` — Pakiet SmO2 (classifier, calculator, types, constants)
- `plateau_detector.py` — Detekcja плато w trendach
- `alert_engine.py` — Silnik alertów fizjologicznych

**Nowe moduły eksportu (3):**
- `tcx_generator.py` — Generowanie plików TCX
- `zone_exporter.py` — Eksport stref mocy/HR do CSV
- `workout_exporter.py` — Eksport treningów do TrainingPeaks CSV

**Nowe moduły danych (3):**
- `db/athlete_profiles.py` — Tabela profili zawodnika (CP, W', VT, antropometria)
- `db/base.py` — Baza abstrakcyjna dla SQLite stores
- `social/reference_data.py` — Benchmarki percentylowe kolarstwa

**Adaptacje:**
- Dodano `calculate_w_prime_biexp` (Caen 2021) do `w_prime.py`
- Dodano `make_cache_key` do `cache_utils.py`
- Dodano `detect_exp_dmax`, `detect_smo2_breakpoints` do `smo2_breakpoints.py`
- Zaktualizowano `__init__.py` (83 eksportowane symbole)
- Zaktualizowano `app.py` — TabRegistry + rendering nowych zakładek

**Testy:** 157 passed, 0 regresji

### 🔧 Changelog (v0.4.0)

### 🔴 Critical Security Fixes
- **RCE via `eval()`** — Usunięto `eval(f"pl.{condition}")` z `polars_adapter.py`; nowe API: `filter(col, op, value)` z typowanymi parametrami
- **Audit Trail** — Zamieniono `print()` na `logger` w security-gating (`persistence.py:176,182`) — teraz decyzje gatingu są logowane z timestamp i severity

### 🟠 High Priority Fixes
- **Duplicate Docstring** — Usunięto zduplikowany body w `normalize_columns_pandas()` (`utils.py`)
- **Missing Logger** — Dodano `import logging` + `logger` w `data_processing.py` (eliminacja `NameError`)
- **Unreachable Except** — Usunięto nieosiągalny drugi `except` block w `data_processing.py`
- **Dead Code** — Usunięto zduplikowany `save_model` body + bug `sub_v` jako klucz w `ml_logic.py`
- **Path Traversal** — Sanitizacja `../`, `/`, `\` z nazw plików w `notes.py`; `NOTES_DIR` resolved do project root
- **XSS** — `html.escape()` na `group`/`section` w `show_breadcrumb()` (`components.py`)
- **Hardcoded Serial** — Zamieniono `12345678` na konfigurowalny `serial_number` w `fit_exporter.py`
- **Error Handling** — Dodano `try/except` z logowaniem w `load_notes()`/`save_notes()` (`notes.py`)
- **Print→Logger** — Zamieniono 40+ `print()` na `logger` w `persistence.py`, `figures/__init__.py`, `builder.py`, `summary_pdf.py`

### 🟡 Medium Priority Fixes
- **DataFrame Mutation** — `validate_test()` teraz kopiuje DataFrame przed modyfikacją kolumn (`pipeline.py`)
- **Settings Contract** — `save_settings()` zwraca `False` zamiast `True` gdy persistence wyłączone (`settings.py`)
- **Duplicate Import** — Usunięto zduplikowany `RAMP_METHOD_VERSION` import i `logger` w `persistence.py`
- **File Hash** — `hashlib.md5(content)` zamiast `hash(name+size)` w `app.py`

### 🟢 Low Priority Fixes
- **Safe Msg** — `safe_msg` zachowuje pełny komunikat z confidence ramp testu zamiast nadpisywania (`app.py`)
- **Dead Assignment** — Usunięto nieużywane `max_hr` w `app.py:328`
- **Duplicate Imports** — Wyczyszczone w `persistence.py`

---

## 🔧 Changelog (v0.3.1)

### 🐛 Critical Fixes (P0)
- **CHO Fractions** — Poprawione wartości 0.4/0.7/1.0 → 0.30/0.70/0.90 (badania pokazują ~30/70/90% nie 40/70/100%)
- **VO2max Formula** — Dodana korekcja GE (Gross Efficiency) dla dokładniejszej estymacji
- **W' Balance** — Zmieniono model liniowy na wykładniczy (Skiba model) dla rekonstytucji W'
- **DataFrame Mutation** — Naprawiona mutacja input DataFrame w `thermal.py`, `session_analysis.py`
- **DFA Quality Grade** — Naprawiona inwertowana logika porównania stringów (max('C', 'A') zwracało 'C')
- **Metrics Dict** — Usunięto DataFrame z metadanych (przyczyna problemów z serializacją)

### ⚠️ High Priority Fixes (P1)
- **Stamina Score** — Teraz uwzględnia parametr W' w obliczeniach (20% wagi)
- **VLamax Disclaimer** — Dodane ostrzeżenie o ±30% niepewności estymacji
- **VT1 Slope Threshold** — Zwiększone z 0.05 do 0.07 (mniej false positives)
- **Glycogen Model** — Naprawione podwójne liczenie modyfikatorów mechanicznych
- **HSI Formula** — Poprawione wagi: Temperatura 70%, HR 30% (wcześniej odwrotnie)
- **Summary Tab** — Naprawione hardcoded zera dla LT1/LT2 (teraz używa VT1/VT2 jako proxy)
- **HRV Cache** — Dodany limit LRU cache + SHA-256 zamiast MD5
- **df.columns Mutation** — Dodane `.copy()` przed modyfikacją w `thresholds.py`

### 🔨 Medium Priority Fixes (P2)
- **Work [kJ]** — Poprawione obliczenia dla próbek nie-1s (używa rzeczywistych dt)
- **VT1 < VT2 Validation** — Dodana walidacja i automatyczna korekta odwróconych wartości
- **CHO Base** — Zmniejszone z 30g/h do 20g/h przy niskiej intensywności
- **Debug Prints** — Usunięte printy debug z `hrv.py`
- **Double Logger** — Usunięty duplikat logger w `smo2_advanced.py`
- **File Hash** — SHA-256 zamiast prostego hash dla uniknięcia kolizji
- **XSS Protection** — Dodane `html.escape()` dla session_type w unsafe_allow_html

### 📝 Low Priority / UI (P3)
- **FRI Warning** — Dodany komunikat o wymaganiu min. 60 min sesji dla wiarygodnego FRI
- **VLamax UI Disclaimer** — Wyświetlane ostrzeżenie o niepewności w interpretacji
---

## 📝 License

MIT License — Zobacz [LICENSE](LICENSE) dla szczegółów.

---

## 👤 Autor

**Wielki Krzych** — [GitHub](https://github.com/WielkiKrzych)

<p align="center">
  <sub>Built with ❤️ using Streamlit, Pandas & NumPy</sub>
</p>

---

## Uwagi

**Zaktualizowano (v0.5.0):** Większość funkcji z Tri_Dashboard została przeniesiona do Analiza Kolarska.

**Nadal nieprzeniesione:**
- Archiwum testów rampowych (Ramp Archive)
- AI Coach
- Generowanie raportów PDF/PNG z sidebar
- Zakładka Vent - Progi Manuals

**Pozostałe sekcje w Podsumowaniu:**
1. Przebieg Treningu
2. Wentylacja (VE) i Oddechy (BR)
3. SmO2 vs THb w czasie
4. Threshold Discordance Index (TDI)
5. Estymacja VO2max z Niepewnością (CI95%)
6. Walidacja Danych i Pewność Progów
