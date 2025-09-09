#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate a complete LaTeX hand-out for Scenario 1 (Smartphone sub-assembly)
for MENGM0056 (2025/26), with parameters deterministically derived from a UUID.
The same UUID always yields the same parameters.

Usage:
  python generate_s1_handout.py --uuid <uuid-string> > mengm0056_s1_handout.tex
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
    demand_nominal_per_day: int
    demand_cv: float
    on_time_target: float

@dataclass
class StationParams:
    count: int
    cycle_time_s: float
    fpy: float = None
    defect_rate: float = None
    detect_prob: float = None
    false_fail: float = None
    rework_time_s: float = None
    rework_success: float = None

@dataclass
class ReliabilityParams:
    mtbf_min: float
    mttr_min: float
    arrival_jitter_cv: float

@dataclass
class CostsParams:
    scrap_cost_per_unit: float
    rework_labour_cost_per_hour: float

@dataclass
class ScenarioParams:
    uuid: str
    global_params: GlobalParams
    smt: StationParams
    camera_align: StationParams
    ict: StationParams
    final_assembly: StationParams
    ft: StationParams
    rework: StationParams
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

# ----------------------------
# Parameter generation
# ----------------------------
def generate(uuid_text: str) -> ScenarioParams:
    uuid_text = uuid_text.strip()
    rng = make_rng(uuid_text)

    # Global
    g = GlobalParams(
        shifts_per_day=2,
        shift_length_hours=7.5,
        demand_nominal_per_day=seeded_int(rng, 900, 1400),
        demand_cv=seeded_uniform(rng, 0.08, 0.22, 3),
        on_time_target=0.95
    )

    # Stations
    smt = StationParams(
        count=seeded_int(rng, 1, 3),
        cycle_time_s=seeded_uniform(rng, 24.0, 36.0, 1),
        fpy=bounded_prob(rng, 0.985, 0.998, 4)
    )
    camera = StationParams(
        count=seeded_int(rng, 1, 2),
        cycle_time_s=seeded_uniform(rng, 35.0, 55.0, 1),
        defect_rate=bounded_prob(rng, 0.015, 0.040, 4)
    )
    ict = StationParams(
        count=seeded_int(rng, 1, 2),
        cycle_time_s=seeded_uniform(rng, 70.0, 110.0, 1),
        detect_prob=bounded_prob(rng, 0.85, 0.98, 3)
    )
    fin = StationParams(
        count=seeded_int(rng, 1, 3),
        cycle_time_s=seeded_uniform(rng, 55.0, 85.0, 1),
        fpy=bounded_prob(rng, 0.97, 0.995, 4)
    )
    ft = StationParams(
        count=seeded_int(rng, 4, 8),  # slots
        cycle_time_s=seeded_uniform(rng, 90.0, 150.0, 1),
        false_fail=bounded_prob(rng, 0.002, 0.010, 4)
    )
    rework = StationParams(
        count=1,
        cycle_time_s=seeded_uniform(rng, 90.0, 180.0, 1),
        rework_success=bounded_prob(rng, 0.70, 0.92, 3)
    )

    # Reliability
    rel = {
        "SMT": ReliabilityParams(
            mtbf_min=seeded_uniform(rng, 240.0, 480.0, 1),
            mttr_min=seeded_uniform(rng, 8.0, 25.0, 1),
            arrival_jitter_cv=seeded_uniform(rng, 0.05, 0.12, 3)
        ),
        "Alignment": ReliabilityParams(
            mtbf_min=seeded_uniform(rng, 180.0, 360.0, 1),
            mttr_min=seeded_uniform(rng, 6.0, 18.0, 1),
            arrival_jitter_cv=seeded_uniform(rng, 0.05, 0.12, 3)
        ),
        "ICT": ReliabilityParams(
            mtbf_min=seeded_uniform(rng, 220.0, 420.0, 1),
            mttr_min=seeded_uniform(rng, 8.0, 20.0, 1),
            arrival_jitter_cv=seeded_uniform(rng, 0.05, 0.12, 3)
        ),
        "FinalAssembly": ReliabilityParams(
            mtbf_min=seeded_uniform(rng, 200.0, 400.0, 1),
            mttr_min=seeded_uniform(rng, 7.0, 20.0, 1),
            arrival_jitter_cv=seeded_uniform(rng, 0.05, 0.12, 3)
        ),
        "FT": ReliabilityParams(
            mtbf_min=seeded_uniform(rng, 260.0, 520.0, 1),
            mttr_min=seeded_uniform(rng, 10.0, 25.0, 1),
            arrival_jitter_cv=seeded_uniform(rng, 0.05, 0.12, 3)
        ),
    }

    costs = CostsParams(
        scrap_cost_per_unit=seeded_uniform(rng, 18.0, 35.0, 2),
        rework_labour_cost_per_hour=seeded_uniform(rng, 18.0, 28.0, 2)
    )

    # Checksum for verification (short hash of full JSON params excluding checksum)
    tmp = {
        "uuid": uuid_text,
        "global_params": asdict(g),
        "smt": asdict(smt),
        "camera_align": asdict(camera),
        "ict": asdict(ict),
        "final_assembly": asdict(fin),
        "ft": asdict(ft),
        "rework": asdict(rework),
        "reliability": {k: asdict(v) for k, v in rel.items()},
        "costs": asdict(costs),
    }
    blob = json.dumps(tmp, sort_keys=True).encode("utf-8")
    checksum = hashlib.sha256(blob).hexdigest()[:12]

    return ScenarioParams(
        uuid=uuid_text,
        global_params=g,
        smt=smt,
        camera_align=camera,
        ict=ict,
        final_assembly=fin,
        ft=ft,
        rework=rework,
        reliability=rel,
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
    # Begin document
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
    lines.append(r"\title{MENGM0056 - Product and Production Systems\\Scenario 1: Smartphone Sub-assembly Line}")
    lines.append(r"\author{Hand-out for Group Coursework (2025/26)}")
    lines.append(r"\date{}")
    lines.append(r"\begin{document}")
    lines.append(r"\maketitle")
    lines.append("")
    lines.append(r"\noindent \textbf{UUID seed:} " + tex_escape(p.uuid) + r" \quad \textbf{Checksum:} " + p.checksum)
    lines.append("")
    lines.append(r"\section*{Purpose}")
    lines.append(r"This scenario simulates decision-making in a mid-volume consumer-electronics sub-assembly factory. Your group receives a fixed baseline design (resources, cycle times, defect and failure characteristics, and demand). You will identify improvement opportunities, select appropriate KPIs, choose and apply techniques from the unit, and justify your proposed changes to management.")
    lines.append("")
    lines.append(r"\section*{Narrative}")
    lines.append(r"A contract manufacturer assembles a mid-range smartphone. Quality issues around camera alignment and intermittent congestion at functional test have been observed during promotional spikes. Demand is expected to grow. Capital expenditure is constrained; process and policy changes are preferred.")
    lines.append("")
    lines.append(r"\section*{Entities and flow (fixed structure)}")
    lines.append(r"PCB population (SMT) $\rightarrow$ Camera module build \& alignment $\rightarrow$ In-circuit test (ICT) $\rightarrow$ Final assembly \& seal $\rightarrow$ Functional test (FT) $\rightarrow$ Pack.")
    lines.append("")
    lines.append(r"\section*{Baseline parameters (seeded)}")
    # Global table
    lines.append(r"\subsection*{Global}")
    lines.append(r"\begin{tabular}{@{}ll@{}}")
    lines.append(r"\toprule")
    lines.append(rf"Shifts per day & {g.shifts_per_day} \\")
    lines.append(rf"Shift length & {g.shift_length_hours}~h \\")
    lines.append(rf"Demand (nominal) & {g.demand_nominal_per_day}~units/day \\")
    lines.append(rf"Demand CV & {g.demand_cv} \\")
    lines.append(rf"On-time target & {int(g.on_time_target*100)}\% \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append("")
    # Station table
    lines.append(r"\subsection*{Stations}")
    lines.append(r"\begin{tabular}{@{}lllll@{}}")
    lines.append(r"\toprule")
    lines.append(r"\textbf{Resource} & \textbf{Count} & \textbf{Time} & \textbf{Quality} & \textbf{Notes} \\")
    lines.append(r"\midrule")
    lines.append(rf"SMT lines & {p.smt.count} & {p.smt.cycle_time_s}~s/board & FPY {p.smt.fpy} & Parallel lines \\")
    lines.append(rf"Camera alignment cells & {p.camera_align.count} & {p.camera_align.cycle_time_s}~s/unit & Defect {p.camera_align.defect_rate} & Rework permitted \\")
    lines.append(rf"ICT bays & {p.ict.count} & {p.ict.cycle_time_s}~s/unit & Detect {p.ict.detect_prob} & Serial/parallel as per count \\")
    lines.append(rf"Final assembly cells & {p.final_assembly.count} & {p.final_assembly.cycle_time_s}~s/unit & FPY {p.final_assembly.fpy} & Manual with jigs \\")
    lines.append(rf"FT rack slots & {p.ft.count} & {p.ft.cycle_time_s}~s/unit & False fail {p.ft.false_fail} & Parallel slots; queueing \\")
    lines.append(rf"Rework station(s) & {p.rework.count} & {p.rework.cycle_time_s}~s/unit & Success {p.rework.rework_success} & From alignment/ICT \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append("")
    # Reliability
    lines.append(r"\subsection*{Reliability and logistics}")
    lines.append(r"\begin{tabular}{@{}llll@{}}")
    lines.append(r"\toprule Resource & MTBF (min) & MTTR (min) & Arrival jitter CV \\")
    lines.append(r"\midrule")
    for k, v in p.reliability.items():
        lines.append(rf"{k} & {v.mtbf_min} & {v.mttr_min} & {v.arrival_jitter_cv} \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append("")
    # Costs
    lines.append(r"\subsection*{Costs}")
    lines.append(r"\begin{tabular}{@{}ll@{}}")
    lines.append(r"\toprule")
    lines.append(rf"Scrap cost per unit & \pounds {p.costs.scrap_cost_per_unit} \\")
    lines.append(rf"Rework labour cost per hour & \pounds {p.costs.rework_labour_cost_per_hour} \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append("")
    # KPIs
    lines.append(r"\section*{Required KPIs}")
    lines.append(r"\begin{itemize}")
    lines.append(r"\item First-pass yield (FPY) by station and rolled throughput yield (RTY).")
    lines.append(r"\item Throughput (units/day), on-time delivery probability, and average lead time.")
    lines.append(r"\item Work-in-progress (WIP) before FT and maximum queue length at FT.")
    lines.append(r"\item Rework rate and rework hours/day; scrap cost per unit.")
    lines.append(r"\end{itemize}")
    # Techniques
    lines.append(r"\section*{Techniques to apply (choose appropriately)}")
    lines.append(r"\begin{itemize}")
    lines.append(r"\item \textbf{Modelling \& KPIs}: KPI definitions, RTY ladder, capacity calculations.")
    lines.append(r"\item \textbf{CAE}: Camera alignment jig/tolerance stack-up if you propose design changes affecting quality or time.")
    lines.append(r"\item \textbf{Mathematical programming}: Staffing and test-bay/slot scheduling; buffer sizing under constraints.")
    lines.append(r"\item \textbf{Uncertainty modelling}: Demand, defect, test time variability, breakdowns; Monte Carlo assessment of service level.")
    lines.append(r"\item \textbf{Simulation}: Discrete-event simulation of the line (bottlenecks and rework loop). Agent-based modelling is optional if human-cobot interactions are relevant.")
    lines.append(r"\item \textbf{Metaheuristic optimisation}: Parameter tuning for conflicting objectives (e.g., reduce defect rate without increasing cycle time beyond takt).")
    lines.append(r"\end{itemize}")
    # Levers
    lines.append(r"\section*{Improvement levers (examples, not exhaustive)}")
    lines.append(r"\begin{itemize}")
    lines.append(r"\item Realignment of staffing across ICT and FT; time-of-day pooling of testers.")
    lines.append(r"\item Buffer policy revision to avoid blocking before FT.")
    lines.append(r"\item Tolerance/jig updates informed by CAE to cut alignment defects.")
    lines.append(r"\item Preventive maintenance intervals to reduce micro-stoppages at FT.")
    lines.append(r"\item Rework routing policies (thresholds for scrap vs. rework).")
    lines.append(r"\end{itemize}")
    # Deliverables
    lines.append(r"\section*{Deliverables}")
    lines.append(r"\begin{enumerate}")
    lines.append(r"\item A report (max 20 sides of A4 including figures and references; appendices unmarked but admissible as evidence).")
    lines.append(r"\item The report should include an executive summary for senior management.")
    lines.append(r"\item Model files (e.g., simulation, optimisation) as appendices/evidence.")
    lines.append(r"\end{enumerate}")
    # Assessment
    lines.append(r"\section*{Assessment emphasis}")
    lines.append(r"Clarity of problem framing and KPI choice; correctness and transparency of models; appropriateness of technique selection; quality of experimental design; depth of analysis; and persuasiveness of recommendations given operational constraints.")
    # Reproducibility
    lines.append(r"\section*{Data ethics and reproducibility}")
    lines.append(r"Report your UUID seed and any random seeds used within tools to ensure reproducibility. State assumptions clearly.")
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
