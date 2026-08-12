"""
Sport-specific physiological time constants — single source of truth.

Consolidated from w_prime.py (bi-exponential W' reconstitution, Caen et al.
2021) and mpa.py (MPA/W'bal envelope, Sufferfest/Wahoo model). The two
parameter sets are intentionally different because they model different
recovery processes:

- ``BIEXP_RECOVERY_PARAMS`` — bi-exponential W' reconstitution below CP
  (Caen et al., 2021 EJAP): (tau_fast [s], tau_slow [s], A_fast).
- ``MPA_RECOVERY_PARAMS`` — effective tau used in
  MPA = W'_bal / tau + CP (Skiba/Sufferfest): (tau [s], tau_long [s],
  fast_fraction).

Keep values in sync with the cited literature; do not merge the two sets.
"""
from __future__ import annotations

# ── Bi-exponential W' reconstitution (Caen et al., 2021) ──────────────────
# Used by calculate_w_prime_biexp in w_prime.py.
#   sport: 0 = cycling, 1 = running, 2 = swimming
BIEXP_RECOVERY_PARAMS: dict[int, tuple[float, float, float]] = {
    0: (50.0, 400.0, 0.65),  # cycling:  (tau_fast, tau_slow, A_fast)
    1: (30.0, 300.0, 0.70),  # running
    2: (20.0, 200.0, 0.75),  # swimming
}

# ── MPA / W'bal envelope (Skiba 2012, Sufferfest/Wahoo model) ──────────────
# Used by mpa.py for the instantaneous MPA = W'_bal / tau + CP formula.
#   sport: 0 = cycling, 1 = running, 2 = swimming
MPA_RECOVERY_PARAMS: dict[int, tuple[float, float, float]] = {
    0: (120.0, 600.0, 0.50),  # Cycling
    1: (150.0, 750.0, 0.45),  # Running
    2: (90.0, 500.0, 0.55),   # Swimming
}
