# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportOperatorIssue=false, reportReturnType=false, reportGeneralTypeIssues=false
# (Django model/field types are unresolved without stubs; these rules are noise here.)
# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportOperatorIssue=false, reportReturnType=false, reportGeneralTypeIssues=false
# (Django model/field types are unresolved without stubs; these rules are noise here.)
"""
Adaptive challenge difficulty with Glicko-2 ratings.

A learner and a challenge each have a rating. Every submission is one game
between them, and the learner's rating then picks the scaffolding, the hint
auto reveal delay and the bonus criteria for the next challenge.

The rating maths follows Mark Glickman, "Example of the Glicko-2 system":
http://www.glicko.net/glicko/glicko2.pdf
"""

from __future__ import annotations

import difflib
import math
from dataclasses import dataclass
from typing import Optional, Sequence

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import UserProfile
from apps.progress.models import AdaptiveAttempt, ChallengeRating

SCALE = 173.7178
DEFAULT_RATING = 1500.0
DEFAULT_DEVIATION = 350.0
DEFAULT_VOLATILITY = 0.06
TAU = 0.5  # how fast volatility may change
CONVERGENCE = 1e-6

# Score of a solved challenge, 1.0 is a clean and quick solve.
HINT_PENALTY = 0.75
SLOW_PENALTY = 0.25  # reached at twice the target time
MIN_SOLVED_SCORE = 0.1
# Failed submissions of one challenge that change ratings. Later ones are
# still counted but are not rated.
MAX_RATED_FAILURES = 3

GUIDED, STANDARD, EXPERT = "guided", "standard", "expert"
STANDARD_FROM = 1400.0
EXPERT_FROM = 1650.0

CHALLENGE_START_RATING = {
    "beginner": 1300.0,
    "intermediate": 1500.0,
    "advanced": 1700.0,
}
TARGET_SECONDS = {"beginner": 300, "intermediate": 600, "advanced": 900}

LEVEL_SETTINGS = {
    # hint delay (None: never shown on its own), share of the target time,
    # hints and failures still allowed for the bonus
    GUIDED: {"hint_after": 60, "time_share": 1.0, "hints": 1, "failures": 2},
    STANDARD: {"hint_after": 240, "time_share": 0.75, "hints": 0, "failures": 1},
    EXPERT: {"hint_after": None, "time_share": 0.5, "hints": 0, "failures": 0},
}


@dataclass(frozen=True)
class Rating:
    rating: float = DEFAULT_RATING
    deviation: float = DEFAULT_DEVIATION
    volatility: float = DEFAULT_VOLATILITY


# -- Glicko-2 ---------------------------------------------------------------


def _g(phi: float) -> float:
    return 1.0 / math.sqrt(1.0 + 3.0 * phi**2 / math.pi**2)


def _expected(mu: float, opponent_mu: float, opponent_phi: float) -> float:
    return 1.0 / (1.0 + math.exp(-_g(opponent_phi) * (mu - opponent_mu)))


def _new_volatility(
    phi: float, sigma: float, v: float, delta: float, tau: float
) -> float:
    """Step 5 of the paper, solved with the Illinois algorithm."""
    a = math.log(sigma**2)

    def f(x: float) -> float:
        ex = math.exp(x)
        top = ex * (delta**2 - phi**2 - v - ex)
        return top / (2.0 * (phi**2 + v + ex) ** 2) - (x - a) / tau**2

    low = a
    if delta**2 > phi**2 + v:
        high = math.log(delta**2 - phi**2 - v)
    else:
        k = 1
        while f(a - k * tau) < 0:
            k += 1
        high = a - k * tau

    f_low, f_high = f(low), f(high)
    while abs(high - low) > CONVERGENCE:
        mid = low + (low - high) * f_low / (f_high - f_low)
        f_mid = f(mid)
        if f_mid * f_high <= 0:
            low, f_low = high, f_high
        else:
            f_low /= 2.0
        high, f_high = mid, f_mid
    return math.exp(low / 2.0)


