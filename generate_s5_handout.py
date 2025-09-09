#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate a complete LaTeX hand-out for Scenario 5 (EV battery module and pack assembly)
for MENGM0056 (2025/26), with parameters deterministically derived from a UUID.
The same UUID always yields the same parameters.

Usage:
  python generate_s5_handout.py --uuid <uuid-string> > mengm0056_s5_handout.tex
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
    target_packs_per_day: int
    oee_target: float
    demand_cv: float  # coefficient of variation in daily demand

@dataclass
class StationParams:
    count: int
    cycle_time_s: float  # per unit or per batch as stated in notes

@dataclass
class QualityParams:
    weld_defect_rate: float          # module weld splash/defect rate
    rework_success: float            # success probability of weld rework
    module_false_fail: float         # false fail at module EOL
    pack_false_fail: float           # false fail at pack EOL
    bms_misflash_rate: float         # firmware mis-flash probability
    leak_fail_rate: float            # pack leak test fail rate (true)
    cell_capacity_sigma_pc: float    # % sigma of cell capacity
    tim_thickness_sigma_mm: float    # mm sigma in thermal interface material

@dataclass
class ReliabilityParams:
    mtbf_min: float
    mttr_min: float

@dataclass
class CostsParams:
    scrap_cost_per_pack: float           # £/pack scrapped after assembly
    rework_labour_cost_per_hour: float   # £/h
    electricity_tariff_p_per_kwh: float  # pence/kWh blended
    nitrogen_cost_per_hour: float        # £/h for welding shield gas
    tim_cost_per_pack: float             # £/pack

@dataclass
class ScenarioParams:
    uuid: str
    global_params: GlobalParams
    cell_grading: StationParams
    module_assembly: StationParams
    laser_weld: StationParams
    module_eol: StationParams
    pack_assembly: StationParams
    bms_flash: StationParams
    pack_eol: StationParams
    leak_test: StationParams
    reliability: Dict[str, ReliabilityParams]
    quality: QualityParams
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

