"""Investigation into the capability of the tool to evaluate cycles in many configurations. The cycle specifications of 
the base cases (CHPC config files) are perturbed one at a time by -20 % and +20 %, after which the optimal cycle of 
every perturbed configuration is evaluated. Temperatures are perturbed in degrees Celsius, since a perturbation of 20 % 
in kelvin would place the heat source above the heat sink. The shaft efficiency is not perturbed, as +20 % exceeds 1.
Run from the root of the repository: python perturbation_study/perturbation_study.py
"""
import multiprocessing
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

from thermoplot import configure_matplotlib, thermoplot_cached
from CHPC.config import Config
from CHPC.logger import setup_logger
from CHPC.results import save_results, load_results
from CHPC.thermodynamics import solve_cycle, compute_performance, build_ts_data, _candidate_bounds, _cp_props
from CHPC.visualization import THERMOPLOT_CONFIG_DIR, TS_MARGINS

logger = setup_logger()

config_files = ["config/R1234ze(E)/CHPC.ini", "config/CO2/CHPC.ini", "config/MM/CHPC.ini"]
perturbation = 0.2

PARAMETERS = {
    "T_h_in": r"$T_{h,in}$", "T_c_in": r"$T_{c,in}$", "ṁ_h": r"$\dot{m}_h$", "cp_h": r"$c_{p,h}$",
    "ṁ_c": r"$\dot{m}_c$", "cp_c": r"$c_{p,c}$", "η_compr": r"$\eta_{compr}$", "η_turb": r"$\eta_{turb}$",
    "ΔT_pp_min_evap": r"$\Delta T_{pp,ev}$", "ΔT_pp_min_cond": r"$\Delta T_{pp,cond}$", "Q_out_req": r"$\dot{Q}_{out}$",
}



# Running the perturbed configurations
# ====================================
def perturbed_configurations(config_file):
    """Base configuration followed by the configurations with one specification perturbed by -20 % or +20 %.

    Returns:
        List of (parameter, sign, cycle_config, general_config), with parameter "base" and sign 0 for the base case.
    """
    config = Config(config_file)
    base, general_config = config.cycleConfig(), config.generalConfig()
    cases = [("base", 0, base, general_config)]
    for parameter in PARAMETERS:
        for sign in (-1, 1):
            cycle_config = dict(base)
            if parameter in ("T_h_in", "T_c_in"):
                cycle_config[parameter] = 273.15 + (base[parameter] - 273.15) * (1 + sign * perturbation)
            else:
                cycle_config[parameter] = base[parameter] * (1 + sign * perturbation)
            cases.append((parameter, sign, cycle_config, general_config))
    return cases


def _solve_case(case):
    """Optimal cycle of one configuration, summarized in the quantities discussed in chapter 3."""
    parameter, sign, cycle_config, general_config = case
    summary = dict(refrigerant=cycle_config["refrigerant"], parameter=parameter, sign=sign,
                   value=cycle_config.get(parameter, np.nan) if parameter != "base" else np.nan)
    try:
        c = solve_cycle(cycle_config, general_config, verbose=False)
    except Exception as e:
        summary.update(success=False, message=str(e))
        return summary
    perf = compute_performance(c, cycle_config, general_config)
    b = _candidate_bounds(cycle_config)
    trace = c["optimization_trace"]
    x = np.asarray(trace["x"])[np.argmin(trace["objective"])]
    # position of the optimum within the bounds, 0 at the lower and 1 at the upper bound
    position = {k: (v - b[k][0]) / (b[k][1] - b[k][0]) for k, v in zip(("PR", "T_ref_1", "s_ref_1", "T_ref_3"), x)}
    T_sat_2 = np.nan if c["supercritical_cycle"] else c["T_cond"]
    summary.update(
        success=True, COP_turb=perf["COP_turb"], COP_isenth=perf["COP_isenth"], PR=perf["PR"], VR_turb=perf["VR_turb"],
        ṁ_ref=perf["ṁ_ref"], T_ref_1=c["T_ref_1"], T_ev=c["T_ev"], superheat=c["T_ref_1"] - c["T_ev"],
        T_ref_3=c["T_ref_3"], subcooling=T_sat_2 - c["T_ref_3"], Q_ref_4=c["Q_ref_4"],
        supercritical=bool(p_ref_2_above_critical(c, cycle_config)), n_eval=len(trace["objective"]),
        position=position, ts=build_ts_data(c, cycle_config, general_config),
    )
    return summary