def glicko2_update(
    player: Rating, games: Sequence[tuple[Rating, float]], tau: float = TAU
) -> Rating:
    """
    Rate one period. ``games`` holds (opponent, score) pairs, score from 0 to 1.

    With no games only the deviation grows.
    """
    mu = (player.rating - DEFAULT_RATING) / SCALE
    phi = player.deviation / SCALE
    sigma = player.volatility

    if not games:
        grown = math.sqrt(phi**2 + sigma**2) * SCALE
        return Rating(player.rating, min(grown, DEFAULT_DEVIATION), sigma)

    inverse_v = 0.0
    improvement = 0.0
    for opponent, score in games:
        opponent_mu = (opponent.rating - DEFAULT_RATING) / SCALE
        opponent_phi = opponent.deviation / SCALE
        expected = _expected(mu, opponent_mu, opponent_phi)
        weight = _g(opponent_phi)
        inverse_v += weight**2 * expected * (1.0 - expected)
        improvement += weight * (score - expected)

    v = 1.0 / inverse_v
    new_sigma = _new_volatility(phi, sigma, v, v * improvement, tau)
    phi_star = math.sqrt(phi**2 + new_sigma**2)
    new_phi = 1.0 / math.sqrt(1.0 / phi_star**2 + 1.0 / v)
    new_mu = mu + new_phi**2 * improvement

    return Rating(
        rating=new_mu * SCALE + DEFAULT_RATING,
        deviation=min(new_phi * SCALE, DEFAULT_DEVIATION),
        volatility=new_sigma,
    )


# -- challenge parameters -----------------------------------------------------


def performance_score(
    *,
    solved: bool,
    hints_used: int = 0,
    time_spent: Optional[float] = None,
    target_seconds: int = TARGET_SECONDS["intermediate"],
) -> float:
    """Turn one submission into a Glicko score. Unknown time costs nothing."""
    if not solved:
        return 0.0
    score = 1.0 - HINT_PENALTY * hints_used
    if time_spent is not None and time_spent > target_seconds:
        overtime = min((time_spent - target_seconds) / target_seconds, 1.0)
        score -= SLOW_PENALTY * overtime
    return max(MIN_SOLVED_SCORE, min(score, 1.0))


def scaffolding_level(skill_rating: float) -> str:
    if skill_rating < STANDARD_FROM:
        return GUIDED
    if skill_rating < EXPERT_FROM:
        return STANDARD
    return EXPERT


def challenge_parameters(level: str, difficulty: str) -> dict:
    settings = LEVEL_SETTINGS[level]
    target = TARGET_SECONDS.get(difficulty, TARGET_SECONDS["intermediate"])
    return {
        "level": level,
        "hint_auto_reveal_after_seconds": settings["hint_after"],
        "bonus_criteria": {
            "max_seconds": int(target * settings["time_share"]),
            "max_hints": settings["hints"],
            "max_failed_attempts": settings["failures"],
        },
    }


def conflict_markers(current: str, incoming: str) -> str:
    """The file as Git would leave it: shared lines merged, differences marked."""
    ours, theirs = current.splitlines(), incoming.splitlines()
    merged: list[str] = []
    matcher = difflib.SequenceMatcher(a=ours, b=theirs, autojunk=False)
    for tag, a1, a2, b1, b2 in matcher.get_opcodes():
        if tag == "equal":
            merged += ours[a1:a2]
        else:
            merged += ["<<<<<<< HEAD", *ours[a1:a2], "======="]
            merged += [*theirs[b1:b2], ">>>>>>> incoming"]
    return "\n".join(merged)


def starter_code(level: str, current: str, incoming: str) -> str:
    """Starting editor content: marked up, plain HEAD version, or empty."""
    if level == GUIDED:
        return conflict_markers(current, incoming)
    if level == STANDARD:
        return current
    return ""


# -- stored state -------------------------------------------------------------


def profile_for(user) -> UserProfile:
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def is_enabled(user) -> bool:
    return UserProfile.objects.filter(
        user=user, adaptive_difficulty_enabled=True
    ).exists()


def set_enabled(user, enabled: bool) -> UserProfile:
    profile = profile_for(user)
    # update() so a stale profile object cannot overwrite the ratings
    UserProfile.objects.filter(pk=profile.pk).update(
        adaptive_difficulty_enabled=enabled
    )
    profile.adaptive_difficulty_enabled = enabled
    return profile


def _attempt(user, challenge_type: str, challenge_id, level: str) -> AdaptiveAttempt:
    attempt, _ = AdaptiveAttempt.objects.select_for_update().get_or_create(
        user=user,
        challenge_type=challenge_type,
        challenge_id=str(challenge_id),
        defaults={"level": level},
    )
    return attempt