# ----------------------------
# Parameter generation
# ----------------------------
def generate(uuid_text: str) -> ScenarioParams:
    uuid_text = uuid_text.strip()
    rng = make_rng(uuid_text)

    # Global parameters
    global_params = GlobalParams(
        shifts_per_day=2,
        shift_length_hours=8.0,
        target_packs_per_day=seeded_int(rng, 90, 140),
        oee_target=seeded_uniform(rng, 0.65, 0.78, 2),
        demand_cv=seeded_uniform(rng, 0.08, 0.20, 3)
    )

    # Stations (counts and takt-like times)
    cell_grading = StationParams(
        count=seeded_int(rng, 4, 8),
        cycle_time_s=seeded_uniform(rng, 70.0, 110.0, 1)  # per test batch for cell bins
    )
    module_assembly = StationParams(
        count=seeded_int(rng, 1, 3),
        cycle_time_s=seeded_uniform(rng, 200.0, 300.0, 1)
    )
    laser_weld = StationParams(
        count=seeded_int(rng, 2, 4),  # weld heads/cells
        cycle_time_s=seeded_uniform(rng, 35.0, 55.0, 1)
    )
    module_eol = StationParams(
        count=seeded_int(rng, 1, 3),
        cycle_time_s=seeded_uniform(rng, 90.0, 150.0, 1)
    )
    pack_assembly = StationParams(
        count=1,
        cycle_time_s=seeded_uniform(rng, 720.0, 1200.0, 0)  # 12-20 min
    )
    bms_flash = StationParams(
        count=seeded_int(rng, 1, 3),
        cycle_time_s=seeded_uniform(rng, 240.0, 480.0, 0)   # 4-8 min
    )
    pack_eol = StationParams(
        count=seeded_int(rng, 2, 4),
        cycle_time_s=seeded_uniform(rng, 1500.0, 2400.0, 0)  # 25-40 min
    )
    leak_test = StationParams(
        count=seeded_int(rng, 1, 2),
        cycle_time_s=seeded_uniform(rng, 360.0, 720.0, 0)    # 6-12 min
    )

    # Quality and variation
    quality = QualityParams(
        weld_defect_rate=bounded_prob(rng, 0.008, 0.025, 4),
        rework_success=bounded_prob(rng, 0.70, 0.92, 3),
        module_false_fail=bounded_prob(rng, 0.003, 0.012, 4),
        pack_false_fail=bounded_prob(rng, 0.002, 0.010, 4),
        bms_misflash_rate=bounded_prob(rng, 0.001, 0.006, 4),
        leak_fail_rate=bounded_prob(rng, 0.003, 0.015, 4),
        cell_capacity_sigma_pc=seeded_uniform(rng, 2.0, 3.5, 2),
        tim_thickness_sigma_mm=seeded_uniform(rng, 0.05, 0.15, 3)
    )

    # Reliability by family (minutes)
    reliability = {
        "CellGrading": ReliabilityParams(
            mtbf_min=seeded_uniform(rng, 300.0, 600.0, 1),
            mttr_min=seeded_uniform(rng, 10.0, 30.0, 1)
        ),
        "ModuleAssembly": ReliabilityParams(
            mtbf_min=seeded_uniform(rng, 240.0, 480.0, 1),
            mttr_min=seeded_uniform(rng, 8.0, 20.0, 1)
        ),
        "LaserWeld": ReliabilityParams(
            mtbf_min=seeded_uniform(rng, 180.0, 360.0, 1),
            mttr_min=seeded_uniform(rng, 6.0, 18.0, 1)
        ),
        "ModuleEOL": ReliabilityParams(
            mtbf_min=seeded_uniform(rng, 260.0, 520.0, 1),
            mttr_min=seeded_uniform(rng, 8.0, 20.0, 1)
        ),
        "PackAssembly": ReliabilityParams(
            mtbf_min=seeded_uniform(rng, 360.0, 720.0, 1),
            mttr_min=seeded_uniform(rng, 12.0, 30.0, 1)
        ),
        "BMSFlash": ReliabilityParams(
            mtbf_min=seeded_uniform(rng, 300.0, 600.0, 1),
            mttr_min=seeded_uniform(rng, 8.0, 20.0, 1)
        ),
        "PackEOL": ReliabilityParams(
            mtbf_min=seeded_uniform(rng, 400.0, 800.0, 1),
            mttr_min=seeded_uniform(rng, 12.0, 28.0, 1)
        ),
        "LeakTest": ReliabilityParams(
            mtbf_min=seeded_uniform(rng, 420.0, 840.0, 1),
            mttr_min=seeded_uniform(rng, 10.0, 24.0, 1)
        ),
    }

    # Costs
    costs = CostsParams(
        scrap_cost_per_pack=seeded_uniform(rng, 380.0, 650.0, 2),
        rework_labour_cost_per_hour=seeded_uniform(rng, 20.0, 32.0, 2),
        electricity_tariff_p_per_kwh=seeded_uniform(rng, 22.0, 38.0, 1),
        nitrogen_cost_per_hour=seeded_uniform(rng, 2.5, 6.0, 2),
        tim_cost_per_pack=seeded_uniform(rng, 6.0, 12.0, 2)
    )

    # Checksum for verification
    tmp = {
        "uuid": uuid_text,
        "global_params": asdict(global_params),
        "cell_grading": asdict(cell_grading),
        "module_assembly": asdict(module_assembly),
        "laser_weld": asdict(laser_weld),
        "module_eol": asdict(module_eol),
        "pack_assembly": asdict(pack_assembly),
        "bms_flash": asdict(bms_flash),
        "pack_eol": asdict(pack_eol),
        "leak_test": asdict(leak_test),
        "reliability": {k: asdict(v) for k, v in reliability.items()},
        "quality": asdict(quality),
        "costs": asdict(costs),
    }
    blob = json.dumps(tmp, sort_keys=True).encode("utf-8")
    checksum = hashlib.sha256(blob).hexdigest()[:12]

    return ScenarioParams(
        uuid=uuid_text,
        global_params=global_params,
        cell_grading=cell_grading,
        module_assembly=module_assembly,
        laser_weld=laser_weld,
        module_eol=module_eol,
        pack_assembly=pack_assembly,
        bms_flash=bms_flash,
        pack_eol=pack_eol,
        leak_test=leak_test,
        reliability=reliability,
        quality=quality,
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
    q = p.quality

    lines = []
    lines.append(r"\documentclass[11pt,a4paper]{article}")
    lines.append(r"\usepackage[margin=2.5cm,landscape]{geometry}")
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
    lines.append(r"\title{MENGM0056 - Product and Production Systems\\Scenario 5: Electric Vehicles - Battery Module and Pack Assembly}")
    lines.append(r"\author{Hand-out for Group Coursework (2025/26)}")
    lines.append(r"\date{}")
    lines.append(r"\begin{document}")
    lines.append(r"\maketitle")
    lines.append("")
    lines.append(r"\noindent \textbf{UUID seed:} " + tex_escape(p.uuid) + r" \quad \textbf{Checksum:} " + p.checksum)
    lines.append("")
    lines.append(r"\section*{Purpose}")
    lines.append(r"This scenario covers a mid-volume EV battery module and pack assembly line. You receive seeded baseline parameters and must propose improvements that raise yield and throughput while maintaining safety and compliance, within typical operational constraints.")
    lines.append("")
    lines.append(r"\section*{Narrative}")
    lines.append(r"The factory assembles 60~kWh battery packs from twelve 5~kWh modules using 21700 cells. Weld rework and pack end-of-line capacity are jointly constraining output. Field incidents in hot weather highlight thermal gradients at fast charge. Capital expenditure is limited in the short term; process, policy, and design-for-manufacture changes are preferred.")
    lines.append("")
    lines.append(r"\section*{Entities and flow (fixed structure)}")
    lines.append(r"Incoming cell grading $\rightarrow$ Cell grouping $\rightarrow$ Module frame assembly $\rightarrow$ Laser tab-welding $\rightarrow$ Module end-of-line (EOL) electrical test $\rightarrow$ Pack assembly and busbar fit $\rightarrow$ BMS integration and firmware flash $\rightarrow$ Pack EOL (insulation resistance, HV leak, charge/discharge) $\rightarrow$ Leak test $\rightarrow$ Pack-out.")
    lines.append("")
    lines.append(r"\section*{Baseline parameters (seeded)}")

    # Global
    lines.append(r"\subsection*{Global}")
    lines.append(r"\begin{tabular}{@{}ll@{}}")
    lines.append(r"\toprule")
    lines.append(rf"Shifts per day & {g.shifts_per_day} \\")
    lines.append(rf"Shift length & {g.shift_length_hours}~h \\")
    lines.append(rf"Target packs/day & {g.target_packs_per_day} \\")
    lines.append(rf"OEE target & {int(g.oee_target*100)}\% \\")
    lines.append(rf"Demand CV & {g.demand_cv} \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append("")

    # Stations
    lines.append(r"\subsection*{Stations and timings}")
    lines.append(r"\begin{tabular}{@{}llll@{}}")
    lines.append(r"\toprule")
    lines.append(r"\textbf{Stage} & \textbf{Count} & \textbf{Cycle/Test time} & \textbf{Notes} \\")
    lines.append(r"\midrule")
    lines.append(rf"Cell grading testers & {p.cell_grading.count} & {p.cell_grading.cycle_time_s}~s/batch & Capacity sets bin inventory \\")
    lines.append(rf"Module assembly lines & {p.module_assembly.count} & {p.module_assembly.cycle_time_s}~s/module & Frame, placement, torque \\")
    lines.append(rf"Laser weld heads & {p.laser_weld.count} & {p.laser_weld.cycle_time_s}~s/module & Weld splash rework loop \\")
    lines.append(rf"Module EOL testers & {p.module_eol.count} & {p.module_eol.cycle_time_s}~s/module & Electrical characterisation \\")
    lines.append(rf"Pack assembly line & {p.pack_assembly.count} & {p.pack_assembly.cycle_time_s}~s/pack & Mechanical fit and busbars \\")
    lines.append(rf"BMS flash stations & {p.bms_flash.count} & {p.bms_flash.cycle_time_s}~s/pack & Firmware load and config \\")
    lines.append(rf"Pack EOL testers & {p.pack_eol.count} & {p.pack_eol.cycle_time_s}~s/pack & Insulation, charge/discharge \\")
    lines.append(rf"Leak testers & {p.leak_test.count} & {p.leak_test.cycle_time_s}~s/pack & Enclosure integrity \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append("")

    # Quality and variation
    lines.append(r"\subsection*{Quality, variation, and reliability}")
    lines.append(r"\begin{tabular}{@{}ll@{}}")
    lines.append(r"\toprule")
    lines.append(rf"Weld defect rate & {q.weld_defect_rate} \\")
    lines.append(rf"Weld rework success & {q.rework_success} \\")
    lines.append(rf"Module EOL false fail & {q.module_false_fail} \\")
    lines.append(rf"Pack EOL false fail & {q.pack_false_fail} \\")
    lines.append(rf"BMS mis-flash rate & {q.bms_misflash_rate} \\")
    lines.append(rf"Leak test fail (true) & {q.leak_fail_rate} \\")
    lines.append(rf"Cell capacity $\sigma$ & {q.cell_capacity_sigma_pc}\% of nominal \\")
    lines.append(rf"TIM thickness $\sigma$ & {q.tim_thickness_sigma_mm}~mm \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append("")
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
    lines.append(rf"Scrap cost (per pack) & \pounds {p.costs.scrap_cost_per_pack} \\")
    lines.append(rf"Rework labour & \pounds {p.costs.rework_labour_cost_per_hour}~/h \\")
    lines.append(rf"Electricity tariff & {p.costs.electricity_tariff_p_per_kwh}~p/kWh \\")
    lines.append(rf"Nitrogen shield gas & \pounds {p.costs.nitrogen_cost_per_hour}~/h \\")
    lines.append(rf"TIM material & \pounds {p.costs.tim_cost_per_pack}~/pack \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append("")

    # KPIs
    lines.append(r"\section*{Required KPIs}")
    lines.append(r"\begin{itemize}")
    lines.append(r"\item Pack first-pass yield (FPY); module FPY; rolled throughput yield (RTY).")
    lines.append(r"\item Throughput (packs/day), EOL tester utilisation, and on-time delivery probability.")
    lines.append(r"\item Rework rate and rework hours/day; scrap cost per pack.")
    lines.append(r"\item Mean cell-to-cell capacity delta in module; maximum module temperature rise under 2C charge (if analysed).")
    lines.append(r"\item Queue length before pack EOL; WIP across welding and EOL.")
    lines.append(r"\end{itemize}")

    # Techniques
    lines.append(r"\section*{Techniques to apply (choose appropriately)}")
    lines.append(r"\begin{itemize}")
    lines.append(r"\item \textbf{Modelling \& KPIs}: Genealogy/traceability KPI design; RTY ladder; capacity calculations.")
    lines.append(r"\item \textbf{CAE}: Thermal model of module and cooling interface to evaluate temperature gradients; busbar stiffness if vibration is considered.")
    lines.append(r"\item \textbf{Mathematical programming}: Cell grouping to minimise module variance; EOL tester scheduling and buffer sizing.")
    lines.append(r"\item \textbf{Uncertainty modelling}: Cell capacity distribution; weld defect probabilities; mis-flash and false-fail rates; Monte Carlo service-level estimation.")
    lines.append(r"\item \textbf{Simulation}: Discrete-event simulation of the whole line, including welding rework loop and EOL blocking; optional agent-based detail for operator–cobot interaction.")
    lines.append(r"\item \textbf{Metaheuristic optimisation}: Weld parameter set search (pulse energy, speed, focus) under FPY and cycle constraints; TIM thickness optimisation with thermal penalty.")
    lines.append(r"\end{itemize}")

    # Levers
    lines.append(r"\section*{Improvement levers (examples, not exhaustive)}")
    lines.append(r"\begin{itemize}")
    lines.append(r"\item Introduce graded cell-binning rules to reduce intra-module variance and quantify warranty risk impact.")
    lines.append(r"\item Reallocate module vs. pack EOL testers by time-of-day to relieve peak blocking; adjust buffers accordingly.")
    lines.append(r"\item Tune weld parameters to cut splash while respecting takt; compare search vs. DOE.")
    lines.append(r"\item Reduce TIM thickness variance via supplier spec and quantify $\Delta T$ reduction at fast charge.")
    lines.append(r"\item Evaluate preventive maintenance on weld heads vs. adding a small rework bench; compare cost per additional good pack.")
    lines.append(r"\end{itemize}")

    # Deliverables
    lines.append(r"\section*{Deliverables}")
    lines.append(r"\begin{enumerate}")
    lines.append(r"\item A report (max 20 sides of A4 including figures and references; appendices unmarked but admissible as evidence).")
    lines.append(r"\item The report should contain an executive summary for senior management.")
    lines.append(r"\item Model files (e.g., simulation, optimisation, CAE) as appendices/evidence.")
    lines.append(r"\end{enumerate}")

    # Assessment
    lines.append(r"\section*{Assessment emphasis}")
    lines.append(r"Clarity of problem framing and KPI choice; correctness and transparency of models; appropriateness of technique selection; quality of experimental design; depth of analysis on yield, EOL capacity, and thermal performance; and persuasiveness of recommendations under operational constraints.")

    # Reproducibility
    lines.append(r"\section*{Data ethics and reproducibility}")
    lines.append(r"Report your UUID seed and any random seeds used. Include enough detail to allow independent regeneration of your parameter tables.")
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
