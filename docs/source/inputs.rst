Inputs
======

An analysis is specified in an ``.ini`` config file. Examples for several refrigerants are given in ``config/``, and the easiest is to copy one of these and change the values. All inputs are in SI units, with temperatures in K. Since keys such as ``ṁ_h`` and ``η_turb`` contain special characters, the file has to be saved as UTF-8.

Inputs that are not used by the selected analysis type or calculation method must not be in the config file, otherwise an error is raised. This way the user cannot be under the impression that a value is taken into account when it is not, e.g. ``PR`` for ``full_optimization``.

[ANALYSIS TYPE]
---------------

.. list-table::
   :header-rows: 1
   :widths: 25 30 45

   * - Input
     - Values
     - Description
   * - ``analysis_type``
     - ``CHPC`` or ``COP_vs_eff``
     - single cycle, or cycles for a grid of efficiencies
   * - ``calculation_method``
     - ``full_optimization`` (default), ``fixed_PR`` or ``three_temp_fix``
     - cycle calculation method, see below

``full_optimization`` optimizes the pressure ratio, the temperature and entropy at the compressor inlet and the temperature at the condenser outlet. ``fixed_PR`` does the same at a given pressure ratio. ``three_temp_fix`` fixes four temperature differences and only optimizes the pressure ratio.

[ANALYSIS SPECIFICATIONS]
-------------------------

.. list-table::
   :header-rows: 1
   :widths: 25 20 55

   * - Input
     - Unit
     - Description
   * - ``refrigerant``
     -
     - working fluid, following the CoolProp naming convention, e.g. ``R1234ze(E)`` or ``CO2``
   * - ``T_h_in``, ``ṁ_h``, ``cp_h``
     - K, kg/s, J/kg/K
     - inlet temperature, mass flow rate and specific heat capacity of the heat sink
   * - ``T_c_in``, ``ṁ_c``, ``cp_c``
     - K, kg/s, J/kg/K
     - inlet temperature, mass flow rate and specific heat capacity of the heat source
   * - ``η_turb``, ``η_compr``
     - \-
     - isentropic efficiency of the turbine and compressor, ``CHPC`` only
   * - ``η_shaft``
     - \-
     - efficiency of the shaft connection between turbine and compressor, default 1
   * - ``ΔT_pp_min_evap``, ``ΔT_pp_min_cond``
     - K
     - minimum pinch-point temperature difference in the evaporator and condenser, not for ``three_temp_fix``
   * - ``Q_out_req``
     - W
     - required heat output, not for ``three_temp_fix``
   * - ``PR``
     - \-
     - compressor pressure ratio, ``fixed_PR`` only
   * - ``ΔT_pp_1``, ``ΔT_pp_3``, ``ΔT_pp_4``, ``ΔT_sh``
     - K
     - temperature difference at the evaporator outlet, condenser outlet and evaporator inlet, and the superheat, ``three_temp_fix`` only

[COP VS EFF SETTINGS]
---------------------

Only for ``analysis_type = COP_vs_eff``.

.. list-table::
   :header-rows: 1
   :widths: 30 25 45

   * - Input
     - Values
     - Description
   * - ``η_turb_bounds``, ``η_compr_bounds``
     - ``[min, max]``
     - lower and upper bound of the turbine and compressor efficiency
   * - ``n_η``
     - integer, e.g. 20
     - number of efficiencies per component, the bounds included. The COP is evaluated for n_η x n_η cycles
   * - ``existing_complete_sweep_action``
     - ``prompt`` (default), ``abort`` or ``recompute``
     - what to do when a complete sweep with the same grid already exists

[NUMERICS]
----------

.. list-table::
   :header-rows: 1
   :widths: 25 20 55

   * - Input
     - Values
     - Description
   * - ``n_pts``
     - integer, default 150
     - number of points along the isobars, used for the heat transfer integration and the diagrams
