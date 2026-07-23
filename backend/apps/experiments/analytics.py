from .models import Experiment, ExperimentEvent
from django.db.models import Count, Q
import math


def _regularized_gamma_lower(s, x, iterations=200):
    """
    Regularized lower incomplete gamma function P(s, x), used to compute
    the chi-squared CDF without requiring scipy. Series expansion,
    accurate enough for typical experiment sample sizes.
    """
    if x < 0 or s <= 0:
        return 0.0
    if x == 0:
        return 0.0

    # Series expansion (valid well for x < s + 1; degrees of freedom here
    # are small integers so this holds for realistic experiment data)
    term = 1.0 / s
    total = term
    for n in range(1, iterations):
        term *= x / (s + n)
        total += term
        if abs(term) < abs(total) * 1e-12:
            break
    return total * math.exp(-x + s * math.log(x) - math.lgamma(s))


def _chi_squared_p_value(chi_sq_stat, degrees_of_freedom):
    """
    P-value for a chi-squared statistic: 1 - CDF(chi_sq_stat; df).
    CDF(x; k) = P(k/2, x/2) using the regularized lower incomplete gamma function.
    """
    if degrees_of_freedom <= 0:
        return 1.0
    cdf = _regularized_gamma_lower(degrees_of_freedom / 2.0, chi_sq_stat / 2.0)
    return max(0.0, min(1.0, 1.0 - cdf))


def calculate_significance(experiment_id):
    """
    Calculate chi-squared significance for an experiment across all its
    variants. Returns per-variant views/conversions/rate plus an overall
    chi_squared statistic, p_value, and significant flag (p < 0.05).
    """
    experiment = Experiment.objects.get(id=experiment_id)

    results = {}
    for variant in experiment.variants:
        total = ExperimentEvent.objects.filter(
            experiment=experiment, variant=variant, event_type="view"
        ).count()

        conversions = ExperimentEvent.objects.filter(
            experiment=experiment, variant=variant, event_type="conversion"
        ).count()

        results[variant] = {
            "views": total,
            "conversions": conversions,
            "rate": conversions / total if total > 0 else 0,
        }

    # Chi-squared test of independence: is conversion rate independent of variant?
    variants = list(results.keys())
    chi_squared_stat = None
    p_value = None
    significant = False

    if len(variants) >= 2:
        total_views = sum(results[v]["views"] for v in variants)
        total_conversions = sum(results[v]["conversions"] for v in variants)

        if total_views > 0 and 0 < total_conversions < total_views:
            overall_rate = total_conversions / total_views
            chi_sq = 0.0
            valid = True

            for v in variants:
                n = results[v]["views"]
                observed_conv = results[v]["conversions"]
                observed_non_conv = n - observed_conv

                expected_conv = n * overall_rate
                expected_non_conv = n * (1 - overall_rate)

                if expected_conv <= 0 or expected_non_conv <= 0:
                    valid = False
                    break

                chi_sq += ((observed_conv - expected_conv) ** 2) / expected_conv
                chi_sq += (
                    (observed_non_conv - expected_non_conv) ** 2
                ) / expected_non_conv

            if valid:
                degrees_of_freedom = len(variants) - 1
                chi_squared_stat = chi_sq
                p_value = _chi_squared_p_value(chi_sq, degrees_of_freedom)
                significant = p_value < 0.05

    return {
        "variants": results,
        "chi_squared": chi_squared_stat,
        "p_value": p_value,
        "significant": significant,
    }
