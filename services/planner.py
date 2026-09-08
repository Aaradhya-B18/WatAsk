from typing import Optional

MATH_FACULTY = {"CS", "MATH", "STAT", "PMATH", "AMATH", "ACTSC", "CO", "MATBUS", "DATSC"}
MAX_PER_TERM = 5
MAX_NON_MATH_PER_TERM = 2

# Courses worth 0.25 units — a term containing one of these can hold an extra course
HALF_CREDIT_COURSES = {"CS 136L"}

# Non-math electives fill early free slots; math electives take over in upper years
NON_MATH_ELECTIVE_START = "1A"


def generate_plan(
    program: str,
    terms: list[str],
    taken: list[str],
    groups: list[dict],
    placed: Optional[dict],
    prereqs: dict,
    specialization: Optional[list[str]] = None,
    current_term: Optional[str] = None,
    max_per_term: int = 5,
    extra_slots: int = 0,
    retaking: Optional[list[str]] = None,
    taken_grades: Optional[dict] = None,
) -> str:
    """
    Greedy 3-phase course scheduler.

    Phase 1 — required courses, multi-pass prereq resolution.
    Phase 2 — advanced/elective pool from 3A onward.
    Phase 3 — fill remaining slots with Non-Math / Free electives (2B onward only).

    Returns a newline-joined string of "TERM: course1, course2, ..." lines.
    """
    all_required: list[str] = []
    advanced_pool: list[str] = []
    for g in groups:
        if g["name"].startswith("Advanced"):
            advanced_pool.extend(g["courses"])
        else:
            all_required.extend(g["courses"])

    # Prioritise chosen specialization courses at the front of the pool
    if specialization:
        spec_set = set(specialization)
        prioritised = [c for c in advanced_pool if c in spec_set]
        rest = [c for c in advanced_pool if c not in spec_set]
        advanced_pool = prioritised + rest

    typical: dict[str, str] = {}
    for g in groups:
        for code, term in (g.get("typical") or {}).items():
            typical[code] = term

    placed_flat: set[str] = set()
    grid_by_term: dict[str, list[str]] = {}
    if placed:
        for term_id, codes in placed.items():
            clean = [c for c in codes if c]
            grid_by_term[term_id] = clean
            placed_flat.update(clean)

    retaking_set = set(retaking or [])
    grades = taken_grades or {}

    already_done = set(taken) | placed_flat
    # Retaking courses must be re-scheduled even though they appear in taken
    to_schedule = [c for c in all_required if c not in already_done or c in retaking_set]

    study_terms = [t for t in terms if t != "COOP"]
    if not study_terms:
        return "No study terms found."

    term_index = {t: i for i, t in enumerate(study_terms)}
    # Always generate the full idealized 1A-4B plan rather than gating scheduling
    # by current_term — that caused required courses missing from an under-logged
    # past term to cascade into every later term instead of staying put.
    current_term_idx = 0
    schedule: dict[str, list[str]] = {t: [] for t in study_terms}

    def placed_before(term_idx: int) -> set[str]:
        # A retaking course isn't "done" just because it's in taken history —
        # it only counts once its rescheduled attempt actually lands somewhere
        result = set(taken) - retaking_set
        for j in range(term_idx):
            t = study_terms[j]
            result.update(grid_by_term.get(t, []))
            for c in schedule[t]:
                result.add(c.replace("[suggested]", "").strip())
        return result

    def term_max(term: str) -> int:
        """Max courses for this term — one extra slot if a half-credit course is present."""
        all_in_term = list(grid_by_term.get(term, [])) + list(schedule[term])
        half_credits = sum(1 for c in all_in_term
                          if c.replace("[suggested]", "").strip() in HALF_CREDIT_COURSES)
        return max_per_term + half_credits

    def term_capacity(term: str) -> int:
        return term_max(term) - len(grid_by_term.get(term, [])) - len(schedule[term])

    def prereqs_ok(code: str, term_idx: int) -> bool:
        if code not in prereqs:
            return True
        done = placed_before(term_idx)
        for group in prereqs[code]:
            group_satisfied = False
            for entry in group:
                parts = entry.split(":")
                req_course = parts[0]
                min_grade = int(parts[1]) if len(parts) > 1 else 50
                if req_course not in done:
                    continue
                # Being retaken — the old failing grade shouldn't count against
                # a fresh attempt, regardless of whether it's still recorded
                if req_course in retaking_set:
                    group_satisfied = True
                    break
                # Course is done — check if grade meets the minimum
                if req_course in grades:
                    # Known grade from history: verify it meets the minimum
                    if grades[req_course] >= min_grade:
                        group_satisfied = True
                        break
                    # Grade known but below minimum — not satisfied by this entry
                else:
                    # No recorded grade (course is in plan/retake schedule) — assume it meets minimum
                    group_satisfied = True
                    break
            if not group_satisfied:
                return False
        return True

    def sort_key(code: str):
        t = typical.get(code, study_terms[-1])
        return (term_index.get(t, len(study_terms)), code)

    # Phase 1 — required courses
    # Prefer ≤4 required per term (reserve 1 slot for electives/breathing room).
    # Only overflow to 5 in the final passes when no 4-slot term is available.
    unplaced = sorted(to_schedule, key=sort_key)
    n_passes = len(study_terms) + 2
    for pass_num in range(n_passes):
        if not unplaced:
            break
        # First (n_passes - 2) passes: cap at 4 required per term (capacity must be > 1)
        # Final 2 passes: allow 5 per term as overflow (capacity > 0)
        min_cap = 1 if pass_num < n_passes - 2 else 0
        still_unplaced: list[str] = []
        for code in unplaced:
            target = typical.get(code, study_terms[-1])
            start_idx = max(term_index.get(target, 0), current_term_idx)
            placed_flag = False
            for i in range(start_idx, len(study_terms)):
                if prereqs_ok(code, i) and term_capacity(study_terms[i]) > min_cap:
                    schedule[study_terms[i]].append(code)
                    placed_flag = True
                    break
            if not placed_flag:
                still_unplaced.append(code)
        unplaced = still_unplaced

    # Phase 2 — advanced pool from 3A, spread evenly across remaining terms
    import math as _math
    adv_start_idx = max(term_index.get("3A", len(study_terms) // 2), current_term_idx)
    avail_adv = [c for c in advanced_pool if c not in already_done]
    n_adv_terms = len(study_terms) - adv_start_idx
    # Spread pool evenly AND cap at (capacity - reserve) so elective slots remain
    spread_cap = _math.ceil(len(avail_adv) / n_adv_terms) if n_adv_terms > 0 else MAX_PER_TERM
    adv_placed: dict[str, int] = {t: 0 for t in study_terms}
    for code in avail_adv:
        for i in range(adv_start_idx, len(study_terms)):
            t = study_terms[i]
            if (prereqs_ok(code, i)
                    and term_capacity(t) > 1
                    and adv_placed[t] < spread_cap):
                schedule[t].append(code + "[suggested]")
                adv_placed[t] += 1
                break

    # Phase 3 — fill remaining slots with electives (non-math electives start from 2B)
    required_non_math = sum(1 for c in all_required if c.split()[0] not in MATH_FACULTY)
    non_math_left = max(0, 10 - required_non_math)
    non_math_start_idx = term_index.get(NON_MATH_ELECTIVE_START, 0)
    math_elective_label = "CS Elective" if program == "cs" else "Math Elective"

    extra_needed = extra_slots  # one extra elective slot per retake, spread across terms
    lines = []
    for idx, term in enumerate(study_terms):
        if idx < current_term_idx:
            continue
        all_in_term = list(grid_by_term.get(term, [])) + list(schedule[term])
        parts = list(all_in_term)
        half_credits = sum(1 for c in all_in_term if c.replace("[suggested]", "").strip() in HALF_CREDIT_COURSES)
        fill_max = 5 + half_credits
        # Give exactly one extra slot to each term until the credit deficit is covered
        if extra_needed > 0:
            fill_max += 1
            extra_needed -= 1
        open_slots = max(0, fill_max - len(all_in_term))
        non_math_this_term = 0
        # 1st year: up to 2 non-math per term; 2nd year+: max 1 non-math per term
        max_non_math = 2 if term in ("1A", "1B") else 1
        for _ in range(open_slots):
            if (non_math_left > 0
                    and non_math_this_term < max_non_math
                    and idx >= non_math_start_idx):
                parts.append("Non-Math Elective")
                non_math_left -= 1
                non_math_this_term += 1
            else:
                parts.append(math_elective_label)
        if parts:
            lines.append(f"{term}: {', '.join(parts)}")

    if unplaced:
        unplaced_set = set(unplaced)
        # Everything actually completed or successfully scheduled anywhere —
        # used to tell a genuine root cause (bad grade, missing prereq) apart
        # from a course that's merely stuck waiting on another blocked one.
        satisfiable = set(already_done) - retaking_set
        for t in study_terms:
            satisfiable.update(c.replace("[suggested]", "").strip() for c in schedule[t])

        def independent_blockers(code: str) -> Optional[list[str]]:
            """Returns reason texts for the first prereq group that's both
            unsatisfied AND not just waiting on another stuck course — i.e. a
            genuine independent cause, not a downstream cascade. None means
            code has no independent cause of its own (pure cascade, or its
            prereqs are actually fine and it's just a scheduling/capacity
            casualty)."""
            chain = prereqs.get(code)
            if not chain:
                return None
            for group in chain:
                blockers = []
                pending_on_cascade = False
                for entry in group:
                    parts = entry.split(":")
                    req_course, min_grade = parts[0], (int(parts[1]) if len(parts) > 1 else 50)
                    if req_course in unplaced_set:
                        pending_on_cascade = True
                        break
                    if req_course in retaking_set:
                        blockers = []
                        break
                    if req_course not in satisfiable:
                        blockers.append(f"{req_course} (not completed)")
                    elif req_course in grades and grades[req_course] < min_grade:
                        blockers.append(f"{req_course} (have {grades[req_course]}%, need {min_grade}%)")
                    else:
                        blockers = []  # this group IS satisfied
                        break
                if pending_on_cascade:
                    continue  # this group will resolve once the cascade's root is fixed
                if blockers:
                    return blockers
            return None

        root_causes = []
        for code in unplaced:
            blockers = independent_blockers(code)
            if blockers:
                root_causes.append(f"{code} needs one of: {', '.join(blockers)}")

        if root_causes:
            lines.append("UNSCHEDULED (fix these to unblock the rest): " + " | ".join(root_causes))
        else:
            lines.append(f"UNSCHEDULED: {', '.join(unplaced)}")

    return "\n".join(lines)
