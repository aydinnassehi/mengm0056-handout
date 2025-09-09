#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate a complete LaTeX hand-out for Scenario 4 (Medical devices - disposable syringes)
for MENGM0056 (2025/26), with parameters deterministically derived from a UUID.
The same UUID always yields the same parameters.

Usage:
  python generate_s4_handout.py --uuid <uuid-string> > mengm0056_s4_handout.tex
"""

import argparse
import hashlib
import json
import random
from dataclasses import dataclass, asdict
from typing import Dict, Optional

# ----------------------------
# Data models
# ----------------------------
@dataclass
class GlobalParams:
    shifts_per_day: int
    shift_length_hours: float
    demand_nominal_per_day: int
    demand_spike_pct: int           # surge percentage for public health campaign
    on_time_target: float

@dataclass
class StationParams:
    count: int
    cycle_time_s: Optional[float] = None    # per-unit time (s); None for batch-only stages
    fpy: Optional[float] = None
    detect_prob: Optional[float] = None
    false_fail: Optional[float] = None
    scrap_rate: Optional[float] = None
    rework_time_s: Optional[float] = None
    rework_success: Optional[float] = None
    # Batch attributes (for sterilisation etc.)
    batch_size_units: Optional[int] = None
    batch_time_min: Optional[float] = None

@dataclass
class BufferPolicy:
    pre_eo_max_hours: float
    post_eo_quarantine_hours: float

@dataclass
class ReliabilityParams:
    mtbf_min: float
    mttr_min: float

@dataclass
class CostsParams:
    scrap_cost_per_unit: float
    pack_material_cost_per_unit: float
    sterilisation_cost_per_batch: float
    labour_cost_per_hour: float
    rework_labour_cost_per_hour: float
    quality_escapes_cost_per_million: float

@dataclass
class ScenarioParams:
    uuid: str
    global_params: GlobalParams
    moulding: StationParams
    assembly: StationParams
    visual_inspection: StationParams
    eo: StationParams
    packing: StationParams
    buffer_policy: BufferPolicy
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

    # Global demand and policy
    g = GlobalParams(
        shifts_per_day=seeded_int(rng, 2, 3),
        shift_length_hours=7.5,
        demand_nominal_per_day=seeded_int(rng, 80000, 150000),
        demand_spike_pct=seeded_int(rng, 25, 60),  # surge magnitude
        on_time_target=0.95
    )

    # Injection moulding (barrels + plungers), per-piece time is average over multi-cavity
    moulding = StationParams(
        count=seeded_int(rng, 3, 6),
        cycle_time_s=seeded_uniform(rng, 16.0, 22.0, 1),
        fpy=bounded_prob(rng, 0.985, 0.998, 4),
        scrap_rate=bounded_prob(rng, 0.004, 0.012, 4)
    )

    # Automated assembly (plunger insertion + needle shield)
    assembly = StationParams(
        count=seeded_int(rng, 1, 3),
        cycle_time_s=seeded_uniform(rng, 0.50, 0.80, 2),
        fpy=bounded_prob(rng, 0.980, 0.996, 4),
        rework_time_s=seeded_uniform(rng, 30.0, 90.0, 0),
        rework_success=bounded_prob(rng, 0.75, 0.92, 3)
    )

    # 100% visual inspection (automated camera)
    visual = StationParams(
        count=seeded_int(rng, 1, 2),
        cycle_time_s=seeded_uniform(rng, 0.30, 0.60, 2),
        detect_prob=bounded_prob(rng, 0.92, 0.99, 3),
        false_fail=bounded_prob(rng, 0.002, 0.010, 4)
    )

    # EO sterilisation - batch process with quarantine
    eo = StationParams(
        count=seeded_int(rng, 1, 2),
        batch_size_units=seeded_int(rng, 40000, 70000),
        batch_time_min=seeded_uniform(rng, 210.0, 320.0, 1)  # 3.5 - 5.3 h including aeration start
    )

    # Packing - operators with per-operator rate
    pack = StationParams(
        count=seeded_int(rng, 8, 16),  # operators
        cycle_time_s=None,             # derived via rate in notes
        fpy=bounded_prob(rng, 0.995, 0.999, 4)
    )

    # Buffer policy around EO
    policy = BufferPolicy(
        pre_eo_max_hours=seeded_uniform(rng, 4.0, 10.0, 1),
        post_eo_quarantine_hours=seeded_uniform(rng, 8.0, 24.0, 1)
    )

    # Reliability by family (minutes)
    reliability = {
        "Moulding": ReliabilityParams(
            mtbf_min=seeded_uniform(rng, 360.0, 720.0, 1),
            mttr_min=seeded_uniform(rng, 10.0, 30.0, 1)
        ),
        "Assembly": ReliabilityParams(
            mtbf_min=seeded_uniform(rng, 300.0, 600.0, 1),
            mttr_min=seeded_uniform(rng, 8.0, 20.0, 1)
        ),
        "Inspection": ReliabilityParams(
            mtbf_min=seeded_uniform(rng, 480.0, 900.0, 1),
            mttr_min=seeded_uniform(rng, 6.0, 15.0, 1)
        ),
        "EO": ReliabilityParams(
            mtbf_min=seeded_uniform(rng, 600.0, 1200.0, 1),
            mttr_min=seeded_uniform(rng, 20.0, 60.0, 1)
        ),
        "Packing": ReliabilityParams(
            mtbf_min=seeded_uniform(rng, 420.0, 840.0, 1),
            mttr_min=seeded_uniform(rng, 8.0, 18.0, 1)
        ),
    }

    # Cost model (GBP)
    costs = CostsParams(
        scrap_cost_per_unit=seeded_uniform(rng, 0.06, 0.15, 2),
        pack_material_cost_per_unit=seeded_uniform(rng, 0.03, 0.08, 2),
        sterilisation_cost_per_batch=seeded_uniform(rng, 120.0, 260.0, 2),
        labour_cost_per_hour=seeded_uniform(rng, 15.0, 23.0, 2),
        rework_labour_cost_per_hour=seeded_uniform(rng, 16.0, 26.0, 2),
        quality_escapes_cost_per_million=seeded_uniform(rng, 4000.0, 12000.0, 0)
    )

    # Checksum for verification
    tmp = {
        "uuid": uuid_text,
        "global_params": asdict(g),
        "moulding": asdict(moulding),
        "assembly": asdict(assembly),
        "visual_inspection": asdict(visual),
        "eo": asdict(eo),
        "packing": asdict(pack),
        "buffer_policy": asdict(policy),
        "reliability": {k: asdict(v) for k, v in reliability.items()},
        "costs": asdict(costs),
    }
    blob = json.dumps(tmp, sort_keys=True).encode("utf-8")
    checksum = hashlib.sha256(blob).hexdigest()[:12]

    return ScenarioParams(
        uuid=uuid_text,
        global_params=g,
        moulding=moulding,
        assembly=assembly,
        visual_inspection=visual,
        eo=eo,
        packing=pack,
        buffer_policy=policy,
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
    lines.append(r"\title{MENGM0056 - Product and Production Systems\\Scenario 4: Medical Devices - Disposable Syringes}")
    lines.append(r"\author{Hand-out for Group Coursework (2025/26)}")
    lines.append(r"\date{}")
    lines.append(r"\begin{document}")
    lines.append(r"\maketitle")
    lines.append("")
    lines.append(r"\noindent \textbf{UUID seed:} " + tex_escape(p.uuid) + r" \quad \textbf{Checksum:} " + p.checksum)
    lines.append("")
    lines.append(r"\section*{Purpose}")
    lines.append(r"This scenario addresses a regulated, high-volume medical-device operation. Your group receives seeded parameters for a syringe line and must deliver an improvement plan that achieves surge demand while maintaining compliance and quality, with limited scope for capital expenditure.")
    lines.append("")
    lines.append(r"\section*{Narrative}")
    lines.append(r"A public health campaign has created a time-bound surge in orders for sterile syringes. The EO sterilisation chamber and downstream quarantine are known bottlenecks. Management prefers process and policy changes over new equipment in the short term. Regulatory compliance must be preserved.")
    lines.append("")
    lines.append(r"\section*{Entities and flow (fixed structure)}")
    lines.append(r"Injection moulding (barrel, plunger) $\rightarrow$ Automated assembly with needle shield $\rightarrow$ 100\% visual inspection $\rightarrow$ EO sterilisation (batch) $\rightarrow$ Quarantine (post-EO) $\rightarrow$ Clean-room packing $\rightarrow$ Release testing.")
    lines.append("")
    lines.append(r"\section*{Baseline parameters (seeded)}")
    # Global
    lines.append(r"\subsection*{Global}")
    lines.append(r"\begin{tabular}{@{}ll@{}}")
    lines.append(r"\toprule")
    lines.append(rf"Shifts per day & {g.shifts_per_day} \\")
    lines.append(rf"Shift length & {g.shift_length_hours}~h \\")
    lines.append(rf"Demand (nominal) & {g.demand_nominal_per_day}~units/day \\")
    lines.append(rf"Surge magnitude & {g.demand_spike_pct}\% above nominal \\")
    lines.append(rf"On-time target & {int(g.on_time_target*100)}\% \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append("")
    # Stations table
    lines.append(r"\subsection*{Stations and process timings}")
    lines.append(r"\small")
    lines.append(r"\begin{longtable}{@{}lllll@{}}")
    lines.append(r"\toprule")
    lines.append(r"\textbf{Stage} & \textbf{Count} & \textbf{Time} & \textbf{Quality} & \textbf{Notes} \\")
    lines.append(r"\midrule")
    lines.append(rf"Injection moulding & {p.moulding.count} & {p.moulding.cycle_time_s}~s/part & FPY {p.moulding.fpy} \newline (scrap {p.moulding.scrap_rate}) & Multi-cavity average \\")
    lines.append(rf"Automated assembly & {p.assembly.count} & {p.assembly.cycle_time_s}~s/part & FPY {p.assembly.fpy} & Rework {p.assembly.rework_time_s}~s (success {p.assembly.rework_success}) \\")
    lines.append(rf"Visual inspection & {p.visual_inspection.count} & {p.visual_inspection.cycle_time_s}~s/part & Detect {p.visual_inspection.detect_prob} (false fail {p.visual_inspection.false_fail}) & 100\% coverage \\")
    if p.eo.batch_size_units and p.eo.batch_time_min:
        lines.append(rf"EO sterilisation (batch) & {p.eo.count} & {p.eo.batch_time_min}~min/batch & - & Batch size {p.eo.batch_size_units} units \\")
    lines.append(rf"Clean-room packing & {p.packing.count} & - & FPY {p.packing.fpy} & Operators; per-operator rate see policy \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{longtable}")
    lines.append("")
    # Policy
    lines.append(r"\subsection*{Buffer policy and quarantine}")
    lines.append(r"\begin{tabular}{@{}ll@{}}")
    lines.append(r"\toprule")
    lines.append(rf"Max pre-EO buffer & {p.buffer_policy.pre_eo_max_hours}~h \\")
    lines.append(rf"Post-EO quarantine & {p.buffer_policy.post_eo_quarantine_hours}~h \\")
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
    lines.append(rf"Scrap cost & \pounds {p.costs.scrap_cost_per_unit}~/unit \\")
    lines.append(rf"Pack material cost & \pounds {p.costs.pack_material_cost_per_unit}~/unit \\")
    lines.append(rf"EO sterilisation cost & \pounds {p.costs.sterilisation_cost_per_batch}~/batch \\")
    lines.append(rf"Labour cost & \pounds {p.costs.labour_cost_per_hour}~/h \\")
    lines.append(rf"Rework labour cost & \pounds {p.costs.rework_labour_cost_per_hour}~/h \\")
    lines.append(rf"Quality escapes proxy & \pounds {int(p.costs.quality_escapes_cost_per_million)}~/million units \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append("")
    # KPIs
    lines.append(r"\section*{Required KPIs}")
    lines.append(r"\begin{itemize}")
    lines.append(r"\item End-to-end lead time and on-time delivery probability under surge conditions.")
    lines.append(r"\item EO chamber utilisation, number of batches/day, and queue time into EO.")
    lines.append(r"\item Quarantine inventory and release rate; packing throughput and operator utilisation.")
    lines.append(r"\item FPY by stage and rolled throughput yield (RTY); rework rate and rework hours/day.")
    lines.append(r"\item Scrap cost per unit and expected cost of quality escapes.")
    lines.append(r"\end{itemize}")
    # Techniques
    lines.append(r"\section*{Techniques to apply}")
    lines.append(r"\begin{itemize}")
    lines.append(r"\item \textbf{Modelling \& KPIs}: RTY ladder; EO batch sizing logic; capacity calculations.")
    lines.append(r"\item \textbf{Mathematical programming}: EO batch sequencing; shift and packing-station staffing to achieve surge output.")
    lines.append(r"\item \textbf{Uncertainty modelling}: Breakdown and false-fail distributions; demand surge profiles; contamination risk as rare events.")
    lines.append(r"\item \textbf{Simulation}: Discrete-event simulation focused on EO bottleneck, quarantine, and packing; test push vs. pull policies.")
    lines.append(r"\item \textbf{Metaheuristic optimisation}: Multi-objective tuning of batch sizes, start times, and buffer limits for on-time delivery vs. WIP.")
    lines.append(r"\item \textbf{CAE (optional)}: If proposing design or fixture changes affecting assembly time or defect modes.")
    lines.append(r"\end{itemize}")
    # Levers
    lines.append(r"\section*{Improvement levers (examples, not exhaustive)}")
    lines.append(r"\begin{itemize}")
    lines.append(r"\item EO campaign scheduling (stagger starts, night runs) within pre-defined safety windows.")
    lines.append(r"\item Rework triage rules after visual inspection to minimise non-value-adding loops.")
    lines.append(r"\item Temporary reallocation of operators to packing during surge hours; dynamic takt alignment.")
    lines.append(r"\item Adjust max pre-EO buffer and quarantine durations where compliant, evaluating risk and service impact.")
    lines.append(r"\end{itemize}")
    # Deliverables
    lines.append(r"\section*{Deliverables}")
    lines.append(r"\begin{enumerate}")
    lines.append(r"\item A report (max 20 sides of A4 including figures and references; appendices unmarked but admissible as evidence).")
    lines.append(r"\item The report should contain a surge-response plan demonstrating capacity to meet demand spike while maintaining compliance.")
    lines.append(r"\item Model files (simulation, optimisation) as appendices or evidence.")
    lines.append(r"\end{enumerate}")
    # Assessment
    lines.append(r"\section*{Assessment emphasis}")
    lines.append(r"Appropriate KPI selection; correctness and transparency of models; evidence-based policy choices; robustness under uncertainty; and clear recommendations that respect regulatory constraints.")
    # Reproducibility
    lines.append(r"\section*{Data ethics and reproducibility}")
    lines.append(r"Report your UUID seed and any random seeds used within tools. Provide sufficient detail for independent regeneration of your parameter tables.")
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
