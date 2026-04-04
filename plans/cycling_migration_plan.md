# Cycling Features Migration Plan: Tri_Dashboard → Analiza_Kolarska

**Created:** 2026-04-04  
**Status:** Planning  
**Source:** `/Users/wielkikrzychmbp/Documents/Tri_Dashboard`  
**Target:** `/Users/wielkikrzychmbp/Documents/Analiza_Kolarska`

---

## Executive Summary

Port 50+ cycling-specific modules from Tri_Dashboard into Analiza_Kolarska across 6 phases. The target already has substantial cycling support — this migration is **additive only**. Key concerns are import path adjustments, merge conflicts with existing overlapping modules, and TabRegistry registration.

### Overlap Map (Critical — read before any phase)

| Area | Tri_Dashboard | Analiza_Kolarska | Action |
|------|--------------|-------------------|--------|
| Durability | `calculations/durability.py` | `calculations/stamina.py` | **Merge** — add `calculate_durability_by_season()`, `get_durability_recommendations()`, `method` param to existing stamina.py |
| SmO2 advanced | `calculations/smo2/` package (4 files) | `calculations/smo2_advanced.py` + `smo2_breakpoints.py` | **Merge** — port unique algorithms (ATT, Butterworth, Feldmann, BP2 typing) into target's existing files |
| SmO2 thresholds | `calculations/smo2_thresholds.py` | `calculations/smo2_breakpoints.py` | **Merge** — port unique features into target |
| SmO2 analysis | `calculations/smo2_analysis.py` | `calculations/smo2_advanced.py` | **Merge** — port unique features |
| Heat strain | `calculations/heat_strain.py` | `calculations/thermoregulation.py` | **Add** as new file — different focus (PSI/WBGT/cumulative strain vs core-temp kinetics) |
| Reporting | 5 files (report_io, report_generator, pdf_generator, index_manager, csv_export) | `reporting/persistence.py` + `summary_export.py` | **Merge** — port `csv_export.py` as new; skip 4 overlapping files |
| VT analysis | `ui/vent_*.py` (6 files) | `ui/vent.py` + `calculations/ventilatory.py` | **SKIP** — already merged in target |
| W' calculation | `calculations/w_prime_reconstitution.py` | `calculations/w_prime.py` | **Add** — reconstitution map is separate from base W' depletion |
| Shared UI | `ui/shared.py` + `ui/utils.py` | **DOES NOT EXIST** | **Copy** — foundational dependency for many UI tabs |
| DB base | `db/base.py` + `db/athlete_profiles.py` | `db/session_store.py` only | **Add** — athlete_profiles table + base class |
| TTE engine | N/A (engine in target) | `modules/tte.py` | UI only — port `ui/tte_ui.py` |
| Intervals engine | N/A (engine in target) | `modules/intervals.py` + `ai/interval_detector.py` | UI only — port `ui/intervals_ui.py` |

### Existing TabRegistry (18 tabs — do NOT modify existing entries)

```
report        → modules.ui.report.render_report_tab
power         → modules.ui.power.render_power_tab
biomech       → modules.ui.biomech.render_biomech_tab
model         → modules.ui.model.render_model_tab
hrv           → modules.ui.hrv.render_hrv_tab
smo2          → modules.ui.smo2.render_smo2_tab
hemo          → modules.ui.hemo.render_hemo_tab
vent          → modules.ui.vent.render_vent_tab
thermal       → modules.ui.thermal.render_thermal_tab
nutrition     → modules.ui.nutrition.render_nutrition_tab
limiters      → modules.ui.limiters.render_limiters_tab
thresholds    → modules.ui.threshold_analysis_ui.render_threshold_analysis_tab
history       → modules.ui.trends_history.render_trends_history_tab
community     → modules.ui.community.render_community_tab
import        → modules.ui.history_import_ui.render_history_import_tab
heart_rate    → modules.ui.heart_rate.render_hr_tab
summary       → modules.ui.summary.render_summary_tab
drift_maps    → modules.ui.drift_maps_ui.render_drift_maps_tab
```

---

## Phase 1: Backend Calculations (No UI Dependencies)

**Goal:** Port all Tier 1 calculation modules. These are pure Python — no Streamlit imports, no UI coupling.

### 1.1 New Files (Safe Copy)

| # | File | Source | Target | Notes |
|---|------|--------|--------|-------|
| 1 | `modules/calculations/w_prime_reconstitution.py` | Copy from Tri | `modules/calculations/w_prime_reconstitution.py` | Distinct from target's `w_prime.py` (base depletion). This adds reconstitution map analytics. Key function: `compute_w_prime_reconstitution_map(df, cp, w_prime_cap, model="biexp", sport=0)` |
| 2 | `modules/calculations/race_predictor.py` | Copy from Tri | `modules/calculations/race_predictor.py` | Standalone — CP/W' race power prediction with env/course adjustments. Key function: `predict_race_power(cp, w_prime, weight_kg, duration_min, ...)` |
| 3 | `modules/calculations/training_distribution.py` | Copy from Tri | `modules/calculations/training_distribution.py` | Time-in-Zone multi-modality engine (power/HR/SmO2). Key function: `calculate_training_distribution(df, cp, hr_max=None, ...)` |
| 4 | `modules/calculations/plateau_detector.py` | Copy from Tri | `modules/calculations/plateau_detector.py` | Trend plateau detection. Key function: `detect_plateau(values, dates, metric_name="", ...)` |
| 5 | `modules/calculations/alert_engine.py` | Copy from Tri | `modules/calculations/alert_engine.py` | Physiological alert dataclasses + engine. Key classes: `Alert`, `OvertrainingRiskIndex`, `AlertReport` |

