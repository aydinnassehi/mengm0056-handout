#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate a complete LaTeX hand-out for Scenario 2 (Automotive components - aluminium gearbox casings)
for MENGM0056 (2025/26), with parameters deterministically derived from a UUID.
The same UUID always yields the same parameters.

Usage:
  python generate_s2_handout.py --uuid <uuid-string> > mengm0056_s2_handout.tex
"""

import argparse
import hashlib
import json
import random
from dataclasses import dataclass, asdict
from typing import Dict

# ----------------------------
# Data models
# ----------------------------
@dataclass
class GlobalParams:
    shifts_per_day: int
    shift_length_hours: float
    weekly_output_target: int          # good parts per week
    demand_cv: float                   # coefficient of variation for weekly orders
    sustainability_focus: str          # textual flag to steer student emphasis

@dataclass
class StationParams:
    count: int
    cycle_time_s: float = None         # or process time representative per part
    batch_size: int = None             # for batch processes
    batch_time_min: float = None       # for ovens etc.
    scrap_rate: float = None           # station-level scrap probability
    detect_prob: float = None          # NDT detection probability
    rework_time_s: float = None        # per part if applicable

@dataclass
class EnergyParams:
    kwh_per_part_casting: float
    kwh_per_part_machining: float
    kwh_per_part_heat_treat: float
    peak_tariff_p_per_kwh: float
    offpeak_tariff_p_per_kwh: float
    peak_start_hour: int
    peak_end_hour: int

@dataclass
class MaterialParams:
    net_mass_kg: float
    gating_runners_kg: float
    recoverable_yield: float           # fraction of gating recoverable as scrap
    alloy_price_per_kg: float
    scrap_recovery_per_kg: float

@dataclass
class ReliabilityParams:
    mtbf_min: float
    mttr_min: float

@dataclass
class CostsParams:
    ndt_cost_per_part: float
    coolant_cost_per_part: float
    labour_cost_per_hour: float
    rework_labour_cost_per_hour: float
    environmental_cost_per_kwh_p: float  # pence per kWh equivalent carbon cost

@dataclass
class ScenarioParams:
    uuid: str
    global_params: GlobalParams
    casting: StationParams
    ndt: StationParams
    heat_treat: StationParams
    cnc: StationParams
    washing: StationParams
    cmm: StationParams
    energy: EnergyParams
    material: MaterialParams
    reliability: Dict[str, ReliabilityParams]
    costs: CostsParams
    checksum: str

# ----------------------------
# Deterministic RNG utilities
# ----------------------------
def make_rng(seed_text: str) -> random.Random:
    digest = hashlib.sha256(seed_text.encode("utf-8")).hexdigest()
    seed = int(digest[:8], 16)  # stable 32-bit seed
    return random.Random(seed)

def seeded_uniform(rng: random.Random, lo: float, hi: float, decimals: int = 2) -> float:
    x = lo + (hi - lo) * rng.random()
    return round(x, decimals)

def seeded_int(rng: random.Random, lo: int, hi: int) -> int:
    return rng.randint(lo, hi)

def bounded_prob(rng: random.Random, lo: float, hi: float, decimals: int = 4) -> float:
    x = lo + (hi - lo) * rng.random()
    x = max(0.0, min(1.0, x))
    return round(x, decimals)

def choose(rng: random.Random, options):
    return options[seeded_int(rng, 0, len(options)-1)]

# ----------------------------
# Parameter generation
# ----------------------------
def generate(uuid_text: str) -> ScenarioParams:
    uuid_text = uuid_text.strip()
    rng = make_rng(uuid_text)

    # Global parameters
    global_params = GlobalParams(
        shifts_per_day=seeded_int(rng, 2, 3),
        shift_length_hours=7.5,
        weekly_output_target=seeded_int(rng, 4200, 5600),  # good parts per week
        demand_cv=seeded_uniform(rng, 0.06, 0.18, 3),
        sustainability_focus=choose(rng, [
            "energy", "scrap", "both"
        ])
    )

    # Stations and process characteristics
    # Casting cells
    casting = StationParams(
        count=seeded_int(rng, 2, 4),
        cycle_time_s=seeded_uniform(rng, 170.0, 240.0, 1),  # 2.8-4.0 min
        scrap_rate=bounded_prob(rng, 0.03, 0.09, 4)          # station scrap at casting
    )

    # X-ray NDT
    ndt = StationParams(
        count=seeded_int(rng, 1, 2),
        cycle_time_s=seeded_uniform(rng, 70.0, 120.0, 1),
        detect_prob=bounded_prob(rng, 0.92, 0.99, 3),
        rework_time_s=seeded_uniform(rng, 240.0, 480.0, 0)   # triage and repair path
    )

    # Heat treatment oven
    heat_treat = StationParams(
        count=seeded_int(rng, 1, 2),
        batch_size=seeded_int(rng, 160, 240),                # parts per batch
        batch_time_min=seeded_uniform(rng, 320.0, 420.0, 1)  # 5.3-7.0 h including ramps/soak
    )

    # CNC machining centres
    cnc = StationParams(
        count=seeded_int(rng, 5, 8),
        cycle_time_s=seeded_uniform(rng, 380.0, 520.0, 0),   # per part combined rough+finish
        scrap_rate=bounded_prob(rng, 0.004, 0.012, 4)
    )

    # Washing
    washing = StationParams(
        count=seeded_int(rng, 1, 2),
        cycle_time_s=seeded_uniform(rng, 60.0, 120.0, 0)
    )

    # CMM inspection
    cmm = StationParams(
        count=seeded_int(rng, 1, 2),
        cycle_time_s=seeded_uniform(rng, 540.0, 780.0, 0),   # 9-13 min
        scrap_rate=bounded_prob(rng, 0.0, 0.002, 4)          # late discovery risk
    )

    # Energy parameters
    energy = EnergyParams(
        kwh_per_part_casting=seeded_uniform(rng, 2.8, 4.2, 2),
        kwh_per_part_machining=seeded_uniform(rng, 0.9, 1.6, 2),
        kwh_per_part_heat_treat=seeded_uniform(rng, 1.6, 2.8, 2),
        peak_tariff_p_per_kwh=seeded_uniform(rng, 32.0, 52.0, 1),
        offpeak_tariff_p_per_kwh=seeded_uniform(rng, 18.0, 28.0, 1),
        peak_start_hour=choose(rng, [15, 16, 17]),
        peak_end_hour=choose(rng, [18, 19, 20])
    )

    # Material parameters
    material = MaterialParams(
        net_mass_kg=seeded_uniform(rng, 5.2, 6.8, 2),
        gating_runners_kg=seeded_uniform(rng, 0.8, 1.6, 2),
        recoverable_yield=seeded_uniform(rng, 0.65, 0.85, 2),
        alloy_price_per_kg=seeded_uniform(rng, 2.6, 3.8, 2),     # £/kg
        scrap_recovery_per_kg=seeded_uniform(rng, 0.9, 1.5, 2)   # £/kg
    )

    # Reliability by family
    reliability = {
        "Furnace": ReliabilityParams(
            mtbf_min=seeded_uniform(rng, 360.0, 720.0, 1),
            mttr_min=seeded_uniform(rng, 20.0, 60.0, 1)
        ),
        "CastingCell": ReliabilityParams(
            mtbf_min=seeded_uniform(rng, 240.0, 540.0, 1),
            mttr_min=seeded_uniform(rng, 8.0, 25.0, 1)
        ),
        "Oven": ReliabilityParams(
            mtbf_min=seeded_uniform(rng, 480.0, 960.0, 1),
            mttr_min=seeded_uniform(rng, 20.0, 45.0, 1)
        ),
        "CNC": ReliabilityParams(
            mtbf_min=seeded_uniform(rng, 300.0, 700.0, 1),
            mttr_min=seeded_uniform(rng, 10.0, 30.0, 1)
        ),
        "CMM": ReliabilityParams(
            mtbf_min=seeded_uniform(rng, 600.0, 1200.0, 1),
            mttr_min=seeded_uniform(rng, 15.0, 30.0, 1)
        ),
    }

    # Costs
    costs = CostsParams(
        ndt_cost_per_part=seeded_uniform(rng, 0.12, 0.35, 2),     # £ per part imaged
        coolant_cost_per_part=seeded_uniform(rng, 0.03, 0.09, 2), # £ per part
        labour_cost_per_hour=seeded_uniform(rng, 16.0, 24.0, 2),
        rework_labour_cost_per_hour=seeded_uniform(rng, 18.0, 28.0, 2),
        environmental_cost_per_kwh_p=seeded_uniform(rng, 1.2, 3.6, 1)  # pence/kWh as carbon proxy
    )

    # Checksum for verification
    tmp = {
        "uuid": uuid_text,
        "global_params": asdict(global_params),
        "casting": asdict(casting),
        "ndt": asdict(ndt),
        "heat_treat": asdict(heat_treat),
        "cnc": asdict(cnc),
        "washing": asdict(washing),
        "cmm": asdict(cmm),
        "energy": asdict(energy),
        "material": asdict(material),
        "reliability": {k: asdict(v) for k, v in reliability.items()},
        "costs": asdict(costs),
    }
    blob = json.dumps(tmp, sort_keys=True).encode("utf-8")
    checksum = hashlib.sha256(blob).hexdigest()[:12]

    return ScenarioParams(
        uuid=uuid_text,
        global_params=global_params,
        casting=casting,
        ndt=ndt,
        heat_treat=heat_treat,
        cnc=cnc,
        washing=washing,
        cmm=cmm,
        energy=energy,
        material=material,
        reliability=reliability,
        costs=costs,
        checksum=checksum
    )

# ----------------------------
# LaTeX rendering
# ----------------------------
def tex_escape(s: str) -> str:
    return (s.replace("&", "\\&")
             .replace("%", "\\%")
             .replace("$", "\\$")
             .replace("#", "\\#")
             .replace("_", "\\_")
             .replace("{", "\\{")
             .replace("}", "\\}")
             .replace("~", "\\textasciitilde{}")
             .replace("^", "\\textasciicircum{}")
             .replace("\\", "\\textbackslash{}"))

def render_latex(p: ScenarioParams) -> str:
    g = p.global_params
    e = p.energy
    m = p.material

    lines = []
    lines.append(r"\documentclass[11pt,a4paper]{article}")
    lines.append(r"\usepackage[margin=2.5cm]{geometry}")
    lines.append(r"\usepackage{booktabs}")
    lines.append(r"\usepackage{siunitx}")
    lines.append(r"\usepackage{enumitem}")
    lines.append(r"\usepackage[hidelinks]{hyperref}")
    lines.append(r"\usepackage{caption}")
    lines.append(r"\usepackage{longtable}")
    lines.append(r"\sisetup{detect-all=true}")
    lines.append("")
    lines.append(r"\setlist[itemize]{nosep}")
    lines.append(r"\setlist[enumerate]{nosep}")
    lines.append("")
    lines.append(r"\title{MENGM0056 - Product and Production Systems\\Scenario 2: Automotive Components - Aluminium Gearbox Casings}")
    lines.append(r"\author{Hand-out for Group Coursework (2025/26)}")
    lines.append(r"\date{}")
    lines.append(r"\begin{document}")
    lines.append(r"\maketitle")
    lines.append("")
    lines.append(r"\noindent \textbf{UUID seed:} " + tex_escape(p.uuid) + r" \quad \textbf{Checksum:} " + p.checksum)
    lines.append("")
    lines.append(r"\section*{Purpose}")
    lines.append(r"This scenario simulates a cast-and-machine workflow for aluminium gearbox casings. Your group receives seeded baseline parameters and must propose improvements that reduce cost and environmental impact while maintaining the weekly output target and quality.")
    lines.append("")
    lines.append(r"\section*{Narrative}")
    lines.append(r"Aluminium and energy prices have risen, and new environmental performance reporting requires reductions in both scrap and energy per good part. Production capacity must be maintained to satisfy weekly orders. Capital expenditure is constrained in the short term, so parameter, policy, and scheduling changes are preferred.")
    lines.append("")
    lines.append(r"\section*{Entities and flow (fixed structure)}")
    lines.append(r"Gravity die casting $\rightarrow$ X-ray NDT $\rightarrow$ Heat treatment $\rightarrow$ CNC rough/finish $\rightarrow$ Washing $\rightarrow$ Coordinate-measuring machine (CMM) $\rightarrow$ Pack.")
    lines.append("")
    lines.append(r"\section*{Baseline parameters (seeded)}")

    # Global
    lines.append(r"\subsection*{Global}")
    lines.append(r"\begin{tabular}{@{}ll@{}}")
    lines.append(r"\toprule")
    lines.append(rf"Shifts per day & {g.shifts_per_day} \\")
    lines.append(rf"Shift length & {g.shift_length_hours}~h \\")
    lines.append(rf"Weekly output target & {g.weekly_output_target}~good~parts/week \\")
    lines.append(rf"Weekly demand CV & {g.demand_cv} \\")
    lines.append(rf"Sustainability emphasis & {tex_escape(g.sustainability_focus)} \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append("")

    # Stations
    lines.append(r"\subsection*{Stations and process timings}")
    lines.append(r"\begin{longtable}{@{}lllll@{}}")
    lines.append(r"\toprule")
    lines.append(r"\textbf{Stage} & \textbf{Count} & \textbf{Time} & \textbf{Quality} & \textbf{Notes} \\")
    lines.append(r"\midrule")
    lines.append(rf"Casting cells & {p.casting.count} & {p.casting.cycle_time_s}~s/part & Scrap {p.casting.scrap_rate} & Gravity die casting \\")
    lines.append(rf"X-ray NDT & {p.ndt.count} & {p.ndt.cycle_time_s}~s/part & Detect {p.ndt.detect_prob} & Rework path {p.ndt.rework_time_s}~s if repairable \\")
    if p.heat_treat.batch_size and p.heat_treat.batch_time_min:
        lines.append(rf"Heat treatment oven & {p.heat_treat.count} & {p.heat_treat.batch_time_min}~min/batch & - & Batch size {p.heat_treat.batch_size} parts \\")
    lines.append(rf"CNC machining centres & {p.cnc.count} & {p.cnc.cycle_time_s}~s/part & Scrap {p.cnc.scrap_rate} & Combined rough and finish \\")
    lines.append(rf"Washing & {p.washing.count} & {p.washing.cycle_time_s}~s/part & - & Deburr and wash \\")
    lines.append(rf"CMM inspection & {p.cmm.count} & {p.cmm.cycle_time_s}~s/part & Scrap {p.cmm.scrap_rate} & Late discovery risk \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{longtable}")
    lines.append("")

    # Materials and energy
    lines.append(r"\subsection*{Materials and energy}")
    lines.append(r"\begin{tabular}{@{}ll@{}}")
    lines.append(r"\toprule")
    lines.append(rf"Net casting mass & {m.net_mass_kg}~kg \\")
    lines.append(rf"Gating and runners & {m.gating_runners_kg}~kg \\")
    lines.append(rf"Recoverable yield from gating & {int(m.recoverable_yield*100)}\% \\")
    lines.append(rf"Alloy price & \pounds {m.alloy_price_per_kg}~/kg \\")
    lines.append(rf"Scrap recovery value & \pounds {m.scrap_recovery_per_kg}~/kg \\")
    lines.append(r"\midrule")
    lines.append(rf"Casting energy & {e.kwh_per_part_casting}~kWh/part \\")
    lines.append(rf"Machining energy & {e.kwh_per_part_machining}~kWh/part \\")
    lines.append(rf"Heat treatment energy & {e.kwh_per_part_heat_treat}~kWh/part \\")
    lines.append(rf"Tariff off-peak & {e.offpeak_tariff_p_per_kwh}~p/kWh \\")
    lines.append(rf"Tariff peak & {e.peak_tariff_p_per_kwh}~p/kWh \\")
    lines.append(rf"Peak window & {e.peak_start_hour}:00\,--\,{e.peak_end_hour}:00 \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append("")

    # Reliability
    lines.append(r"\subsection*{Reliability}")
    lines.append(r"\begin{tabular}{@{}lll@{}}")
    lines.append(r"\toprule Resource & MTBF (min) & MTTR (min) \\")
    lines.append(r"\midrule")
    for k, v in p.reliability.items():
        lines.append(rf"{k} & {v.mtbf_min} & {v.mttr_min} \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append("")

    # Costs
    lines.append(r"\subsection*{Costs}")
    lines.append(r"\begin{tabular}{@{}ll@{}}")
    lines.append(r"\toprule")
    lines.append(rf"X-ray NDT imaging cost & \pounds {p.costs.ndt_cost_per_part}~/part \\")
    lines.append(rf"Coolant and consumables & \pounds {p.costs.coolant_cost_per_part}~/part \\")
    lines.append(rf"Labour cost & \pounds {p.costs.labour_cost_per_hour}~/h \\")
    lines.append(rf"Rework labour cost & \pounds {p.costs.rework_labour_cost_per_hour}~/h \\")
    lines.append(rf"Environmental cost proxy & {p.costs.environmental_cost_per_kwh_p}~p/kWh \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append("")

    # KPIs
    lines.append(r"\section*{Required KPIs}")
    lines.append(r"\begin{itemize}")
    lines.append(r"\item Scrap percentage by stage and rolled throughput yield (RTY).")
    lines.append(r"\item Energy consumption per good part, and energy cost per good part.")
    lines.append(r"\item Material utilisation: net mass divided by total poured, and alloy cost per good part.")
    lines.append(r"\item Weekly throughput and on-time completion against the weekly output target.")
    lines.append(r"\item CMM queue time and heat treatment oven utilisation.")
    lines.append(r"\end{itemize}")

    # Techniques
    lines.append(r"\section*{Techniques to apply}")
    lines.append(r"\begin{itemize}")
    lines.append(r"\item \textbf{Modelling \& KPIs}: RTY ladder; energy and material balance per good part.")
    lines.append(r"\item \textbf{CAE}: Casting gating and riser changes; distortion risk and machining allowance sensitivity.")
    lines.append(r"\item \textbf{Mathematical programming}: Oven batch sizing and start-time scheduling to avoid peak tariffs; CNC assignment and shift planning.")
    lines.append(r"\item \textbf{Uncertainty modelling}: Demand variability; breakdown distributions; defect modes and NDT detection uncertainty.")
    lines.append(r"\item \textbf{Metaheuristic optimisation}: Multi-parameter process window search for casting temperatures, die temperatures, and shot speeds under yield and cycle constraints.")
    lines.append(r"\item \textbf{Simulation}: Discrete-event simulation for bottlenecks at CMM and ovens; evaluate queueing and batch policies.")
    lines.append(r"\end{itemize}")

    # Levers
    lines.append(r"\section*{Improvement levers (examples, not exhaustive)}")
    lines.append(r"\begin{itemize}")
    lines.append(r"\item Shift oven starts to minimise time in peak tariff windows while protecting weekly output.")
    lines.append(r"\item Modify gating and riser design to cut porosity and reduce machining allowances.")
    lines.append(r"\item Balance CNC routing based on cycle spread; consider dynamic assignment to reduce queues.")
    lines.append(r"\item Introduce NDT triage rules for repairability to prevent non-valuable rework.")
    lines.append(r"\item Implement scrap segregation to maximise recovery value.")
    lines.append(r"\end{itemize}")

    # Deliverables
    lines.append(r"\section*{Deliverables}")
    lines.append(r"\begin{enumerate}")
    lines.append(r"\item A report (max 20 sides of A4 including figures and references; appendices unmarked but admissible as evidence).")
    lines.append(r"\item A weekly production plan demonstrating compliance with the output target and tariff policy.")
    lines.append(r"\item Model files (e.g., simulation, optimisation, CAE) as appendices or evidence.")
    lines.append(r"\end{enumerate}")

    # Assessment
    lines.append(r"\section*{Assessment emphasis}")
    lines.append(r"Sound KPI selection and modelling; correctness and transparency of calculations; appropriate choice of techniques; quality of experimental design; depth of analysis on scrap and energy; and clear, defensible recommendations that meet operational constraints.")

    # Reproducibility
    lines.append(r"\section*{Data ethics and reproducibility}")
    lines.append(r"Report your UUID seed and any random seeds used within tools. Include enough detail to allow independent regeneration of your parameter tables.")
    lines.append("")
    lines.append(r"\end{document}")
    return "\n".join(lines)

# ----------------------------
# Main
# ----------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uuid", required=True, help="UUID string (any version).")
    args = ap.parse_args()

    params = generate(args.uuid)
    tex = render_latex(params)
    print(tex)

if __name__ == "__main__":
    main()
