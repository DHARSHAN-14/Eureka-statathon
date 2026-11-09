"""
PIGS v5 — NCO Search Hint System
==================================
Generates natural-language search example phrases that show users
HOW to describe an occupation — "I am a...", "The person who...", etc.

Exposed via a lightbulb icon in the search bar.  Only activated when
the search needs guidance (vague / broad query or scattered results).
"""
from __future__ import annotations
import re
from collections import Counter

# ── Stop words ─────────────────────────────────────────────────────────────────
_STOP = {
    'i','me','my','we','us','you','he','she','it','they','am','is','are','was',
    'were','be','been','being','have','has','had','do','does','did','will',
    'would','shall','should','can','could','may','might','must','a','an','the',
    'and','but','or','nor','so','yet','of','at','by','for','with','about','to',
    'from','in','on','up','out','over','into','that','this','who','what','where',
    'when','how','which','as','if','then','than','no','not','also','just','very',
    'too','own','same','such','both','each','some','any','all','type','kind',
    'sort','related','person','people','one','two','three','make','made','get',
    'got','work','job','occupation','field','role','position','sector','area',
}

# ── Action verbs — signals that query describes a specific task ────────────────
_VERBS = {
    'repair','fix','maintain','service','restore','install','build','construct',
    'design','create','develop','manufacture','assemble','operate','drive','pilot',
    'manage','supervise','lead','direct','coordinate','oversee','administer',
    'teach','train','educate','instruct','tutor','treat','diagnose','prescribe',
    'nurse','sell','market','promote','advise','research','analyze','analyse',
    'study','investigate','test','inspect','cook','prepare','bake','guard',
    'protect','secure','monitor','audit','review','survey','farm','grow',
    'harvest','cultivate','write','translate','draft','edit','program','code',
    'debug','plan','schedule','organize','clean','deliver','transport','handle',
    'process','record','file','assist','weld','grind','polish','paint','plumb',
    'wire','drill','mine','load','pack','sort','serve','counsel','consult',
    'evaluate','assess','measure','calibrate','launch','deploy','troubleshoot',
    'sew','stitch','cut','spin','weave','dye','brew','distil','refine','smelt',
    'cast','forge','press','stamp','print','bind','carve','sculpt','draw',
    'photograph','film','broadcast','transmit','navigate','steer','haul','hoist',
}

# ── Single words too generic to anchor an occupation search ───────────────────
_BROAD_SINGLES = {
    'science','technology','engineering','mathematics','health','medical',
    'education','finance','law','legal','art','music','sport','sports',
    'agriculture','military','police','government','business','trade',
    'construction','manufacturing','computer','software','data','network',
    'transport','food','environment','media','communication','management',
    'administration','machine','energy','chemical','electrical','mechanical',
    'production','industry','security','research','design','banking','retail',
    'mining','fishing','farming','teaching','nursing','driving','cooking',
    'cleaning','painting','welding','printing','weaving','spinning','cutting',
}


# ── Specificity scorer ─────────────────────────────────────────────────────────

def _specificity(query: str) -> float:
    words = re.sub(r"[^a-z0-9\s]", "", query.lower()).split()
    content = [w for w in words if w not in _STOP and len(w) > 2]
    n = len(content)

    if n >= 5:   score = 0.55
    elif n >= 4: score = 0.45
    elif n >= 3: score = 0.32
    elif n >= 2: score = 0.18
    else:        score = 0.0

    if any(w in _VERBS for w in words):
        score += 0.28

    if n <= 1 and content and content[0] in _BROAD_SINGLES:
        score -= 0.20

    return max(0.0, min(score, 1.0))


# ── NCO diversity ──────────────────────────────────────────────────────────────

def _diversity(results: list) -> float:
    divs = [
        str((r.get("details") or {}).get("division", "")).strip()
        for r in results[:5]
    ]
    divs = [d for d in divs if d]
    if not divs:
        return 0.5
    return min(len(set(divs)) / len(divs), 1.0)


def _top_divisions(results: list, n: int = 4) -> list[str]:
    c: Counter = Counter()
    for r in results[:12]:
        div = str((r.get("details") or {}).get("division", "")).strip()
        if div:
            c[div] += 1
    return [d for d, _ in c.most_common(n)]


