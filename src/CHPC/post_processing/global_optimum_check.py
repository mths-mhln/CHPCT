"""Investigation into whether the optimizer finds the global maximum COP of a CHPC config file. Three checks are made:
1) the optimization is repeated for several seeds of the differential evolution algorithm, which should all 
   converge to the same cycle,
2) the candidates evaluated by the optimizer are shown in a scatter matrix of the design space, and
3) the coverage of the design space by the candidates is quantified, with the share of the design space that has 
   been visited, and with the centred L2 discrepancy compared with reference samples, such that it can be interpreted.
Run from the root of the repository: python -m CHPC.post_processing.global_optimum_check
"""
import multiprocessing
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import qmc

from thermoplot import configure_matplotlib
from CHPC.utils.config import Config
from CHPC.utils.logger import setup_logger
from CHPC.utils.results import save_results, load_results
from CHPC.cycle_evaluation.thermodynamics import solve_cycle, compute_performance, _candidate_bounds

logger = setup_logger()

config_file = "config/R1234ze(E)/CHPC.ini"
seeds = [42, 1, 2, 3, 4, 5, 6, 7]

VARIABLES = [r"$PR$", r"$T_{ref,1}$", r"$s_{ref,1}$", r"$T_{ref,3}$"]
UNITS = [r"$[-]$", r"$[\mathrm{K}]$", r"$[\mathrm{J/kg/K}]$", r"$[\mathrm{K}]$"]



# Running the optimizations
# =========================
def _run_seed(args):
    """Optimize the cycle of a config file for one seed of the differential evolution algorithm, and save the results."""
    config_file, seed, output_dir = args
    config = Config(config_file)
    cycle_config, general_config = config.cycleConfig(), config.generalConfig()
    general_config["de_seed"] = seed
    cycle_data = solve_cycle(cycle_config, general_config, verbose=False)
    perf = compute_performance(cycle_data, cycle_config, general_config)
    return save_results(Path(output_dir) / cycle_config["refrigerant"] / "data" / f"seed_{seed}.npz",
                        cycle_config=cycle_config, general_config=general_config, cycle_data=cycle_data, perf=perf)


def run_global_optimum_check(config_file, seeds, output_dir="results/global_optimum_check", processes=None):
    """Optimize the cycle for every seed, in parallel since the optimizations are independent.

    Returns:
        Paths of the results files, in the order of the seeds.
    """
    with multiprocessing.Pool(processes) as pool:
        return pool.map(_run_seed, [(config_file, seed, output_dir) for seed in seeds])



# Coverage of the design space
# ============================
def coverage_metrics(x, bounds, n_bins=5, n_reference=5, seed=0):
    """Quantify how well the candidates cover the design space, normalized to the unit hypercube by the bounds.

    The share of visited cells is the fraction of the n_bins^d cells of equal size that contain at least one candidate. 
    The centred L2 discrepancy (CD) measures the deviation from a uniform distribution, and is 0 for a perfectly uniform 
    distribution of infinitely many points. To interpret its value, it is compared with that of a random uniform sample 
    of the same size, and with that of the same number of points placed in the centre of the design space.

    Returns:
        Dictionary with the number of candidates, the share of visited cells and the discrepancies.
    """
    lo, hi = np.array(bounds).T
    u = np.clip((np.asarray(x) - lo) / (hi - lo), 0.0, 1.0)
    n, d = u.shape
    cells = np.minimum((u * n_bins).astype(int), n_bins - 1)
    visited = len({tuple(c) for c in cells}) / n_bins**d
    rng = np.random.default_rng(seed)
    return dict(
        n=n,
        visited_cells=visited,
        CD=qmc.discrepancy(u, method="CD", workers=-1),
        CD_random=np.mean([qmc.discrepancy(rng.random((n, d)), method="CD", workers=-1) for _ in range(n_reference)]),
        CD_centre=qmc.discrepancy(np.full((n, d), 0.5), method="CD"),
    )



# Post processing
# ===============
def _search_bounds(cycle_config):
    b = _candidate_bounds(cycle_config)
    return [b["PR"], b["T_ref_1"], b["s_ref_1"], b["T_ref_3"]]


