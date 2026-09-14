"""Planning arithmetic only. No GPU access, downloads, or model experiments.

Run: python estimate_resources.py --output RESOURCE_ESTIMATES.json
The configuration is a budget assumption that Phase 0 must verify on the host.
The paired sample-size calculation is an approximation, not a power guarantee.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
from statistics import NormalDist


def paired_n_approx(delta: float, discordance: float, alpha: float, power: float) -> int:
    if not (0 < delta < 1 and delta <= discordance <= 1):
        raise ValueError("Require 0 < delta <= discordance <= 1.")
    if not (0 < alpha < 1 and 0.5 < power < 1):
        raise ValueError("Require 0 < alpha < 1 and 0.5 < power < 1.")
    normal = NormalDist()
    return math.ceil((normal.inv_cdf(1-alpha/2) + normal.inv_cdf(power))**2 * discordance / delta**2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=None)
    args = parser.parse_args()
    params, layers, hidden, qheads, kvheads, head_dim = 2516756480, 42, 2048, 16, 2, 128
    cases = {
        'BF16_weights_only': params*2,
        'residual_cache_10k_inputs_3_anchors': 10000*layers*3*hidden*2,
        'residual_cache_10k_inputs_all_2048_tokens': 10000*layers*2048*hidden*2,
        'KV_cache_batch4_sequence2048': 2*layers*4*2048*kvheads*head_dim*2,
        'KV_cache_batch4_sequence4096': 2*layers*4*4096*kvheads*head_dim*2,
    }
    result = {
        'status': 'computed_budget_estimates_not_empirical_measurements',
        'config_on_host_verified': False,
        'assumed_config': dict(parameters=params,layers=layers,hidden=hidden,query_heads=qheads,kv_heads=kvheads,head_dim=head_dim),
        'memory': {name: dict(bytes=value,GB=value/10**9,GiB=value/2**30,TiB=value/2**40) for name,value in cases.items()},
        'power_approximation': {'delta':.05,'discordance':.2,'power':.8,
            'n_alpha_05':paired_n_approx(.05,.2,.05,.8),
            'n_alpha_05_div3':paired_n_approx(.05,.2,.05/3,.8),
            'limitations':'Independent paired binary units; no clustering, invalid output adjustment or empirical power simulation.'},
        'gpu_hours_budget_caps_not_predictions':{'P0':5,'P1':10,'P2':25,'P3':40,'P4':20,'P5':20,'total':120},
    }
    encoded=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if args.output is not None:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(encoded)
    else:
        print(encoded,end='')

if __name__ == '__main__':
    main()