def start_challenge(
    user, challenge_type: str, challenge_id
) -> Optional[AdaptiveAttempt]:
    """
    Start the server side clock. Opening the challenge again keeps the first
    start time and level. Returns None when the learner has not opted in.
    """
    profile = profile_for(user)
    if not profile.adaptive_difficulty_enabled:
        return None
    with transaction.atomic():
        attempt = _attempt(
            user,
            challenge_type,
            challenge_id,
            scaffolding_level(profile.skill_rating),
        )
        # No clock for a challenge already submitted without being started.
        if attempt.started_at is None and attempt.submissions == 0:
            attempt.started_at = timezone.now()
            attempt.save(update_fields=["started_at"])
    return attempt


def record_hint(user, challenge_type: str, challenge_id, available: int = 1) -> None:
    """Count a hint. Seeing the same hint again does not count twice."""
    profile = profile_for(user)
    if not profile.adaptive_difficulty_enabled:
        return
    with transaction.atomic():
        attempt = _attempt(
            user,
            challenge_type,
            challenge_id,
            scaffolding_level(profile.skill_rating),
        )
        if attempt.solved_at is None and attempt.hints_used < available:
            attempt.hints_used += 1
            attempt.save(update_fields=["hints_used"])


def record_submission(
    user, challenge_type: str, challenge_id, *, solved: bool, difficulty: str
) -> Optional[dict]:
    """
    Update the learner and challenge ratings after one submission.

    Returns None when the learner has not opted in. Submissions after a solve,
    and failures past MAX_RATED_FAILURES, leave the ratings unchanged.
    """
    with transaction.atomic():
        # Lock order is always profile, attempt, challenge.
        profile = (
            UserProfile.objects.select_for_update()
            .filter(user=user, adaptive_difficulty_enabled=True)
            .first()
        )
        if profile is None:
            return None
        attempt = _attempt(
            user,
            challenge_type,
            challenge_id,
            scaffolding_level(profile.skill_rating),
        )
        learner = Rating(
            profile.skill_rating,
            profile.rating_deviation,
            profile.rating_volatility,
        )
        result = {
            "rated": False,
            "rating_before": learner.rating,
            "skill_rating": learner.rating,
            "rating_deviation": learner.deviation,
            "level": scaffolding_level(learner.rating),
            "bonus_met": False,
        }
        if attempt.solved_at is not None:
            return result

        now = timezone.now()
        attempt.submissions += 1
        if not solved:
            attempt.failed_attempts += 1
            if attempt.failed_attempts > MAX_RATED_FAILURES:
                attempt.save()
                return result

        time_spent = (
            (now - attempt.started_at).total_seconds() if attempt.started_at else None
        )
        if solved:
            attempt.solved_at = now
            bonus = challenge_parameters(attempt.level, difficulty)["bonus_criteria"]
            result["bonus_met"] = (
                time_spent is not None
                and time_spent <= bonus["max_seconds"]
                and attempt.hints_used <= bonus["max_hints"]
                and attempt.failed_attempts <= bonus["max_failed_attempts"]
            )
        attempt.save()

        challenge_row, _ = ChallengeRating.objects.select_for_update().get_or_create(
            challenge_type=challenge_type,
            challenge_id=str(challenge_id),
            defaults={"rating": CHALLENGE_START_RATING.get(difficulty, DEFAULT_RATING)},
        )
        challenge = Rating(
            challenge_row.rating, challenge_row.deviation, challenge_row.volatility
        )
        score = performance_score(
            solved=solved,
            hints_used=attempt.hints_used,
            time_spent=time_spent,
            target_seconds=TARGET_SECONDS.get(
                difficulty, TARGET_SECONDS["intermediate"]
            ),
        )
        # Both sides are rated from the values they had before this game.
        new_learner = glicko2_update(learner, [(challenge, score)])
        new_challenge = glicko2_update(challenge, [(learner, 1.0 - score)])

        UserProfile.objects.filter(pk=profile.pk).update(
            skill_rating=new_learner.rating,
            rating_deviation=new_learner.deviation,
            rating_volatility=new_learner.volatility,
        )
        challenge_row.rating = new_challenge.rating
        challenge_row.deviation = new_challenge.deviation
        challenge_row.volatility = new_challenge.volatility
        challenge_row.games += 1
        challenge_row.save()

        result.update(
            rated=True,
            skill_rating=new_learner.rating,
            rating_deviation=new_learner.deviation,
            level=scaffolding_level(new_learner.rating),
        )
        return result
