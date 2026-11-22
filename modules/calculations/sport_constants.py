"""
Sport-specific physiological time constants — single source of truth.

Consolidated from w_prime.py (bi-exponential W' reconstitution, Caen et al.
2021):

- ``BIEXP_RECOVERY_PARAMS`` — bi-exponential W' reconstitution below CP
  (Caen et al., 2021 EJAP): (tau_fast [s], tau_slow [s], A_fast).

Keep values in sync with the cited literature.
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