# ── Natural-language prompt generator ─────────────────────────────────────────

def _verb_phrase(title: str, description: str) -> str:
    """
    Extract a short activity phrase from the occupation description.
    Used to build "The person who <verb_phrase>" and "I <verb_phrase>" prompts.
    """
    if description:
        words = re.sub(r'\s+', ' ', description.strip()).split()
        # Find the first action verb and take up to 7 words from there
        for i, w in enumerate(words[:12]):
            if w.lower().rstrip('s,.:;') in _VERBS:
                phrase = ' '.join(words[i:i+7]).rstrip('.,;:')
                return phrase
        # Fall back: words 1-7 (skip the title that usually opens the description)
        return ' '.join(words[:7]).rstrip('.,;:')

    # No description: build from title
    base = re.sub(r',.*', '', title).strip().lower()
    return f"work as {base}"


_ARTICLE = re.compile(r'^[aeiou]', re.I)

def _article(word: str) -> str:
    return "an" if _ARTICLE.match(word) else "a"


def _make_prompts(top_results: list) -> list[str]:
    """
    Generate up to 4 natural-language search example phrases from the top results.

    Patterns (rotated across results):
      0 → "I am a/an <title>"
      1 → "The person who <verb phrase from description>"
      2 → "Working as a/an <title>"
      3 → "I <verb phrase from description>"
      4 → "In the field of <division>"
    """
    prompts: list[str] = []
    seen_titles: set[str] = set()
    divisions_used: set[str] = set()

    patterns = [
        # (uses_vp, template_fn)
        (False, lambda t, vp, div: f"I am {_article(t)} {t}"),
        (True,  lambda t, vp, div: f"The person who {vp}"),
        (False, lambda t, vp, div: f"Working as {_article(t)} {t}"),
        (True,  lambda t, vp, div: f"I {vp}"),
        (False, lambda t, vp, div: f"In the field of {div}" if div else None),
    ]

    for r in top_results[:8]:
        if len(prompts) >= 4:
            break

        title = str(r.get("occupation_title", "")).strip()
        if not title:
            continue
        # Normalise: "Software Engineer, Senior" → "Software Engineer"
        title_short = re.sub(r',.*', '', title).strip()
        key = title_short.lower()
        if key in seen_titles:
            continue
        seen_titles.add(key)

        desc = str((r.get("details") or {}).get("occupation_description", "")).strip()
        div  = str((r.get("details") or {}).get("division", "")).strip()
        vp   = _verb_phrase(title_short, desc)

        idx = len(prompts)
        uses_vp, fn = patterns[idx % len(patterns)]

        # "In the field of" pattern — only once, and only if division available
        if patterns[idx % len(patterns)][1].__code__.co_varnames and div in divisions_used:
            idx += 1  # skip, try next pattern slot

        result = fn(title_short.lower(), vp.lower(), div.lower())
        if result:
            prompts.append(result)
            if div:
                divisions_used.add(div)

    return prompts


# ── Main PIGS analyzer ─────────────────────────────────────────────────────────

def pigs_v2_analyze(query: str, top_results: list) -> dict | None:
    """
    Returns a PIGS hint payload when guidance would help, else None.

    Payload:
      {
        "prompts":   [str, ...],   # natural-language search example phrases
        "tip":       str | None,   # optional header shown in the panel
      }
    """
    query = (query or "").strip()
    if not query or not top_results:
        return None

    spec = _specificity(query)
    div  = _diversity(top_results)
    wc   = len(query.split())
    q_key = re.sub(r"[^a-z]", "", query.lower())

    is_broad_single = wc == 1 and q_key in _BROAD_SINGLES

    # Specific query + focused results — user knows what they want, stay silent
    if spec >= 0.55 and div <= 0.40:
        return None

    prompts = _make_prompts(top_results)
    if not prompts:
        return None

    if is_broad_single or (wc <= 1 and spec < 0.10):
        tip = f'"{query.capitalize()}" is broad — try describing the occupation.'
    elif spec < 0.35:
        tip = "Try describing what the person does or where they work."
    else:
        tip = "Your search spans multiple fields — try a more specific description."

    return {
        "tip":     tip,
        "prompts": prompts,
    }
