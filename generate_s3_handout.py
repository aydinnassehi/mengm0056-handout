#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate a complete LaTeX hand-out for Scenario 3
(FMCG - Bottled Beverage, 500 ml) for MENGM0056 (2025/26).
Parameters are deterministically derived from a UUID string.
The same UUID always yields the same parameter set.

Usage:
  python generate_s3_handout.py --uuid <uuid-string> > mengm0056_s3_handout.tex
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
    base_daily_demand_cases: int          # cases/day (12 bottles per case)
    demand_cv_daily: float                # coefficient of variation (daily)
    sku_count: int                        # number of SKUs/flavours
    service_level_target: float           # on-time despatch target (e.g., 0.95)

@dataclass
class LineParams:
    count: int
    rate_bph: int                         # nominal bottles per hour per machine/line
    availability: float                   # effective availability factor (0-1)

@dataclass
class PackerParams:
    count: int
    case_rate_cph: int                    # cases per hour per machine
    availability: float

@dataclass
class ChangeoverParams:
    cip_min: int                          # clean-in-place duration (flavour)
    flavour_change_min: int               # additional operations for syrup change
    label_change_min: int                 # label roll/artwork change only
    min_batch_cases: int                  # minimum run size to justify change

@dataclass
class LogisticsParams:
    loading_bays: int
    despatch_start_hour: int              # e.g., 7
    despatch_end_hour: int                # e.g., 19
    truck_interarrival_mean_min: int      # mean minutes between truck arrivals (Poisson)
    truck_service_min: int                # minutes to load a truck
    cases_per_pallet: int
    pallets_per_truck: int

@dataclass
class ReliabilityParams:
    mtbf_min: float
    mttr_min: float

@dataclass
class CostsParams:
    holding_cost_per_pallet_day: float    # £/pallet/day
    changeover_cost_per_event: float      # £ per changeover (materials, QA, waste)
    lateness_penalty_per_truck: float     # £ penalty per late truck/order
    scrap_cost_per_case: float            # £/case for product scrapped in changeovers/CIP losses

@dataclass
class ScenarioParams:
    uuid: str
    global_params: GlobalParams
    blow_moulder: LineParams
    filler: LineParams
    labeller: LineParams
    packer: PackerParams
    palletiser: PackerParams
    changeover: ChangeoverParams
    logistics: LogisticsParams
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

def bounded_prob(rng: random.Random, lo: float, hi: float, decimals: int = 3) -> float:
    x = lo + (hi - lo) * rng.random()
    x = max(0.0, min(1.0, x))
    return round(x, decimals)

def choose(rng: random.Random, options):
    return options[seeded_int(rng, 0, len(options) - 1)]