def p_ref_2_above_critical(cycle_data, cycle_config):
    return cycle_data["p_ref_2"] > _cp_props("Pcrit", f"REFPROP::{cycle_config['refrigerant']}")


def run_perturbation_study(config_files, output_dir="results/perturbation_study", processes=None):
    """Optimize every perturbed configuration of every config file in parallel, and save one results file per refrigerant.

    Returns:
        Paths of the results files.
    """
    cases = [case for f in config_files for case in perturbed_configurations(f)]
    logger.info(f"Running {len(cases)} configurations")
    with multiprocessing.Pool(processes) as pool:
        summaries = list(pool.imap(_solve_case, cases))
    files = []
    for refrigerant in dict.fromkeys(s["refrigerant"] for s in summaries):
        cases_ref = [s for s in summaries if s["refrigerant"] == refrigerant]
        files.append(save_results(Path(output_dir) / refrigerant / "data" / f"perturbation_study_{refrigerant}.npz",
                                  **{f"case_{i}": s for i, s in enumerate(cases_ref)}))
        logger.info(f"Saved: {files[-1]}")
    return files



# Post processing
# ===============
def _cases(results_file):
    results = load_results(results_file)
    return [results[f"case_{i}"] for i in range(len(results))]


def summarize_perturbation_study(results_file):
    """Log the range of the outcomes over all configurations of one refrigerant.

    Returns:
        Dictionary with the number of configurations, the number of feasible ones and the ranges of the outcomes.
    """
    cases = _cases(results_file)
    ok = [c for c in cases if c["success"]]
    summary = dict(refrigerant=cases[0]["refrigerant"], n=len(cases), feasible=len(ok))
    for key in ("COP_turb", "PR", "VR_turb", "superheat", "subcooling", "Q_ref_4"):
        values = np.array([c[key] for c in ok], dtype=float)
        summary[key] = (np.nanmin(values), np.nanmax(values)) if np.any(np.isfinite(values)) else (np.nan, np.nan)
    for key in ("PR", "T_ref_1", "s_ref_1", "T_ref_3"):
        pos = np.array([c["position"][key] for c in ok])
        summary[f"{key}_at_lower_bound"] = int(np.sum(pos < 0.005))
        summary[f"{key}_at_upper_bound"] = int(np.sum(pos > 0.995))
    logger.info(summary)
    for c in cases:
        if not c["success"]:
            logger.info(f"no feasible cycle for {c['parameter']} {'+' if c['sign'] > 0 else '-'}20 %: {c['message']}")
    return summary


