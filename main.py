import os
import sys
cwd = os.getcwd()
sys.path.append(f'{cwd}/test/system_tests/')

from CHPC.utils.config import Config
from CHPC.cycle_evaluation.thermodynamics import solve_cycle, compute_performance, build_ts_data, build_ph_data
from CHPC.COP_vs_eff.cop_efficiency_sweep import run_cop_vs_eff_investigation
from CHPC.utils.results import save_results, method_suffix
from CHPC.utils.logger import setup_logger

from rich.console import Console
from rich.table import Table

import numpy as np
import timeit


logger = setup_logger()

# config file of the analysis. CHPC.ini evaluates a single cycle, COP_vs_eff.ini the COP for a grid of
# turbine and compressor efficiencies. The cycle calculation method is selected in the config file.
config_file = "config/R1234ze(E)/CHPC.ini"



def main(config_file: str, perform_verification: bool = False) -> None:
    """Run the analysis specified in the config file, and save its results to the results folder.
    The diagrams are made afterwards with postprocess.py.

    Args:
        config_file: Path to the .ini file with the analysis specifications.
        perform_verification: Whether to run verification checks before analysis.
    """
    config = Config(config_file)
    cycle_config = config.cycleConfig()
    general_config = config.generalConfig()

    # Perform code verification:
    if perform_verification:
        from verification import verification
        verification(verification_table=True, generate_thdy_diagrams=False)

    # Select which analysis branch to run from the configuration.
    analysis_type = general_config["analysis_type"]

    # Branch 1: solve one cycle, print KPIs, and save the cycle data for post processing.
    if analysis_type == "CHPC":
        logger.info(f"Evaluating conceptual heat pump cycle ({general_config['calculation_method']})")
        cycle_data = solve_cycle(cycle_config, general_config, verbose=False)
        perf = compute_performance(cycle_data, cycle_config, general_config)
        table = Table(title=f"Conceptual Heat Pump Cycle - {cycle_config['refrigerant']}", show_lines=False)
        table.add_column("Symbol", style="cyan", no_wrap=True)
        table.add_column("Value", justify="right")
        table.add_column("Unit", justify="center")
        table.add_column("Description", style="dim")
        rows = [
            ("COP_is",      f"{perf['COP_is']:.2f}",        "-",  "Isentropic coefficient of performance"),
            ("COP_turb",    f"{perf['COP_turb']:.2f}",       "-",  "Turbine-based coefficient of performance"),
            ("COP_isenth",  f"{perf['COP_isenth']:.2f}",     "-",  "Isenthalpic coefficient of performance"),
            ("PR",          f"{perf['PR']:.2f}",             "-",  "Pressure ratio across the compressor"),
            ("VR_turb",     f"{perf['VR_turb']:.2f}",        "-",  "Volumetric expansion ratio across the turbine"),
            ("ṁ_ref",       f"{perf['ṁ_ref']:.3f}",         "kg/s",  "Mass flow rate of the refrigerant"),
            ("Ẇ_turb",      f"{perf['Ẇ_turb']:.0f}",         "W",  "Turbine power output"),
            ("Ẇ_comp_turb", f"{perf['Ẇ_comp_turb']:.0f}",     "W",  "Additional compressor power input if turbine"),
            ("Q_in_turb",        f"{perf['Q_in_turb']:.0f}",           "W",  "Heat absorbed by the cycle (actual)"),
            ("Q_in_isenth", f"{perf['Q_in_isenth']:.0f}",    "W",  "Heat absorbed under isenthalpic process"),
            ("Q_out",       f"{perf['Q_out']:.0f}",          "W",  "Heat rejected by the cycle")
        ]
        for symbol, value, unit, description in rows:
            table.add_row(symbol, value, unit, description)
        Console().print(table)

        # State point table of the resulting cycle (same keys for both calculation methods).
        cycle_table = Table(title=f"Cycle State Points - {cycle_config['refrigerant']}", show_lines=False)
        cycle_table.add_column("Point", style="cyan", no_wrap=True)
        cycle_table.add_column("Description", style="dim")
        cycle_table.add_column("p (bar)", justify="right")
        cycle_table.add_column("T (K)", justify="right")
        cycle_table.add_column("h (kJ/kg)", justify="right")
        cycle_table.add_column("s (kJ/kg/K)", justify="right")
        cycle_table.add_column("x (-)", justify="right")

        point_descriptions = {
            1: "Evaporator outlet / compressor inlet",
            2: "Compressor outlet / condenser inlet",
            3: "Condenser outlet / turbine inlet",
            4: "Turbine outlet / evaporator inlet",
        }
        for i, description in point_descriptions.items():
            cycle_table.add_row(
                str(i),
                description,
                f"{cycle_data[f'p_ref_{i}'] / 1e5:.2f}", # Pa -> bar (assumed SI input)
                f"{cycle_data[f'T_ref_{i}'] :.2f}", # K -> °C (assumed SI input)
                f"{cycle_data[f'h_ref_{i}'] / 1e3:.2f}", # J/kg -> kJ/kg
                f"{cycle_data[f's_ref_{i}'] / 1e3:.4f}", # J/kg/K -> kJ/kg/K
                f"{cycle_data[f'Q_ref_{i}']:.3f}",
            )
        Console().print(cycle_table)

        # Operating conditions of the cycle: refrigerant mass flow and evaporation/condensation temperatures.
        operating_table = Table(title=f"Cycle Operating Conditions - {cycle_config['refrigerant']}", show_lines=False)
        operating_table.add_column("Symbol", style="cyan", no_wrap=True)
        operating_table.add_column("Value", justify="right")
        operating_table.add_column("Unit", justify="center")
        operating_table.add_column("Description", style="dim")
        # Evaporation/condensation temperatures can be NaN: no condensation in a transcritical cycle,
        # and neither in a fully supercritical cycle. Show "N/A" and add a note in the description.
        T_ev, T_cond = cycle_data['T_ev'], cycle_data['T_cond']
        fmt = lambda T: "N/A" if T==None else f"{T:.2f}"
        note = " (supercritical)" if T_ev==None and T_cond==None else " (transcritical)" if T_cond==None else ""
        operating_rows = [
            ("ṁ_ref",  f"{cycle_data['ṁ_ref']:.3f}",  "kg/s", "Mass flow rate of the refrigerant"),
            ("T_ev",   fmt(T_ev),                      "K",    "Evaporation temperature"),
            ("T_cond", fmt(T_cond),                    "K",    "Condensation temperature" + note),
        ]
        for symbol, value, unit, description in operating_rows:
            operating_table.add_row(symbol, value, unit, description)
        Console().print(operating_table)

        refrigerant = cycle_config["refrigerant"]
        results_file = save_results(
            f"results/heat_pump_thermodynamic_diagrams/{refrigerant}/data/"
            f"CHPC_{refrigerant}{method_suffix(general_config['calculation_method'])}.npz",
            cycle_config=cycle_config,
            general_config=general_config,
            cycle_data=cycle_data,
            perf=perf,
            ts_data=build_ts_data(cycle_data, cycle_config, general_config),
            ph_data=build_ph_data(cycle_data, cycle_config),
        )
        logger.info(f"Results saved to {results_file}")
        logger.info("Evaluation Completed")

    # Branch 2: run parameter sweep to study COP sensitivity to component efficiency.
    elif analysis_type == "COP_vs_eff":
        run_cop_vs_eff_investigation(cycle_config, general_config, logger)

if __name__ == "__main__":
    start = timeit.default_timer()
    main(config_file, perform_verification=False)
    logger.info(f"Evaluation time: {timeit.default_timer() - start:.2f} seconds")