**Import adjustments for all 1.1 files:**
- `from .common import ensure_pandas` → target has `modules.calculations.common` with same function — **keep relative import**
- `from .w_prime import ...` → target has `modules.calculations.w_prime` — **keep relative import**
- `from .thermal import ...` → target has `modules.calculations.thermal` — **keep relative import**
- Any absolute `from modules.X import Y` → verify target has equivalent path

### 1.2 New File: Heat Strain (Distinct from thermoregulation.py)

| # | File | Source | Target | Notes |
|---|------|--------|--------|-------|
| 6 | `modules/calculations/heat_strain.py` | Copy from Tri | `modules/calculations/heat_strain.py` | **Different module** from target's `thermoregulation.py`. Tri's version: PSI wrapper + WBGT approximation + cumulative strain tracking + risk categorization + recommendation engine. Target's: core-temp kinetics + cardiac drift/EF coupling. Both should coexist. Key function: `calculate_heat_strain_index_enhanced(df_pl, resting_hr=0.0, ...)` |

**Import adjustments:**
- May import from `modules.calculations.thermal` — verify API compatibility
- May import from `modules.calculations.common` — same in both

### 1.3 Merge: Durability → Stamina

**File:** `modules/calculations/stamina.py` (MODIFY existing)

Add these functions from Tri's `durability.py`:

```python
# 1. Add method parameter to existing calculate_durability_index()
#    Tri signature:  calculate_durability_index(df, min_duration_min=20, method="half")
#    Target current: calculate_durability_index(df, min_duration_min=30)  — half-only
#    Action: Add method="half" param, keep backward-compatible default
#    Implementation: port the "rolling" method branch from Tri

# 2. New function — seasonal analysis
def calculate_durability_by_season(df: pd.DataFrame, season_length_min: int = 5) -> pd.DataFrame:
    """Groups workouts by season windows, computes durability index per window."""
    # Port from Tri durability.py

# 3. New function — contextual recommendations
def get_durability_recommendations(di: float, workout_duration_min: float) -> list:
    """Returns list of recommendation strings based on DI level and duration."""
    # Port from Tri durability.py

# 4. Upgrade existing get_durability_interpretation()
#    Tri's version is more granular with longer-form text.
#    Action: Replace target's simple interpretation with Tri's detailed version
#    Risk: LOW — this is display text only, no API change
```

### 1.4 Merge: SmO2 Thresholds & Analysis

**File:** `modules/calculations/smo2_breakpoints.py` (MODIFY existing)

Port unique features from Tri's `smo2_thresholds.py`:
- ATT validation (`att_mm` parameter)
- Butterworth smoothing method switch
- Baseline-corrected ΔSmO2 calculation
- First-60s exclusion filter
- Exp-Dmax integration
- BP2 inflection typing
- 4-knot segmented cross-validation
- Multi-muscle MOT2 consistency check

**File:** `modules/calculations/smo2_advanced.py` (MODIFY existing)

Port unique features from Tri's `smo2_analysis.py`:
- Feldmann phase transition detection
- SmO2min → VO2 proxy estimation
- Context-aware SmO2 interpretation helper
- `SmO2AdvancedMetrics` dataclass field enhancements (if any missing)

**Strategy:** These are complex merges. Port incrementally — add each unique feature as a new function/parameter, then wire it into existing pipeline. Do NOT rewrite existing target algorithms.

### 1.5 Add: SmO2 Package (Calculator + Classifier)

**Decision: Add as new package alongside existing monolith files**

| # | File | Source | Target | Notes |
|---|------|--------|--------|-------|
| 7 | `modules/calculations/smo2/__init__.py` | Copy from Tri | `modules/calculations/smo2/__init__.py` | Facade API — adjust internal imports |
| 8 | `modules/calculations/smo2/calculator.py` | Copy from Tri | `modules/calculations/smo2/calculator.py` | `SmO2MetricsCalculator` class (slope, halftime reoxy, HR coupling, drift) |
| 9 | `modules/calculations/smo2/classifier.py` | Copy from Tri | `modules/calculations/smo2/classifier.py` | `SmO2LimiterClassifier.classify(...)`, recommendation mapping |
| 10 | `modules/calculations/smo2/types.py` | Copy from Tri | `modules/calculations/smo2/types.py` | `SmO2AdvancedMetrics`, `SmO2ThresholdResult` dataclasses — verify no conflicts with target's existing types in `smo2_advanced.py` |
| 11 | `modules/calculations/smo2/constants.py` | Copy from Tri | `modules/calculations/smo2/constants.py` | Limiter/T1/T2/artifact thresholds + recommendations |

