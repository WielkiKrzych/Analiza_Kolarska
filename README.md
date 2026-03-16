# 🚴 Analiza Kolarska

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Streamlit-1.30%2B-red?style=for-the-badge&logo=streamlit" alt="Streamlit">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/Tests-159%20passed-brightgreen?style=for-the-badge&logo=pytest" alt="Tests">
</p>

Profesjonalna aplikacja do analizy danych treningowych kolarskich z zaawansowaną wizualizacją i modelowaniem fizjologicznym.

---

## ⭐ Kluczowe Funkcje

| Moduł | Funkcje |
|-------|----------|
| **📊 Overview** | Raport KPI, Podsumowanie sesji, Krzywa mocy |
| **⚡ Performance** | Power, Biomech, Model (CP/W'), HR, Hematologia, Drift Maps |
| **🧠 Intelligence** | Nutrition, Limiters |
| **🫀 Physiology** | HRV, SmO2, Ventilation, Thermal |

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
   │ SQLite  │   │         │   │ FIT/CSV │
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
- **SQLite** — Baza danych sesji
- **Pytest** — Testy (159 passed)

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
│   │   ├── power.py           ⚡ Metryki mocy (NP, IF, TSS)
│   │   ├── hrv.py             💓 Analiza HRV
│   │   ├── smo2_advanced.py    🩸 SmO2 + dekonwolucja
│   │   ├── ventilatory.py      🫁 VT1/VT2 detection
│   │   ├── thresholds.py       📐 Wykrywanie progów
│   │   └── ...
│   ├── ui/                    🎨 Komponenty interfejsu
│   ├── db/                    💾 SQLite session store
│   ├── reporting/             📈 Generowanie raportów
│   └── export/                📤 Eksport (FIT, CSV)
│
├── services/
│   ├── session_analysis.py     🔄 Analiza sesji
│   └── session_orchestrator.py 🎭 Koordynacja
│
├── models/                    📋 Modele danych
├── signals/                  🔬 Przetwarzanie sygnałów
├── tests/                    🧪 Testy (159 passed)
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
# ====================== 159 passed, 8 warnings ======================
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

## 🔧 Changelog (v0.4.0)

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

Ta wersja jest uproszczoną wersją Tri_Dashboard, z której usunięto:
- Zakładki związane z progami wentylacyjnymi (Vent - Progi, Vent - Progi Manuals)
- Zakładki związane z progami SmO2 (SmO2 - Progi, SmO2 - Progi Manuals)
- Archiwum testów rampowych (Ramp Archive)
- AI Coach
- Generowanie raportów PDF/PNG z sidebar
- Zakładka Intervals (funkcjonalność przeniesiona do Biomech)
- Zakładka TTE (Time To Exhaustion)

**Z zakładki Podsumowanie usunięto:**
- Model Matematyczny CP
- Progi Wentylacyjne VT1/VT2
- Progi SmO2 LT1/LT2

Pozostałe sekcje w Podsumowaniu:
1. Przebieg Treningu
2. Wentylacja (VE) i Oddechy (BR)
3. SmO2 vs THb w czasie
4. Threshold Discordance Index (TDI)
5. Estymacja VO2max z Niepewnością (CI95%)
6. Walidacja Danych i Pewność Progów
