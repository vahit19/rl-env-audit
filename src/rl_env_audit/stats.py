"""Exact binomial bounds for the certificate."""

from __future__ import annotations

import math


def upper_bound(failures: int, trials: int, alpha: float = 0.05) -> float:
    """One-sided Clopper-Pearson upper bound on the failure rate at confidence 1 - alpha.

    With zero failures this is 1 - alpha**(1/n): 59 clean trials bound the rate below 5%.
    """
    if trials <= 0:
        return 1.0
    if failures >= trials:
        return 1.0
    if failures == 0:
        return 1.0 - alpha ** (1.0 / trials)
    lo, hi = failures / trials, 1.0
    for _ in range(100):  # bisection on P(Bin(n, p) <= k) = alpha
        mid = (lo + hi) / 2
        if binom_cdf(failures, trials, mid) > alpha:
            lo = mid
        else:
            hi = mid
    return hi


def binom_cdf(k: int, n: int, p: float) -> float:
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k + 1))


def trials_needed(rate: float, alpha: float = 0.05) -> int:
    """Clean trials needed so that zero failures certifies a failure rate below `rate`."""
    return math.ceil(math.log(alpha) / math.log(1.0 - rate))
