"""Temperature-only estimate of alpha = dh_exp/dh_comp and of the ideal turbine-assisted COP.

Expansion  : saturated liquid at T_sink  -> isentropic expansion to T_source - Tpp.
Compression: saturated vapour at T_source - Tpp -> isentropic compression to T_sink + Tpp.
COP = Q_out / (W_in - W_turb) = (h_hot - h_liq) / (dh_comp - dh_exp)
"""
import CoolProp.CoolProp as CP

# --- set these to the values of your cycle specification table ---------------
T_SINK = 353.15      # K, sink temperature (high T)          <-- placeholder
T_SOURCE = 288.15    # K, source temperature (low T)         <-- placeholder
T_PP = 10.0          # K, pinch-point temperature difference <-- placeholder
FLUIDS = ["CO2", "R1234ze(E)"]
# -----------------------------------------------------------------------------


def h_TS(fl, T, s):
    """Enthalpy at (T, s); handles the two-phase region explicitly."""
    if T < CP.PropsSI("Tcrit", fl):
        sl = CP.PropsSI("S", "T", T, "Q", 0, fl)
        sv = CP.PropsSI("S", "T", T, "Q", 1, fl)
        if sl <= s <= sv:
            x = (s - sl) / (sv - sl)
            hl = CP.PropsSI("H", "T", T, "Q", 0, fl)
            hv = CP.PropsSI("H", "T", T, "Q", 1, fl)
            return hl + x * (hv - hl)
    return CP.PropsSI("H", "T", T, "S", s, fl)


def isentrope_estimate(refrigerant, T_sink=T_SINK, T_source=T_SOURCE, Tpp=T_PP):
    fl = f"REFPROP::{refrigerant}"
    Tcrit = CP.PropsSI("Tcrit", fl)
    T_evap = T_source - Tpp

    # Expansion: S(T_sink, Q=0) -> H(S, T_source - Tpp)
    T_liq = T_sink
    if T_sink >= Tcrit:            # no saturated liquid above the critical point
        T_liq = Tcrit - 0.01
        # print(f"[{refrigerant}] T_sink >= Tcrit: using T = Tcrit - 0.01 K for the liquid state")
    s_liq = CP.PropsSI("S", "T", T_liq, "Q", 0, fl)
    h_liq = CP.PropsSI("H", "T", T_liq, "Q", 0, fl)
    dh_exp = h_liq - h_TS(fl, T_evap, s_liq)

    # Compression: S(T_source - Tpp, Q=1) -> H(S, T_sink + Tpp)
    s_vap = CP.PropsSI("S", "T", T_evap, "Q", 1, fl)
    h_vap = CP.PropsSI("H", "T", T_evap, "Q", 1, fl)
    h_hot = h_TS(fl, T_sink + Tpp, s_vap)
    dh_comp = h_hot - h_vap

    alpha = dh_exp / dh_comp
    cop = (h_hot - h_liq) / (dh_comp - dh_exp)
    return dict(dh_exp=dh_exp, dh_comp=dh_comp, alpha=alpha, cop=cop,
                alpha_cop=alpha * cop)


if __name__ == "__main__":
    print(f"T_sink={T_SINK} K, T_source={T_SOURCE} K, Tpp={T_PP} K")
    print(f"{'fluid':<12}{'dh_exp':>10}{'dh_comp':>10}{'ratio':>8}{'COP':>8}{'ratio*COP':>11}")
    for name in FLUIDS:
        r = isentrope_estimate(name)
        print(f"{name:<12}{r['dh_exp']/1e3:>10.1f}{r['dh_comp']/1e3:>10.1f}"
              f"{r['alpha']:>8.3f}{r['cop']:>8.2f}{r['alpha_cop']:>11.3f}")