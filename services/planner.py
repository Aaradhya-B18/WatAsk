from typing import Optional

MATH_FACULTY = {"CS", "MATH", "STAT", "PMATH", "AMATH", "ACTSC", "CO", "MATBUS", "DATSC"}
MAX_PER_TERM = 5
MAX_NON_MATH_PER_TERM = 2


def generate_plan(
    program: str,
    terms: list[str],
    taken: list[str],
    groups: list[dict],
    placed: Optional[dict],
    prereqs: dict,
) -> str:
    """
    Greedy 3-phase course scheduler.

    Phase 1 — required courses, multi-pass prereq resolution.
    Phase 2 — advanced/elective pool from 3A onward.
    Phase 3 — fill remaining slots with Non-Math / Free electives.

    Returns a newline-joined string of "TERM: course1, course2, ..." lines.
    """
    all_required: list[str] = []
    advanced_pool: list[str] = []
    for g in groups:
        if g["name"].startswith("Advanced"):
            advanced_pool.extend(g["courses"])
        else:
            all_required.extend(g["courses"])

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

    already_done = set(taken) | placed_flat
    to_schedule = [c for c in all_required if c not in already_done]

    study_terms = [t for t in terms if t != "COOP"]
    if not study_terms:
        return "No study terms found."

    term_index = {t: i for i, t in enumerate(study_terms)}
    schedule: dict[str, list[str]] = {t: [] for t in study_terms}

    def placed_before(term_idx: int) -> set[str]:
        result = set(taken)
        for j in range(term_idx):
            t = study_terms[j]
            result.update(grid_by_term.get(t, []))
            for c in schedule[t]:
                result.add(c.replace("[suggested]", "").strip())
        return result

    def term_capacity(term: str) -> int:
        return MAX_PER_TERM - len(grid_by_term.get(term, [])) - len(schedule[term])

    def prereqs_ok(code: str, term_idx: int) -> bool:
        if code not in prereqs:
            return True
        done = placed_before(term_idx)
        for group in prereqs[code]:
            if not any(c.split(":")[0] in done for c in group):
                return False
        return True

    def sort_key(code: str):
        t = typical.get(code, study_terms[-1])
        return (term_index.get(t, len(study_terms)), code)

    # Phase 1 — required courses
    unplaced = sorted(to_schedule, key=sort_key)
    for _ in range(len(study_terms) + 2):
        if not unplaced:
            break
        still_unplaced: list[str] = []
        for code in unplaced:
            target = typical.get(code, study_terms[-1])
            start_idx = term_index.get(target, 0)
            placed = False
            for i in range(start_idx, len(study_terms)):
                if prereqs_ok(code, i) and term_capacity(study_terms[i]) > 0:
                    schedule[study_terms[i]].append(code)
                    placed = True
                    break
            if not placed:
                still_unplaced.append(code)
        unplaced = still_unplaced

    # Non-math budget
    required_non_math = sum(1 for c in all_required if c.split()[0] not in MATH_FACULTY)
    non_math_left = max(0, 10 - required_non_math)

    # Phase 2 — advanced pool from 3A
    adv_start_idx = term_index.get("3A", len(study_terms) // 2)
    for code in [c for c in advanced_pool if c not in already_done]:
        for i in range(adv_start_idx, len(study_terms)):
            t = study_terms[i]
            non_math_reserve = 1 if non_math_left > 0 else 0
            if prereqs_ok(code, i) and term_capacity(t) > non_math_reserve:
                schedule[t].append(code + "[suggested]")
                break

    # Phase 3 — fill with electives
    lines = []
    for term in study_terms:
        parts = list(grid_by_term.get(term, [])) + list(schedule[term])
        open_slots = term_capacity(term)
        non_math_this_term = 0
        for _ in range(open_slots):
            if non_math_left > 0 and non_math_this_term < MAX_NON_MATH_PER_TERM:
                parts.append("Non-Math Elective")
                non_math_left -= 1
                non_math_this_term += 1
            else:
                parts.append("Free Elective")
        if parts:
            lines.append(f"{term}: {', '.join(parts)}")

    return "\n".join(lines)