# ----------------------------
# Parameter generation
# ----------------------------
def generate(uuid_text: str) -> ScenarioParams:
    uuid_text = uuid_text.strip()
    rng = make_rng(uuid_text)

    # Global assumptions
    global_params = GlobalParams(
        shifts_per_day=2,
        shift_length_hours=7.5,
        base_daily_demand_cases=seeded_int(rng, 1500, 2800),   # 12-bottle cases per day
        demand_cv_daily=seeded_uniform(rng, 0.12, 0.35, 3),    # weather-driven volatility
        sku_count=seeded_int(rng, 3, 6),
        service_level_target=0.95
    )

    # Line capacities (nominal) and availability (OEE-ish availability factor)
    blow_moulder = LineParams(
        count=1,
        rate_bph=seeded_int(rng, 22000, 26000),
        availability=seeded_uniform(rng, 0.82, 0.93, 3)
    )
    filler = LineParams(
        count=1,
        rate_bph=seeded_int(rng, 20000, 24000),
        availability=seeded_uniform(rng, 0.80, 0.92, 3)
    )
    labeller = LineParams(
        count=1,
        rate_bph=seeded_int(rng, 22000, 26000),
        availability=seeded_uniform(rng, 0.85, 0.95, 3)
    )
    packer = PackerParams(
        count=1,
        case_rate_cph=seeded_int(rng, 1500, 2100),             # cases/h
        availability=seeded_uniform(rng, 0.85, 0.95, 3)
    )
    palletiser = PackerParams(
        count=1,
        case_rate_cph=seeded_int(rng, 1400, 2000),
        availability=seeded_uniform(rng, 0.90, 0.98, 3)
    )

    # Changeovers and CIP
    changeover = ChangeoverParams(
        cip_min=seeded_int(rng, 35, 60),
        flavour_change_min=seeded_int(rng, 15, 35),
        label_change_min=seeded_int(rng, 7, 15),
        min_batch_cases=seeded_int(rng, 300, 800)
    )

    # Despatch and yard logistics
    logistics = LogisticsParams(
        loading_bays=seeded_int(rng, 1, 3),
        despatch_start_hour=7,
        despatch_end_hour=seeded_int(rng, 18, 20),
        truck_interarrival_mean_min=seeded_int(rng, 35, 75),
        truck_service_min=seeded_int(rng, 35, 60),
        cases_per_pallet=choose(rng, [72, 84, 96, 108]),
        pallets_per_truck=seeded_int(rng, 24, 30)
    )

    # Reliability (major resources)
    reliability = {
        "BlowMoulder": ReliabilityParams(
            mtbf_min=seeded_uniform(rng, 360.0, 720.0, 1),
            mttr_min=seeded_uniform(rng, 12.0, 30.0, 1)
        ),
        "Filler": ReliabilityParams(
            mtbf_min=seeded_uniform(rng, 300.0, 600.0, 1),
            mttr_min=seeded_uniform(rng, 15.0, 35.0, 1)
        ),
        "Labeller": ReliabilityParams(
            mtbf_min=seeded_uniform(rng, 420.0, 900.0, 1),
            mttr_min=seeded_uniform(rng, 8.0, 20.0, 1)
        ),
        "Packer": ReliabilityParams(
            mtbf_min=seeded_uniform(rng, 480.0, 960.0, 1),
            mttr_min=seeded_uniform(rng, 10.0, 25.0, 1)
        ),
        "Palletiser": ReliabilityParams(
            mtbf_min=seeded_uniform(rng, 600.0, 1200.0, 1),
            mttr_min=seeded_uniform(rng, 10.0, 20.0, 1)
        ),
    }

    # Costs
    costs = CostsParams(
        holding_cost_per_pallet_day=seeded_uniform(rng, 1.4, 2.6, 2),    # £/pallet/day
        changeover_cost_per_event=seeded_uniform(rng, 120.0, 280.0, 2),  # £/event incl. syrup/waste/QA
        lateness_penalty_per_truck=seeded_uniform(rng, 180.0, 400.0, 2), # £/late truck
        scrap_cost_per_case=seeded_uniform(rng, 1.0, 2.0, 2)             # £/case (product + packaging)
    )

    # Checksum for quick verification
    tmp = {
        "uuid": uuid_text,
        "global_params": asdict(global_params),
        "blow_moulder": asdict(blow_moulder),
        "filler": asdict(filler),
        "labeller": asdict(labeller),
        "packer": asdict(packer),
        "palletiser": asdict(palletiser),
        "changeover": asdict(changeover),
        "logistics": asdict(logistics),
        "reliability": {k: asdict(v) for k, v in reliability.items()},
        "costs": asdict(costs),
    }
    blob = json.dumps(tmp, sort_keys=True).encode("utf-8")
    checksum = hashlib.sha256(blob).hexdigest()[:12]

    return ScenarioParams(
        uuid=uuid_text,
        global_params=global_params,
        blow_moulder=blow_moulder,
        filler=filler,
        labeller=labeller,
        packer=packer,
        palletiser=palletiser,
        changeover=changeover,
        logistics=logistics,
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
    ch = p.changeover
    lg = p.logistics

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
    lines.append(r"\title{MENGM0056 - Product and Production Systems\\Scenario 3: FMCG - Bottled Beverage (500 ml)}")
    lines.append(r"\author{Hand-out for Group Coursework (2025/26)}")
    lines.append(r"\date{}")
    lines.append(r"\begin{document}")
    lines.append(r"\maketitle")
    lines.append("")
    lines.append(r"\noindent \textbf{UUID seed:} " + tex_escape(p.uuid) + r" \quad \textbf{Checksum:} " + p.checksum)
    lines.append("")
    lines.append(r"\section*{Purpose}")
    lines.append(r"This scenario considers a high-throughput beverage line with volatile demand and despatch congestion. Your task is to propose operational policies that stabilise service level and improve utilisation while controlling changeover losses and inventory.")
    lines.append("")
    lines.append(r"\section*{Narrative}")
    lines.append(r"A 500~ml carbonated soft drink is produced in PET bottles. The line comprises blow-moulding, filling, labelling, case-packing and palletising, with despatch to outbound trucks via limited loading bays. Demand varies with weather and promotions. CIP and changeovers consume valuable capacity. Capital spend is constrained; improvements should focus on scheduling, policies, and parameter changes.")
    lines.append("")
    lines.append(r"\section*{Entities and flow (fixed structure)}")
    lines.append(r"Preforms $\rightarrow$ Blow-mould $\rightarrow$ Fill $\rightarrow$ Cap $\rightarrow$ Label $\rightarrow$ Case-pack $\rightarrow$ Palletise $\rightarrow$ Despatch.")
    lines.append("")
    lines.append(r"\section*{Baseline parameters (seeded)}")

    # Global
    lines.append(r"\subsection*{Global}")
    lines.append(r"\begin{tabular}{@{}ll@{}}")
    lines.append(r"\toprule")
    lines.append(rf"Shifts per day & {g.shifts_per_day} \\")
    lines.append(rf"Shift length & {g.shift_length_hours}~h \\")
    lines.append(rf"Base daily demand & {g.base_daily_demand_cases}~cases/day (12 bottles/case) \\")
    lines.append(rf"Daily demand CV & {g.demand_cv_daily} \\")
    lines.append(rf"Number of SKUs & {g.sku_count} \\")
    lines.append(rf"On-time despatch target & {int(g.service_level_target*100)}\% \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append("")

    # Line capacities
    lines.append(r"\subsection*{Line capacities and availability}")
    lines.append(r"\begin{longtable}{@{}llll@{}}")
    lines.append(r"\toprule")
    lines.append(r"\textbf{Resource} & \textbf{Count} & \textbf{Nominal rate} & \textbf{Availability} \\")
    lines.append(r"\midrule")
    lines.append(rf"Blow-moulder & {p.blow_moulder.count} & {p.blow_moulder.rate_bph}~bph & {p.blow_moulder.availability} \\")
    lines.append(rf"Filler & {p.filler.count} & {p.filler.rate_bph}~bph & {p.filler.availability} \\")
    lines.append(rf"Labeller & {p.labeller.count} & {p.labeller.rate_bph}~bph & {p.labeller.availability} \\")
    lines.append(rf"Case-packer & {p.packer.count} & {p.packer.case_rate_cph}~cph & {p.packer.availability} \\")
    lines.append(rf"Palletiser & {p.palletiser.count} & {p.palletiser.case_rate_cph}~cph & {p.palletiser.availability} \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{longtable}")
    lines.append("")

    # Changeovers
    lines.append(r"\subsection*{Changeovers and CIP}")
    lines.append(r"\begin{tabular}{@{}ll@{}}")
    lines.append(r"\toprule")
    lines.append(rf"CIP duration (flavour) & {ch.cip_min}~min \\")
    lines.append(rf"Additional flavour change operations & {ch.flavour_change_min}~min \\")
    lines.append(rf"Label-only change duration & {ch.label_change_min}~min \\")
    lines.append(rf"Minimum batch size & {ch.min_batch_cases}~cases \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append("")

    # Logistics
    lines.append(r"\subsection*{Despatch and yard logistics}")
    lines.append(r"\begin{tabular}{@{}ll@{}}")
    lines.append(r"\toprule")
    lines.append(rf"Loading bays & {lg.loading_bays} \\")
    lines.append(rf"Despatch window & {lg.despatch_start_hour}:00\,--\,{lg.despatch_end_hour}:00 \\")
    lines.append(rf"Mean truck inter-arrival & {lg.truck_interarrival_mean_min}~min \\")
    lines.append(rf"Truck service time & {lg.truck_service_min}~min \\")
    lines.append(rf"Cases per pallet & {lg.cases_per_pallet} \\")
    lines.append(rf"Pallets per truck & {lg.pallets_per_truck} \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append("")

    # Reliability
    lines.append(r"\subsection*{Reliability (downtime parameters)}")
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
    lines.append(rf"Holding cost & \pounds {p.costs.holding_cost_per_pallet_day}~/pallet/day \\")
    lines.append(rf"Changeover cost (all-in) & \pounds {p.costs.changeover_cost_per_event}~/event \\")
    lines.append(rf"Lateness penalty & \pounds {p.costs.lateness_penalty_per_truck}~/late~truck \\")
    lines.append(rf"Scrap cost (changeover/CIP) & \pounds {p.costs.scrap_cost_per_case}~/case \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append("")

    # Required KPIs
    lines.append(r"\section*{Required KPIs}")
    lines.append(r"\begin{itemize}")
    lines.append(r"\item Line utilisation by unit (blow-moulder, filler, labeller, packer, palletiser).")
    lines.append(r"\item Changeover time and product loss per week; percentage of capacity lost to changeovers/CIP.")
    lines.append(r"\item Order lead time distribution and on-time despatch rate (service level).")
    lines.append(r"\item Loading-bay utilisation and maximum truck queue length; truck lateness count.")
    lines.append(r"\item Finished-goods days-of-cover and average pallets in buffer.")
    lines.append(r"\end{itemize}")

    # Techniques
    lines.append(r"\section*{Techniques to apply}")
    lines.append(r"\begin{itemize}")
    lines.append(r"\item \textbf{Modelling \& KPIs}: capacity model, bottleneck identification, changeover loss accounting.")
    lines.append(r"\item \textbf{Mathematical programming}: shift patterns, SKU sequencing and batch sizing subject to CIP and bay constraints.")
    lines.append(r"\item \textbf{Uncertainty modelling}: daily demand and truck arrivals; downtime distributions.")
    lines.append(r"\item \textbf{Simulation}: discrete-event model of the line and despatch yard; evaluate congestion and schedules.")
    lines.append(r"\item \textbf{Metaheuristic optimisation}: lot-sizing and sequence optimisation with changeover penalties and service-level targets.")
    lines.append(r"\end{itemize}")

    # Improvement levers
    lines.append(r"\section*{Improvement levers (examples)}")
    lines.append(r"\begin{itemize}")
    lines.append(r"\item SKU sequencing to group labels and reduce full CIP events; threshold policies for label-only changes.")
    lines.append(r"\item Time-of-day despatch smoothing: reserve windows for large orders; dynamic bay assignment.")
    lines.append(r"\item Buffer targets before palletiser and before despatch to prevent starvation/blocking.")
    lines.append(r"\item Preventive maintenance windows aligned with expected demand troughs.")
    lines.append(r"\end{itemize}")

    # Deliverables
    lines.append(r"\section*{Deliverables}")
    lines.append(r"\begin{enumerate}")
    lines.append(r"\item A report (max 20 sides of A4 including figures and references; appendices unmarked but admissible as evidence).")
    lines.append(r"\item A production and despatch plan for one representative week, showing SKU sequence, batch sizes, and expected service level.")
    lines.append(r"\item Model files (e.g., simulation, optimisation) as appendices/evidence.")
    lines.append(r"\end{enumerate}")

    # Assessment
    lines.append(r"\section*{Assessment emphasis}")
    lines.append(r"Clarity and correctness of the capacity and KPI model; appropriate choice and justification of techniques; quality of experimental design; robustness to demand variability; and persuasiveness of recommendations under operational constraints.")

    # Reproducibility
    lines.append(r"\section*{Data ethics and reproducibility}")
    lines.append(r"Report your UUID seed and any random seeds used within tools. Provide enough detail for independent regeneration of your parameter tables.")
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