def make_candidate_scatter_matrix(results_file, other_results_files=(), output_dir=None, figsize=(10.0, 10.0)):
    """Scatter matrix of all candidates evaluated during an optimization, in the design space spanned by the bounds. 
    Infeasible candidates are grey, feasible candidates are coloured by their COP_turb. The optimum is marked with a 
    red star, and the optima of the other results files (other seeds) with black crosses.
    """
    configure_matplotlib()
    results = load_results(results_file)
    trace = results["cycle_data"]["optimization_trace"]
    x, failed, objective = np.asarray(trace["x"]), np.asarray(trace["failed"], dtype=bool), np.asarray(trace["objective"])
    bounds = _search_bounds(results["cycle_config"])
    best = x[np.argmin(objective)]
    others = [np.asarray(load_results(f)["cycle_data"]["optimization_trace"]["x"])[
        np.argmin(load_results(f)["cycle_data"]["optimization_trace"]["objective"])] for f in other_results_files]

    d = len(VARIABLES)
    fig, axes = plt.subplots(d, d, figsize=figsize)
    for i in range(d):
        for j in range(d):
            ax = axes[i, j]
            if j > i:
                ax.axis("off")
                continue
            if i == j:
                bins = np.linspace(*bounds[i], 31)
                ax.hist(x[:, i], bins=bins, color="#bbbbbb", label=r"$\mathrm{all}$")
                ax.hist(x[~failed, i], bins=bins, color="#1a3a6b", label=r"$\mathrm{feasible}$")
                ax.set_yticks([])
            else:
                ax.scatter(x[failed, j], x[failed, i], s=1, color="#bbbbbb", alpha=0.3, rasterized=True)
                sc = ax.scatter(x[~failed, j], x[~failed, i], s=2, c=-objective[~failed], cmap="viridis", rasterized=True)
                for other in others:
                    ax.scatter(other[j], other[i], marker="x", s=40, color="black", zorder=4)
                ax.scatter(best[j], best[i], marker="*", s=160, color="red", edgecolor="black", linewidth=0.6, zorder=5)
                ax.set_ylim(bounds[i])
            ax.set_xlim(bounds[j])
            if i == d - 1:
                ax.set_xlabel(f"{VARIABLES[j]} {UNITS[j]}")
            else:
                ax.set_xticklabels([])
            if j == 0 and i > 0:
                ax.set_ylabel(f"{VARIABLES[i]} {UNITS[i]}")
            elif j > 0:
                ax.set_yticklabels([])
    axes[0, 0].legend(loc="upper right", fontsize=9, framealpha=0.85)
    cax = fig.add_axes([0.62, 0.72, 0.3, 0.025])
    fig.colorbar(sc, cax=cax, orientation="horizontal", label=r"$\mathrm{COP}_{\mathrm{turb}}\ [-]$")
    fig.subplots_adjust(wspace=0.08, hspace=0.08)

    refrigerant = results["cycle_config"]["refrigerant"]
    output_dir = Path(results_file).parents[1] if output_dir is None else Path(output_dir)
    output_path = output_dir / f"Candidate Scatter Matrix - {refrigerant}.pdf"
    fig.savefig(output_path, dpi=600, bbox_inches="tight")
    logger.info(f"Saved: {output_path}")
    return fig


def summarize_global_optimum_check(results_files):
    """Log the optimum of every seed, and the coverage of the design space by the candidates of the first seed.

    Returns:
        List with the optimum of every seed, and the coverage metrics of the initial population and all candidates.
    """
    optima = []
    for f in results_files:
        r = load_results(f)
        c, trace = r["cycle_data"], r["cycle_data"]["optimization_trace"]
        optima.append(dict(seed=int(r["general_config"]["de_seed"]), COP_turb=r["perf"]["COP_turb"], PR=c["PR"],
                           T_ref_1=c["T_ref_1"], s_ref_1=c["s_ref_1"], T_ref_3=c["T_ref_3"], n_eval=len(trace["objective"])))
        logger.info("seed {seed:3d}: COP_turb {COP_turb:.4f}, PR {PR:.3f}, T_ref_1 {T_ref_1:.2f} K, s_ref_1 {s_ref_1:.1f} J/kg/K, "
                    "T_ref_3 {T_ref_3:.2f} K, {n_eval} evaluations".format(**optima[-1]))
    cop = np.array([o["COP_turb"] for o in optima])
    logger.info(f"COP_turb over all seeds: {cop.min():.4f} to {cop.max():.4f} (spread {100 * (cop.max() - cop.min()) / cop.max():.3f} %)")

    r = load_results(results_files[0])
    x = np.asarray(r["cycle_data"]["optimization_trace"]["x"])
    bounds = _search_bounds(r["cycle_config"])
    n_population = int(r["general_config"].get("de_popsize", 30)) * len(bounds)
    coverage = {"initial population": coverage_metrics(x[:n_population], bounds), "all candidates": coverage_metrics(x, bounds)}
    for name, m in coverage.items():
        logger.info(f"{name}: {m['n']} candidates, {100 * m['visited_cells']:.1f} % of the cells visited, CD {m['CD']:.4f} "
                    f"(random sample {m['CD_random']:.4f}, all in the centre {m['CD_centre']:.4f})")
    return optima, coverage


if __name__ == "__main__":
    results_files = run_global_optimum_check(config_file, seeds)
    summarize_global_optimum_check(results_files)
    make_candidate_scatter_matrix(results_files[0], other_results_files=results_files[1:])
    plt.show()