**Import adjustments for SmO2 package:**
- `__init__.py`: Remove backward-compat import `from ..smo2_advanced import detect_smo2_thresholds_moxy` (target's smo2_advanced.py has different export names)
- Internal imports: `from .common import ...` → adjust to `from modules.calculations.common import ...` or keep relative if it works
- `classifier.py`: Uses `numba` + `cache` — verify target has `modules/cache_utils.py` (it does) and `modules/numba_utils.py` (it does)
- `types.py`: Check `SmO2AdvancedMetrics` dataclass — target's `smo2_advanced.py` may already define a version. If conflict, rename Tri's to `SmO2PackageMetrics` or merge fields

### 1.6 Update `modules/calculations/__init__.py`

Add new public exports:

```python
# New calculation modules
from .w_prime_reconstitution import compute_w_prime_reconstitution_map
from .race_predictor import predict_race_power
from .training_distribution import calculate_training_distribution
from .plateau_detector import detect_plateau
from .alert_engine import Alert, AlertReport, OvertrainingRiskIndex
from .heat_strain import calculate_heat_strain_index_enhanced
```

### Phase 1 Verification

```bash
# 1. Python import check — every new module must import cleanly
python -c "from modules.calculations.w_prime_reconstitution import compute_w_prime_reconstitution_map"
python -c "from modules.calculations.race_predictor import predict_race_power"
python -c "from modules.calculations.training_distribution import calculate_training_distribution"
python -c "from modules.calculations.plateau_detector import detect_plateau"
python -c "from modules.calculations.alert_engine import Alert, AlertReport"
python -c "from modules.calculations.heat_strain import calculate_heat_strain_index_enhanced"
python -c "from modules.calculations.smo2 import SmO2MetricsCalculator, SmO2LimiterClassifier"

# 2. Verify stamina.py still works with new functions
python -c "from modules.calculations.stamina import calculate_durability_by_season, get_durability_recommendations"

# 3. Verify existing modules NOT broken
python -c "from modules.calculations.stamina import calculate_durability_index"
python -c "from modules.calculations.smo2_advanced import detect_smo2_thresholds_moxy"
python -c "from modules.calculations.thermoregulation import ..."
python -c "from modules.calculations.w_prime import ..."
python -c "from modules.calculations.smo2_breakpoints import ..."

# 4. Compile check all modified files
python -m py_compile modules/calculations/stamina.py
python -m py_compile modules/calculations/smo2_breakpoints.py
python -m py_compile modules/calculations/smo2_advanced.py
python -m py_compile modules/calculations/__init__.py
```

---

## Phase 2: Database Layer — Athlete Profiles

**Goal:** Add athlete_profiles table to existing SQLite database, enabling per-athlete CP/W'/VT thresholds and anthropometrics.

### 2.1 New File: DB Base Class

| # | File | Source | Target | Notes |
|---|------|--------|--------|-------|
| 1 | `modules/db/base.py` | Copy from Tri | `modules/db/base.py` | `BaseStore(ABC)` abstract class with SQLite connection management |

**Import adjustments:**
- Tri: `from modules.config import DB_PATH` → Target: `from modules.config import Config` then use `Config.DB_PATH`
- Verify `Config.DB_PATH` exists in target's `modules/config.py` (it does)

### 2.2 New File: Athlete Profiles Store

| # | File | Source | Target | Notes |
|---|------|--------|--------|-------|
| 2 | `modules/db/athlete_profiles.py` | Copy from Tri | `modules/db/athlete_profiles.py` | Full CRUD for athlete profiles: CP, W', VT1/VT2 thresholds, anthropometrics (weight, height, age), profile/session reassignment logic |

**Import adjustments:**
- `from .base import BaseStore` → keep (local relative import)
- `from modules.config import DB_PATH` → `from modules.config import Config` then `Config.DB_PATH`
- Any `from modules.utils import ...` → verify equivalent exists in target's `modules/utils.py`

### 2.3 Modify: Session Store (Optional Enhancement)

**File:** `modules/db/session_store.py` (MODIFY existing — LOW priority)

- Consider adding optional `athlete_profile_id` column to sessions table
- Add filter-by-profile method if needed
- **DO NOT break existing session CRUD API** — this is purely additive
- Can defer to post-migration cleanup

### 2.4 Update `modules/db/__init__.py`

```python
from .base import BaseStore
from .session_store import SessionStore, SessionRecord
from .athlete_profiles import AthleteProfileStore, AthleteProfile
```

### Phase 2 Verification

```bash
# 1. Import check
python -c "from modules.db.base import BaseStore"
python -c "from modules.db.athlete_profiles import AthleteProfileStore, AthleteProfile"

# 2. Schema migration — verify table creation
python -c "
from modules.db.athlete_profiles import AthleteProfileStore
store = AthleteProfileStore()
store._ensure_table()  # Creates table if not exists
print('Table created/verified OK')
"

# 3. Verify existing session store still works
python -c "from modules.db.session_store import SessionStore"

# 4. Verify no DB file corruption
# Check that existing sessions table is intact after adding athlete_profiles
```

---

## Phase 3: UI Tabs — Tier 2 Features

**Goal:** Port all Tier 2 UI tabs, register them in TabRegistry. This is the largest phase.

### 3.0 Prerequisite: Shared UI Modules

**Target currently LACKS `modules/ui/shared.py` and `modules/ui/utils.py`.** These are foundational dependencies for most UI tabs and MUST be copied first.

| # | File | Source | Target | Exports |
|---|------|--------|--------|---------|
| 1 | `modules/ui/shared.py` | Copy from Tri | `modules/ui/shared.py` | `chart()`, `metric()`, `require_data()`, `dataframe()`, `alert()` |
| 2 | `modules/ui/utils.py` | Copy from Tri | `modules/ui/utils.py` | `parse_time_to_seconds()`, `format_time()`, `hash_dataframe()`, `hash_params()` |

**Import adjustments for shared.py:**
- Tri imports: `import streamlit as st`, `import plotly.graph_objects as go`, `import pandas as pd` — all available in target
- Check if Tri's `shared.py` imports from any Tri-specific calculation modules — adjust paths
- These are Streamlit helper functions — likely zero or minimal import changes needed

**Import adjustments for utils.py:**
- Pure utility functions — likely zero import changes needed
- Verify `hash_dataframe` / `hash_params` don't depend on Tri-specific modules

### 3.1 New UI Tab Files

| # | File | Source | Target | Render Function | Tab Key |
|---|------|--------|--------|----------------|---------|
| 3 | `modules/ui/race_predictor_ui.py` | Copy from Tri | `modules/ui/race_predictor_ui.py` | `render_race_predictor_tab()` | `race_predictor` |
| 4 | `modules/ui/durability_ui.py` | Copy from Tri | `modules/ui/durability_ui.py` | `render_durability_tab()` | `durability` |
| 5 | `modules/ui/heat_strain_ui.py` | Copy from Tri | `modules/ui/heat_strain_ui.py` | `render_heat_strain_tab()` | `heat_strain` |
| 6 | `modules/ui/w_prime_reconstitution_ui.py` | Copy from Tri | `modules/ui/w_prime_reconstitution_ui.py` | `render_w_prime_reconstitution_tab()` | `w_prime_recon` |
| 7 | `modules/ui/training_distribution_ui.py` | Copy from Tri | `modules/ui/training_distribution_ui.py` | `render_training_distribution_tab()` | `training_dist` |
| 8 | `modules/ui/tte_ui.py` | Copy from Tri | `modules/ui/tte_ui.py` | `render_tte_tab()` | `tte` |
| 9 | `modules/ui/intervals_ui.py` | Copy from Tri | `modules/ui/intervals_ui.py` | `render_intervals_tab()` | `intervals` |
| 10 | `modules/ui/smo2_thresholds.py` | Copy from Tri | `modules/ui/smo2_thresholds_tab.py` | `render_smo2_thresholds_tab()` | `smo2_thresholds` |
| 11 | `modules/ui/smo2_manual_thresholds.py` | Copy from Tri | `modules/ui/smo2_manual_thresholds.py` | `render_smo2_manual_thresholds_tab()` | `smo2_manual` |
| 12 | `modules/ui/alerts.py` | Copy from Tri | `modules/ui/alerts.py` | `render_alerts_tab()` | `alerts` |

> **NOTE on smo2_thresholds.py naming:** Target already has `modules/calculations/smo2_breakpoints.py`. To avoid confusion between calculation and UI files with same name, rename Tri's `modules/ui/smo2_thresholds.py` → `modules/ui/smo2_thresholds_tab.py`.

### 3.2 Summary Enhancement Files

| # | File | Source | Target | Notes |
|---|------|--------|--------|-------|
| 13 | `modules/ui/summary_calculations.py` | Copy from Tri | `modules/ui/summary_calculations.py` | Pure math helpers: `_calculate_np()`, `_estimate_cp_wprime()`, `_get_vent_metrics_for_power()`. No Streamlit imports. |
| 14 | `modules/ui/summary_thresholds.py` | Copy from Tri | `modules/ui/summary_thresholds.py` | VT/LT threshold renderers — may overlap with target's `ui/threshold_analysis_ui.py`. Review before copying. |
| 15 | `modules/ui/summary_charts.py` | Copy from Tri | `modules/ui/summary_charts.py` | Summary chart builders — integrate into existing summary tab or keep as helper module |

**For summary files:** These are helper modules consumed by the existing summary tab, not standalone tabs. Port them and evaluate integration with target's `modules/ui/summary.py`.

### 3.3 Common Import Adjustments (ALL UI Files)

Every UI file from Tri will need these import path fixes:

| Tri Import | Target Import | Reason |
|-----------|--------------|--------|
| `from modules.ui.shared import ...` | `from modules.ui.shared import ...` | Same (we just added it in 3.0) |
| `from modules.ui.utils import ...` | `from modules.ui.utils import ...` | Same (we just added it in 3.0) |
| `from modules.calculations.durability import ...` | `from modules.calculations.stamina import ...` | Merged into stamina.py in Phase 1 |
| `from modules.calculations.smo2_thresholds import ...` | `from modules.calculations.smo2_breakpoints import ...` | Merged into breakpoints in Phase 1 |
| `from modules.calculations.smo2_analysis import ...` | `from modules.calculations.smo2_advanced import ...` | Merged into advanced in Phase 1 |
| `from modules.db.athlete_profiles import ...` | `from modules.db.athlete_profiles import ...` | Same (Phase 2) |
| `from modules.export.workout_exporter import ...` | `from modules.export.workout_exporter import ...` | Same (Phase 4) |
| `from modules.calculations import (...)` | Verify each symbol exists in target's `__init__.py` | Phase 1 updates |
| `from modules.social.reference_data import ...` | `from modules.social.reference_data import ...` | Same (Phase 4) |

### 3.4 TTE UI — Special Handling

The target already has `modules/tte.py` (top-level module, NOT in calculations/) with:
- `compute_tte()`
- `compute_tte_result()`
- `batch_compute_tte_for_all_sessions()`

Tri's `tte_ui.py` likely imports TTE functions from `modules.calculations.tte`. Adjust:

```python
# Tri's pattern (will need changing):
from modules.calculations.tte import compute_tte, ...

# Target's actual location:
from modules.tte import compute_tte, compute_tte_result, batch_compute_tte_for_all_sessions
```

### 3.5 Intervals UI — Special Handling

Target has:
- `modules/intervals.py` — `detect_intervals(...)` (top-level module)
- `modules/ai/interval_detector.py` — `IntervalDetector.detect_intervals(...)`

Tri's `intervals_ui.py` likely imports from `modules.calculations.intervals`. Adjust:

```python
# Tri: from modules.calculations.intervals import detect_intervals
# Target: from modules.intervals import detect_intervals
```

### 3.6 Register New Tabs in `app.py`

**File:** `app.py` (MODIFY existing)

Add to `TabRegistry._tabs` dict (after existing 18 entries):

```python
# Phase 3 — New cycling tabs
"race_predictor": ("modules.ui.race_predictor_ui", "render_race_predictor_tab"),
"durability": ("modules.ui.durability_ui", "render_durability_tab"),
"heat_strain": ("modules.ui.heat_strain_ui", "render_heat_strain_tab"),
"w_prime_recon": ("modules.ui.w_prime_reconstitution_ui", "render_w_prime_reconstitution_tab"),
"training_dist": ("modules.ui.training_distribution_ui", "render_training_distribution_tab"),
"tte": ("modules.ui.tte_ui", "render_tte_tab"),
"intervals": ("modules.ui.intervals_ui", "render_intervals_tab"),
"smo2_thresholds": ("modules.ui.smo2_thresholds_tab", "render_smo2_thresholds_tab"),
"smo2_manual": ("modules.ui.smo2_manual_thresholds", "render_smo2_manual_thresholds_tab"),
"alerts": ("modules.ui.alerts", "render_alerts_tab"),
```

**Tab placement in UI layout:** Add new tabs to appropriate `st.tabs()` groups in `app.py`:

| Tab Key | Group | Suggested Label |
|---------|-------|-----------------|
| `race_predictor` | Performance (⚡) | 🏁 Race Predictor |
| `durability` | Performance (⚡) | 💪 Durability |
| `heat_strain` | Physiology (🫀) | 🌡️ Heat Strain |
| `w_prime_recon` | Performance (⚡) | 🔄 W' Reconstitution |
| `training_dist` | Performance (⚡) | 📊 Training Distribution |
| `tte` | Performance (⚡) | ⏱️ TTE |
| `intervals` | Performance (⚡) | 🔁 Intervals |
| `smo2_thresholds` | Physiology (🫀) | 🩸 SmO2 Thresholds |
| `smo2_manual` | Physiology (🫀) | ✏️ SmO2 Manual |
| `alerts` | Intelligence (🧠) | 🚨 Alerts |

### Phase 3 Verification

```bash
# 1. Import check for all new UI modules
python -c "from modules.ui.shared import chart, metric, require_data"
python -c "from modules.ui.utils import parse_time_to_seconds, format_time"
python -c "from modules.ui.race_predictor_ui import render_race_predictor_tab"
python -c "from modules.ui.durability_ui import render_durability_tab"
python -c "from modules.ui.heat_strain_ui import render_heat_strain_tab"
python -c "from modules.ui.w_prime_reconstitution_ui import render_w_prime_reconstitution_tab"
python -c "from modules.ui.training_distribution_ui import render_training_distribution_tab"
python -c "from modules.ui.tte_ui import render_tte_tab"
python -c "from modules.ui.intervals_ui import render_intervals_tab"
python -c "from modules.ui.smo2_thresholds_tab import render_smo2_thresholds_tab"
python -c "from modules.ui.smo2_manual_thresholds import render_smo2_manual_thresholds_tab"
python -c "from modules.ui.alerts import render_alerts_tab"

# 2. Verify TabRegistry has new entries
python -c "
from app import TabRegistry
print(f'Total tabs: {len(TabRegistry._tabs)}')  # Should be 28 (18 + 10)
assert 'race_predictor' in TabRegistry._tabs
assert 'durability' in TabRegistry._tabs
assert 'heat_strain' in TabRegistry._tabs
assert 'tte' in TabRegistry._tabs
assert 'alerts' in TabRegistry._tabs
print('All 10 new tabs registered OK')
"

# 3. Visual verification — launch app and click each new tab
streamlit run app.py
# Click through each new tab, verify no runtime errors
# Check browser console for Streamlit errors

# 4. LSP diagnostics on all new/modified files
```

---

## Phase 4: Exports — Tier 3

**Goal:** Add TCX generation, TrainingPeaks CSV export, and zone CSV export alongside existing FIT exporter.

### 4.1 New Export Files

| # | File | Source | Target | Notes |
|---|------|--------|--------|-------|
| 1 | `modules/export/workout_exporter.py` | Copy from Tri | `modules/export/workout_exporter.py` | TrainingPeaks CSV export — standalone utility class |
| 2 | `modules/export/tcx_generator.py` | Copy from Tri | `modules/export/tcx_generator.py` | TCX XML generation for Garmin/Strava upload |
| 3 | `modules/export/zone_exporter.py` | Copy from Tri | `modules/export/zone_exporter.py` | Power/HR zone CSV export |

**Import adjustments:**
- These are mostly standalone — they generate files from session data
- Verify they import from `modules.config` not Tri-specific paths
- Check if they depend on `modules.db` for session data — adjust to use target's `SessionStore`
- Verify `lxml` or `xml.etree` dependency (TCX generation) — both available in target

### 4.2 Add Reference Data

| # | File | Source | Target | Notes |
|---|------|--------|--------|-------|
| 4 | `modules/social/reference_data.py` | Copy from Tri | `modules/social/reference_data.py` | Cycling benchmark percentile tables — used by race_predictor and alerts |

**Import adjustments:**
- Pure data file (dicts/constants) — likely zero import changes
- Verify target has `modules/social/` directory (it does per exploration)

### 4.3 Update `modules/export/__init__.py`

```python
from .fit_exporter import FitExporter, PlatformSync
from .workout_exporter import WorkoutExporter  # new
from .tcx_generator import TCXGenerator  # new
from .zone_exporter import ZoneExporter  # new
```

### 4.4 Integration: Add Export Buttons to Relevant Tabs

After porting export modules, add export download buttons to existing/new tabs:
- **Summary tab** (`ui/summary.py`) — add TCX + TrainingPeaks + Zone CSV export buttons
- **Race predictor tab** (`ui/race_predictor_ui.py`) — add workout export
- **Durability tab** (`ui/durability_ui.py`) — add zone export
- **Training distribution tab** (`ui/training_distribution_ui.py`) — add zone CSV export

### Phase 4 Verification

```bash
# 1. Import check
python -c "from modules.export.workout_exporter import WorkoutExporter"
python -c "from modules.export.tcx_generator import TCXGenerator"
python -c "from modules.export.zone_exporter import ZoneExporter"
python -c "from modules.social.reference_data import ..."  # verify data loads

# 2. Functional test — verify exporters instantiate
python -c "
from modules.export.tcx_generator import TCXGenerator
from modules.export.workout_exporter import WorkoutExporter
from modules.export.zone_exporter import ZoneExporter
print('All exporters loaded OK')
"

# 3. Verify existing FIT exporter still works
python -c "from modules.export.fit_exporter import FitExporter, PlatformSync"

# 4. Visual check — verify export buttons appear in tabs
streamlit run app.py
```

---

## Phase 5: Reporting Enhancements — Tier 4

**Goal:** Add CSV export capabilities to reporting. Skip files that overlap with target's `persistence.py`.

### 5.1 Overlap Decision Matrix

| Tri File | Target Equivalent | Decision | Reason |
|----------|------------------|----------|--------|
| `report_io.py` | `persistence.py` (save/load) | **SKIP** | Fully covered — save/load report functions identical |
| `report_generator.py` | `persistence.py` (report generation flow) | **SKIP** | Fully covered — report assembly logic exists |
| `pdf_generator.py` | `persistence.py` (`_auto_generate_pdf`) | **SKIP** | Fully covered — PDF/DOCX generation exists |
| `index_manager.py` | `persistence.py` (`_update_index`) | **SKIP** | Fully covered — report indexing exists |
| `csv_export.py` | **NO EQUIVALENT** | **PORT** | Unique: `export_session_csv()`, `export_metrics_csv()` |

### 5.2 New File

| # | File | Source | Target | Notes |
|---|------|--------|--------|-------|
| 1 | `modules/reporting/csv_export.py` | Copy from Tri | `modules/reporting/csv_export.py` | Session and metrics CSV export — unique capability not in target |

**Import adjustments:**
- May import from `modules.reporting.persistence` for report data access
- Adjust any `from modules.db.session_store import ...` to use target's `SessionStore` API
- May import from `modules.config` — verify `Config` usage

### 5.3 Update `modules/reporting/__init__.py`

```python
from .persistence import save_ramp_test_report, generate_and_save_pdf, generate_ramp_test_pdf
from .summary_export import export_summary
from .csv_export import export_session_csv, export_metrics_csv  # new
```

### Phase 5 Verification

```bash
# 1. Import check
python -c "from modules.reporting.csv_export import export_session_csv, export_metrics_csv"

# 2. Verify existing reporting still works
python -c "from modules.reporting.persistence import save_ramp_test_report, generate_and_save_pdf"

# 3. Verify no import cycles
python -c "import modules.reporting; print('OK')"
```

---

## Phase 6: Advanced Features — Tier 5

**Goal:** Port advanced UI features. Lower priority — nice-to-have enhancements.

### 6.1 Vent Threshold Tabs — SKIP (with review)

**Decision: DO NOT PORT the 6 VT files.** Target already has `modules/ui/vent.py` and `modules/calculations/ventilatory.py` which merged all of Tri's split VT modules.

**Files to skip:**
- `modules/ui/vent_thresholds.py` → superseded by `ui/vent.py`
- `modules/ui/vent_thresholds_charts.py` → superseded by `ui/vent.py`
- `modules/ui/vent_thresholds_timeline.py` → superseded by `ui/vent.py`
- `modules/ui/vent_thresholds_display.py` → superseded by `ui/vent.py`
- `modules/ui/vent_theory.py` → review for unique educational content only
- `modules/ui/manual_thresholds.py` → review for unique manual VT entry UI only

**Action items:**
1. Quickly scan `vent_theory.py` for educational/theory content not in target's vent tab — if found, integrate as a section
2. Quickly scan `manual_thresholds.py` for manual VT threshold entry UI not in target — if found, integrate into `ui/vent.py`

### 6.2 New UI Files

| # | File | Source | Target | Render Function | Tab Key | Notes |
|---|------|--------|--------|----------------|---------|-------|
| 1 | `modules/ui/ramp_archive.py` | Copy from Tri | `modules/ui/ramp_archive.py` | `render_ramp_archive_tab()` | `ramp_archive` | Ramp test archive browser — may depend on reporting persistence |
| 2 | `modules/ui/ai_coach.py` | Copy from Tri | `modules/ui/ai_coach.py` | `render_ai_coach_tab()` | `ai_coach` | AI coaching recommendations — may depend on ML infrastructure |

### 6.3 Import Adjustments

- `ramp_archive.py`: Likely imports from `modules.reporting.persistence` for archived reports — adjust to target's API
- `ai_coach.py`: May depend on ML models or external APIs — verify target has equivalent infrastructure in `modules/ai/`

### 6.4 Register in TabRegistry

```python
# Phase 6 tabs — add to TabRegistry._tabs
"ramp_archive": ("modules.ui.ramp_archive", "render_ramp_archive_tab"),
"ai_coach": ("modules.ui.ai_coach", "render_ai_coach_tab"),
```

**Tab placement:**
| Tab Key | Group | Suggested Label |
|---------|-------|-----------------|
| `ramp_archive` | Overview (📊) or separate | 📁 Ramp Archive |
| `ai_coach` | Intelligence (🧠) | 🤖 AI Coach |

### Phase 6 Verification

```bash
# 1. Import check
python -c "from modules.ui.ramp_archive import render_ramp_archive_tab"
python -c "from modules.ui.ai_coach import render_ai_coach_tab"

# 2. TabRegistry check
python -c "
from app import TabRegistry
print(f'Total tabs: {len(TabRegistry._tabs)}')  # Should be 30 (18 + 10 + 2)
assert 'ramp_archive' in TabRegistry._tabs
assert 'ai_coach' in TabRegistry._tabs
print('All tabs registered OK')
"

# 3. Visual verification
streamlit run app.py
# Click Ramp Archive and AI Coach tabs
```

---

## Cross-Cutting Concerns

### Import Path Mapping Reference

| Tri_Dashboard Pattern | Analiza_Kolarska Pattern |
|----------------------|--------------------------|
| `from modules.calculations.durability import ...` | `from modules.calculations.stamina import ...` |
| `from modules.calculations.smo2_thresholds import ...` | `from modules.calculations.smo2_breakpoints import ...` |
| `from modules.calculations.smo2_analysis import ...` | `from modules.calculations.smo2_advanced import ...` |
| `from modules.calculations.tte import ...` | `from modules.tte import ...` |
| `from modules.calculations.intervals import ...` | `from modules.intervals import ...` |
| `from modules.db.session_store import ...` | `from modules.db.session_store import ...` (same) |
| `from modules.config import DB_PATH` | `from modules.config import Config` then `Config.DB_PATH` |
| `from modules.ui.shared import ...` | `from modules.ui.shared import ...` (new, copied in Phase 3) |
| `from modules.ui.utils import ...` | `from modules.ui.utils import ...` (new, copied in Phase 3) |
| `from modules.calculations.common import ...` | `from modules.calculations.common import ...` (same) |
| `from modules.calculations.w_prime import ...` | `from modules.calculations.w_prime import ...` (same) |
| `from modules.calculations.thermal import ...` | `from modules.calculations.thermal import ...` (same) |

### Dependency Check

All external dependencies are already present in both `pyproject.toml` files:
- `streamlit`, `pandas`, `polars`, `plotly`, `numpy`, `scipy`
- `neurokit2`, `matplotlib`, `statsmodels`
- `python-docx`, `numba`, `kaleido`
- `python-dotenv`, `requests`

**No new pip dependencies required.**

### Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Import path mismatch causing ImportError | High | Medium | Systematic find-and-replace using mapping table above |
| stamina.py merge breaks existing durability API | Medium | High | Add new functions only; upgrade interpretation separately; run existing tests |
| SmO2 merge conflicts between package and monolith | Medium | High | Keep both coexist — package for calculator/classifier/types, monolith for advanced analysis |
| UI tabs reference Tri-specific session data format | Medium | Medium | Verify session DataFrame schema matches between projects before Phase 3 |
| TabRegistry key collision with existing tabs | Low | Low | All proposed keys verified unique vs existing 18 |
| Circular imports between new modules | Low | High | Phase 1 modules are leaf deps; UI depends on calcs only; no cross-phase cycles |
| SmO2 dataclass name collision | Medium | Medium | Tri's `SmO2AdvancedMetrics` in types.py vs target's in smo2_advanced.py — rename or merge |

---

## File Count Summary

| Phase | New Files | Modified Files | Skipped Files |
|-------|----------|---------------|---------------|
| Phase 1: Backend Calcs | 11 | 4 (stamina.py, smo2_breakpoints.py, smo2_advanced.py, __init__.py) | 0 |
| Phase 2: Database | 2 | 2 (session_store.py optional, db/__init__.py) | 0 |
| Phase 3: UI Tabs | 15 | 2 (app.py, ui/__init__.py optional) | 0 |
| Phase 4: Exports | 4 | 1 (export/__init__.py) | 0 |
| Phase 5: Reporting | 1 | 1 (reporting/__init__.py) | 4 (overlap with persistence.py) |
| Phase 6: Advanced | 2 | 1 (app.py already modified) | 6 (VT already merged) |
| **Total** | **35** | **~10** | **10** |

---

## Execution Order Checklist

- [ ] **Phase 1.1:** Copy 5 standalone calculation files (w_prime_reconstitution, race_predictor, training_distribution, plateau_detector, alert_engine)
- [ ] **Phase 1.2:** Copy heat_strain.py
- [ ] **Phase 1.3:** Merge durability → stamina.py (3 new functions + 1 interpretation upgrade)
- [ ] **Phase 1.4:** Merge SmO2 thresholds → smo2_breakpoints.py (unique algorithms)
- [ ] **Phase 1.5:** Merge SmO2 analysis → smo2_advanced.py (unique features)
- [ ] **Phase 1.6:** Add smo2/ package (5 files: __init__, calculator, classifier, types, constants)
- [ ] **Phase 1.7:** Update calculations/__init__.py with new exports
- [ ] **Phase 1.8:** **VERIFY** — all Phase 1 imports + existing module integrity
- [ ] **Phase 2.1:** Copy db/base.py (adjust Config.DB_PATH)
- [ ] **Phase 2.2:** Copy db/athlete_profiles.py
- [ ] **Phase 2.3:** Optionally modify session_store.py (athlete FK)
- [ ] **Phase 2.4:** Update db/__init__.py
- [ ] **Phase 2.5:** **VERIFY** — DB table creation + existing store integrity
- [ ] **Phase 3.0:** Copy ui/shared.py + ui/utils.py (prerequisite)
- [ ] **Phase 3.1:** Copy 10 UI tab files + 3 summary helper files
- [ ] **Phase 3.2:** Rename smo2_thresholds.py → smo2_thresholds_tab.py
- [ ] **Phase 3.3:** Adjust ALL imports per mapping table (systematic find-replace)
- [ ] **Phase 3.4:** Fix TTE imports (modules.calculations.tte → modules.tte)
- [ ] **Phase 3.5:** Fix Intervals imports (modules.calculations.intervals → modules.intervals)
- [ ] **Phase 3.6:** Register 10 new tabs in app.py TabRegistry
- [ ] **Phase 3.7:** Add tabs to appropriate st.tabs() groups in app.py layout
- [ ] **Phase 3.8:** **VERIFY** — import check + visual tab test (all 28 tabs)
- [ ] **Phase 4.1:** Copy 3 export files (workout_exporter, tcx_generator, zone_exporter)
- [ ] **Phase 4.2:** Copy reference_data.py to modules/social/
- [ ] **Phase 4.3:** Update export/__init__.py
- [ ] **Phase 4.4:** Add export buttons to relevant tabs (summary, race_predictor, durability, training_dist)
- [ ] **Phase 4.5:** **VERIFY** — exports load + visual check
- [ ] **Phase 5.1:** Copy csv_export.py (only unique reporting file)
- [ ] **Phase 5.2:** Update reporting/__init__.py
- [ ] **Phase 5.3:** **VERIFY** — import + no cycles
- [ ] **Phase 6.1:** Review vent_theory.py + manual_thresholds.py for unique features (likely skip)
- [ ] **Phase 6.2:** Copy ramp_archive.py + ai_coach.py
- [ ] **Phase 6.3:** Register 2 new tabs in TabRegistry
- [ ] **Phase 6.4:** **VERIFY** — full app launch, all 30 tabs functional
- [ ] **FINAL REGRESSION:** Launch app → click every tab → verify zero errors → confirm existing 18 tabs untouched