def make_sensitivity_plot(results_files, output_dir="results/perturbation_study", figsize=(12.0, 4.8)):
    """Change of the optimal COP_turb with respect to the base case, for every perturbed specification and refrigerant. 
    Configurations without a feasible cycle are marked with a cross."""
    configure_matplotlib()
    fig, axes = plt.subplots(1, len(results_files), figsize=figsize, sharey=True)
    axes = np.atleast_1d(axes)
    labels = list(PARAMETERS.values())
    y = np.arange(len(labels))
    for ax, f in zip(axes, results_files):
        cases = _cases(f)
        base = next(c for c in cases if c["parameter"] == "base")
        labelled = set()
        for sign, colour, offset in ((-1, "#6ab0de", 0.2), (1, "#1a3a6b", -0.2)):
            for k, parameter in enumerate(PARAMETERS):
                c = next(c for c in cases if c["parameter"] == parameter and c["sign"] == sign)
                label = (r"$-20\,\%$" if sign < 0 else r"$+20\,\%$") if c["success"] else r"$\mathrm{infeasible}$"
                if c["success"]:
                    ax.barh(y[k] + offset, 100 * (c["COP_turb"] / base["COP_turb"] - 1), height=0.38, color=colour,
                            label=None if label in labelled else label)
                else:
                    ax.scatter(0, y[k] + offset, marker="x", color="#d64545", zorder=3, label=None if label in labelled else label)
                labelled.add(label)
        ax.axvline(0, color="black", lw=0.8)
        ax.set_title(rf"$\mathrm{{{base['refrigerant']}}}$, $\mathrm{{COP}}_{{\mathrm{{turb}}}} = {base['COP_turb']:.2f}$", fontsize=11)
        ax.set_xlabel(r"$\Delta \mathrm{COP}_{\mathrm{turb}}\ [\%]$")
        ax.grid(True, axis="x", alpha=0.25)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(labels)
    axes[0].invert_yaxis()
    axes[-1].legend(loc="lower right", fontsize=9, framealpha=0.85)
    fig.tight_layout()
    output_path = Path(output_dir) / "COP_turb_sensitivity.pdf"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=600, bbox_inches="tight")
    logger.info(f"Saved: {output_path}")
    return fig


def make_cycle_overlay_plot(results_file, thermoplot_config_file=None, margins=None):
    """Optimal cycles of all feasible configurations of one refrigerant in a single T-s diagram, with the base cycle 
    in a thicker line."""
    configure_matplotlib()
    cases = [c for c in _cases(results_file) if c["success"]]
    refrigerant = cases[0]["refrigerant"]
    m = TS_MARGINS if margins is None else {**TS_MARGINS, **margins}
    s_all = np.concatenate([np.asarray(c["ts"]["major"]["s"]) for c in cases])
    T_all = np.concatenate([np.asarray(c["ts"]["major"]["T"]) for c in cases])
    fluid = f"REFPROP::{refrigerant}"
    T_crit = _cp_props("Tcrit", fluid)
    s_crit = _cp_props("S", "P", _cp_props("Pcrit", fluid), "T", T_crit, fluid)
    s_lo, s_hi = min(s_all.min(), s_crit), max(s_all.max(), s_crit)
    T_lo, T_hi = min(T_all.min(), T_crit), max(T_all.max(), T_crit)
    ds, dT = s_hi - s_lo, T_hi - T_lo
    thermoplot_config_file = THERMOPLOT_CONFIG_DIR / "TS.ini" if thermoplot_config_file is None else thermoplot_config_file
    fig = thermoplot_cached(str(thermoplot_config_file), {
        "fluid_name": refrigerant,
        "S_range": [s_lo - ds * m["s_left"], s_hi + ds * m["s_right"]],
        "T_range": [T_lo - dT * m["T_bot"], T_hi + dT * m["T_top"]]})
    ax = fig.get_axes()[0]
    for c in cases:
        base = c["parameter"] == "base"
        ax.plot(c["ts"]["minor"]["s"], c["ts"]["minor"]["T"], color="green", lw=2.0 if base else 0.8,
                alpha=1.0 if base else 0.55, zorder=8 if base else 7)
        ax.scatter(c["ts"]["major"]["s"], c["ts"]["major"]["T"], color="orange", s=6 if base else 3, zorder=9)
    fig.tight_layout()
    output_path = Path(results_file).parents[1] / f"Perturbed Cycles - {refrigerant} - TS.pdf"
    fig.savefig(output_path, dpi=600, bbox_inches="tight")
    logger.info(f"Saved: {output_path}")
    return fig


if __name__ == "__main__":
    results_files = run_perturbation_study(config_files)
    for f in results_files:
        summarize_perturbation_study(f)
        make_cycle_overlay_plot(f)
    make_sensitivity_plot(results_files)
    plt.show()
