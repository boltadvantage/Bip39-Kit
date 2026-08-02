#!/usr/bin/env python3
"""
BIP39 utilities: generate, verify, and audit a wordlist. Pure stdlib.

  ./bip39.py gen [N]          generate N 24-word mnemonics (default 1)
  ./bip39.py gen12 [N]        generate N 12-word mnemonics
  ./bip39.py verify "w1 ..."  check a mnemonic's checksum
  ./bip39.py audit other.txt  diff another wordlist against the canonical one

Entropy comes from secrets.token_bytes -> the OS CSPRNG (getrandom(2)).
"""
import hashlib
import math
import re
import os
import secrets
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORDLIST = os.path.join(HERE, "english.txt")
CANONICAL_SHA256 = "2f5eed53a4727b4bf8880d8f3f199efc90e58503646d9ff8eff3a2ed3b24dbda"


def load_words(path=WORDLIST):
    with open(path, "rb") as f:
        raw = f.read()
    if path == WORDLIST:
        got = hashlib.sha256(raw).hexdigest()
        if got != CANONICAL_SHA256:
            sys.exit(f"FATAL: wordlist hash mismatch\n  expected {CANONICAL_SHA256}\n  got      {got}")
    words = raw.decode("utf-8").split("\n")
    words = [w.strip() for w in words if w.strip()]
    if len(words) != 2048:
        sys.exit(f"FATAL: expected 2048 words, got {len(words)}")
    return words


def generate(words, strength_bits=256):
    """strength 256 -> 24 words, 128 -> 12 words."""
    if strength_bits % 32 or not 128 <= strength_bits <= 256:
        sys.exit("strength must be 128..256 and a multiple of 32")
    entropy = secrets.token_bytes(strength_bits // 8)
    checksum_bits = strength_bits // 32
    digest = hashlib.sha256(entropy).digest()

    bits = "".join(f"{b:08b}" for b in entropy)
    bits += f"{digest[0]:08b}"[:checksum_bits]

    return " ".join(words[int(bits[i:i + 11], 2)] for i in range(0, len(bits), 11))


# Repeating die-size patterns. Every size is a power of two, so each roll
# contributes a whole number of bits and nothing is ever rejected.
# Each pattern multiplies out to exactly 2048, so one throw = one word with
# nothing discarded and nothing rerolled. The d8 leads every mixed pattern on
# purpose: word 24 needs only 3 more entropy bits, and a d8 supplies exactly 3,
# so even the final partial throw wastes nothing.
PATTERNS = {
    "d8d4":     [8, 8, 8, 4],       # 3+3+3+2 = 11 bits
    "d16d8":    [8, 16, 16],        # 3+4+4 = 11 bits  (fewest dice)
    "d16d8d4":  [8, 16, 4, 4],      # 3+4+2+2 = 11 bits
    "d8d4coin": [8, 8, 4, 4, 2],    # 3+3+2+2+1 = 11 bits
    "coin":     [2],                # 11 flips = 11 bits
    "d4":       [4],
    "d8":       [8],
    "d16":      [16],
}


# Identical dice thrown as a set, one complete word per throw.
#   (die size, dice per throw, keep outcomes below this)
# The threshold is the largest multiple of 2048 the throw can reach, so that
# `n % 2048` stays perfectly uniform. For power-of-two dice the throw total is
# already a multiple of 2048 and nothing is ever rejected -- surplus bits are
# simply discarded, which costs nothing in fairness.
GROUPS = {
    "d16x3": (16, 3, 4096),   # 16^3 = 4096 = 2 x 2048
    "d8x4":  (8, 4, 4096),    #  8^4 = 4096
    "d4x6":  (4, 6, 4096),    #  4^6 = 4096
    "d6":    (6, 5, 6144),    #  6^5 = 7776 -> keep 6144, reroll ~21%
}


def dice_bits(mode, rolls, need):
    """Turn a list of die faces into `need` bits. Returns (bits, dice_used)."""
    if mode in GROUPS:
        size, count, ceiling = GROUPS[mode]
        total = size ** count
        bits, used, rejected = "", 0, 0

        for i in range(0, len(rolls) - count + 1, count):
            group = rolls[i:i + count]
            bad = [d for d in group if not 1 <= d <= size]
            if bad:
                sys.exit(f"{mode} mode: face {bad[0]} is not 1-{size}")
            n = 0
            for d in group:
                n = n * size + (d - 1)
            used += count
            if n >= ceiling:
                rejected += 1
                continue
            bits += f"{n % 2048:011b}"
            if len(bits) >= need:
                break

        if rejected:
            drop = total - ceiling
            print(f"# {rejected} throw(s) rejected ({drop} of {total} outcomes are out of range)",
                  file=sys.stderr)
        return bits, used

    pattern = PATTERNS[mode]
    bits, used = "", 0
    for i, face in enumerate(rolls):
        size = pattern[i % len(pattern)]
        if not 1 <= face <= size:
            sys.exit(f"{mode} mode: roll #{i + 1} is {face}, but that die is a d{size} (1-{size})")
        bits += f"{face - 1:0{size.bit_length() - 1}b}"
        used = i + 1
        if len(bits) >= need:
            break
    return bits, used


def dice_plan(mode, need):
    """How many dice to roll, and how they group up."""
    if mode in GROUPS:
        size, count, ceiling = GROUPS[mode]
        total = size ** count
        throws = -(-(need + need // 32) // 11)
        waste = "no rerolls, {} surplus bit(s) discarded per throw".format(
            total.bit_length() - 1 - 11) if ceiling == total else \
            "reroll {:.0%} of throws".format((total - ceiling) / total)
        return (f"{count}d{size} per word ({total} outcomes; {waste}), "
                f"{throws} throws = {throws * count} dice")
    pattern = PATTERNS[mode]
    bits, n = 0, 0
    while bits < need:
        bits += pattern[n % len(pattern)].bit_length() - 1
        n += 1
    sizes = ", ".join(f"d{s}" for s in pattern)
    per_group = sum(s.bit_length() - 1 for s in pattern)
    grouping = f"{len(pattern)} dice ({sizes}) = {per_group} bits" if len(pattern) > 1 \
        else f"1 die (d{pattern[0]}) = {per_group} bits"
    return f"{n} rolls total -- {grouping} per group"


def from_dice(words, mode, rolls, strength_bits=256):
    need = strength_bits
    bits, used = dice_bits(mode, rolls, need)

    if len(bits) < need:
        have = len(bits)
        sys.exit(
            f"not enough entropy: got {have} of {need} bits from {used} dice.\n"
            f"  {dice_plan(mode, need)}"
        )

    bits = bits[:need]
    entropy = int(bits, 2).to_bytes(need // 8, "big")
    checksum_bits = need // 32
    full = bits + f"{hashlib.sha256(entropy).digest()[0]:08b}"[:checksum_bits]
    return " ".join(words[int(full[i:i + 11], 2)] for i in range(0, len(full), 11)), used


def _gser(a, x):
    """Regularized lower incomplete gamma P(a,x) by series expansion."""
    ap, s, d = a, 1.0 / a, 1.0 / a
    for _ in range(500):
        ap += 1
        d *= x / ap
        s += d
        if abs(d) < abs(s) * 1e-14:
            break
    return s * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _gcf(a, x):
    """Regularized upper incomplete gamma Q(a,x) by continued fraction."""
    tiny = 1e-300
    b, c, d = x + 1 - a, 1 / tiny, 1 / (x + 1 - a)
    h = d
    for i in range(1, 500):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-14:
            break
    return h * math.exp(-x + a * math.log(x) - math.lgamma(a))


def chi2_sf(stat, df):
    """P(chi-square_df >= stat) -- the p-value."""
    if stat <= 0:
        return 1.0
    a, x = df / 2.0, stat / 2.0
    return 1.0 - _gser(a, x) if x < a + 1 else _gcf(a, x)


def ncx2_sf(x, df, lam):
    """P(noncentral chi-square(df, lam) > x), as a Poisson mixture of central ones."""
    if lam <= 0:
        return chi2_sf(x, df)
    half, total, k = lam / 2.0, 0.0, 0
    while k < 800:
        w = math.exp(-half + k * math.log(half) - math.lgamma(k + 1))
        total += w * chi2_sf(x, df + 2 * k)
        if k > half and w < 1e-16:
            break
        k += 1
    return min(1.0, total)


def chi2_crit(df, alpha=0.05):
    """The chi-square value a fair die exceeds only `alpha` of the time."""
    lo, hi = 0.0, df * 20.0 + 200
    for _ in range(200):
        mid = (lo + hi) / 2
        if chi2_sf(mid, df) > alpha:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def detect_power(sides, n, excess, alpha=0.05):
    """
    Chance of flagging a die whose worst face is over-represented by `excess`.

    Bigger dice need MORE rolls, not fewer: the non-centrality per roll is
    excess^2 * (sides-1) / (sides+excess)^2, which falls off roughly as 1/sides,
    and the extra degrees of freedom raise the threshold again.
    """
    df = sides - 1
    lam = n * excess ** 2 * (sides - 1) / (sides + excess) ** 2
    return ncx2_sf(chi2_crit(df, alpha), df, lam)


def rolls_for(sides, excess, want=0.80):
    """
    Fewest rolls giving `want` probability of detection.

    The non-central chi-square approximation runs about 10% optimistic against
    a direct simulation, so the answer carries a matching safety margin -- an
    under-powered test that looks adequate is the failure worth avoiding.
    """
    lo, hi = sides * 5, sides * 600
    while lo < hi:
        mid = (lo + hi) // 2
        if detect_power(sides, mid, excess) >= want:
            hi = mid
        else:
            lo = mid + 1
    return int(lo * 1.12)


def roll_guidance(sides):
    """(rolls to catch a doubled face, rolls to catch a +50% face) at 80%."""
    return rolls_for(sides, 1.0), rolls_for(sides, 0.5)


def test_die(sides, rolls):
    """Chi-square goodness-of-fit plus a repeat check for independence."""
    bad = [r for r in rolls if not 1 <= r <= sides]
    if bad:
        sys.exit(f"face {bad[0]} is outside 1-{sides}")
    n = len(rolls)
    if n < sides * 5:
        print(f"NOTE: {n} rolls is below the {sides * 5} needed for the test to be "
              f"valid (expected count >= 5 per face).\n", file=sys.stderr)

    counts = [rolls.count(f) for f in range(1, sides + 1)]
    exp = n / sides
    stat = sum((c - exp) ** 2 / exp for c in counts)
    df = sides - 1
    p = chi2_sf(stat, df)

    print(f"  {n} rolls of a d{sides}   expected {exp:.1f} per face\n")
    width = max(counts) or 1
    for f, c in enumerate(counts, 1):
        bar = "#" * int(38 * c / width)
        flag = "  <-- " + ("high" if c > exp else "low") if abs(c - exp) > 3 * math.sqrt(exp) else ""
        print(f"    {f:>3}  {c:>5}  {bar}{flag}")

    print(f"\n  chi-square {stat:.2f}   df {df}   p = {p:.4f}")
    if p < 0.01:
        print("  VERDICT: strong evidence this die is biased -- do not use it")
    elif p < 0.05:
        print("  VERDICT: suspicious. Roll another few hundred times before trusting it")
    else:
        print("  VERDICT: no evidence of bias at this sample size")

    # independence: a fair, well-rolled die repeats its previous face 1/sides of the time
    reps = sum(1 for a, b in zip(rolls, rolls[1:]) if a == b)
    m = n - 1
    exp_r = m / sides
    sd = math.sqrt(m * (1 / sides) * (1 - 1 / sides))
    z = (reps - exp_r) / sd if sd else 0.0
    print(f"\n  repeats: {reps} of {m} consecutive pairs (expect {exp_r:.1f}, z = {z:+.2f})")
    if abs(z) > 3:
        print("  -> rolls look DEPENDENT. Are you dropping the die the same way each time?")
    else:
        print("  -> no sign of dependence between consecutive rolls")

    gross, fine = roll_guidance(sides)
    print(f"\n  Passing means no bias was DETECTED, not that none exists. For a d{sides},")
    print(f"  an 80% chance of catching a face that comes up twice as often needs")
    print(f"  ~{gross} rolls; catching a 50%-over face needs ~{fine}.", end="")
    if n < gross:
        print(f" You have {n}.")
    else:
        print(f" You have {n} -- enough for the first.")
    return p


def _ask(prompt, default=None):
    try:
        got = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit("cancelled")
    return got or (default if default is not None else "")


def plan_session(sides=None, target=None):
    """Ask what die, offer roll counts by how much bias each would catch."""
    while sides is None:
        got = _ask("\n  How many sides does your die have? > ")
        if got.lstrip("dD").isdigit() and 2 <= int(got.lstrip("dD")) <= 1000:
            sides = int(got.lstrip("dD"))
        else:
            print("  give a number from 2 to 1000 (e.g. 16, or d16)")

    if target is not None:
        return sides, target

    tiers = [
        (sides * 5,                      "bare minimum -- the test is only just valid"),
        (rolls_for(sides, 1.0, 0.80),    "catches a badly defective die"),
        (rolls_for(sides, 1.0, 0.98),    "near-certain on a doubled face"),
        (rolls_for(sides, 0.5, 0.80),    "catches subtle bias too"),
    ]
    # keep them strictly increasing and distinct
    clean, last = [], 0
    for n, why in tiers:
        if n > last:
            clean.append((n, why))
            last = n
    tiers = clean

    print(f"\n  Testing a d{sides}. How thorough do you want to be?\n")
    print(f"    {'#':>2}  {'rolls':>6}   {'catches a':>11}  {'catches a':>11}   {'approx':>7}")
    print(f"    {'':>2}  {'':>6}   {'doubled face':>11}  {'+50% face':>11}   {'time':>7}")
    for i, (n, why) in enumerate(tiers, 1):
        p100 = detect_power(sides, n, 1.0)
        p50 = detect_power(sides, n, 0.5)
        mins = max(1, round(n * 4 / 60))
        print(f"    {i:>2}  {n:>6}   {p100:>10.0%}  {p50:>11.0%}   {mins:>5} min   {why}")

    rec = 2 if len(tiers) > 1 else 1
    print(f"\n  Pick 1-{len(tiers)}, or type any roll count you prefer.")
    while True:
        got = _ask(f"  How many rolls? [{rec}] > ", str(rec))
        if not got.isdigit():
            print("  numbers only")
            continue
        v = int(got)
        if 1 <= v <= len(tiers):
            return sides, tiers[v - 1][0]
        if v >= sides * 5:
            return sides, v
        print(f"  {v} is below the {sides * 5} needed for the test to mean anything")


def _save_rolls(logpath, rolls):
    if logpath:
        with open(logpath, "w") as f:
            f.write(" ".join(map(str, rolls)) + "\n")


def roll_session(sides, target, logpath):
    """
    Interactive collection: roll, type the face, repeat. Every entry is written
    straight to the log, so a crash or a closed terminal costs you nothing.

    Running face counts are deliberately NOT displayed during collection --
    seeing that a face is 'behind' can nudge how you throw, which is exactly the
    dependence the test is meant to detect.
    """
    rolls = []
    if logpath and os.path.exists(logpath):
        prior = [int(t) for t in re.findall(r'\d+', open(logpath).read())
                 if 1 <= int(t) <= sides]
        if prior:
            ans = input(f"{logpath} already holds {len(prior)} rolls. Resume? [Y/n] ")
            if ans.strip().lower() in ("", "y", "yes"):
                rolls = prior
                print(f"resumed at {len(rolls)}")

    print(f"\nRolling a d{sides} -- target {target} rolls.")
    print("  type the face after each roll, then Enter")
    print("  several at once is fine:  3 7 12 1")
    print("  u = undo last     q = stop early and test what we have\n")

    while len(rolls) < target:
        left = target - len(rolls)
        try:
            line = input(f"  [{len(rolls):>4}/{target}]  {left:>4} left > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line in ("q", "quit", "stop"):
            break
        if line in ("u", "undo"):
            if rolls:
                print(f"         undid {rolls.pop()}")
                _save_rolls(logpath, rolls)
            else:
                print("         nothing to undo")
            continue

        added = 0
        for t in line.split():
            if not t.isdigit():
                print(f"         '{t}' is not a number -- ignored")
                continue
            v = int(t)
            if not 1 <= v <= sides:
                print(f"         {v} is not 1-{sides} -- ignored")
                continue
            rolls.append(v)
            added += 1
            if len(rolls) >= target:
                break
        if added:
            _save_rolls(logpath, rolls)

    print(f"\ncollected {len(rolls)} rolls" + (f", saved to {logpath}" if logpath else ""))
    if len(rolls) < target:
        print(f"({target - len(rolls)} short of the target -- "
              f"rerun with the same --log to pick up where you left off)")
    print()
    return rolls


def von_neumann(throws, width, need):
    """
    Whiten biased coins. Compare each coin against ITSELF in the next throw:
    differ -> keep the first bit, same -> discard. Output is exactly unbiased
    for any per-coin bias, as long as flips are independent. Comparing coin 3
    against coin 4 would NOT be valid -- they can have different biases -- which
    is why this pairs by position rather than walking the stream.
    """
    bits, used, tossed = "", 0, 0
    for i in range(0, len(throws) - 1, 2):
        a, b = throws[i], throws[i + 1]
        used += 2
        for p in range(width):
            if a[p] != b[p]:
                bits += a[p]
            else:
                tossed += 1
            if len(bits) >= need:
                return bits, used, tossed
    return bits, used, tossed


def parse_coins(raw, width):
    """H/T, h/t, 1/0 -> list of throws, each `width` bits."""
    flat = "".join("1" if c in "H h 1".split() or c in "Hh1" else "0"
                   for c in raw if c in "HhTt10")
    if len(flat) % width:
        flat = flat[:len(flat) - len(flat) % width]
    return [flat[i:i + width] for i in range(0, len(flat), width)]


def from_coins(words, raw, width=11, strength_bits=256, whiten=True):
    throws = parse_coins(raw, width)
    if not throws:
        sys.exit("no coin results found -- use H/T or 1/0")

    if whiten:
        bits, used, tossed = von_neumann(throws, width, strength_bits)
        note = f"{used} throws consumed, {tossed} bits discarded by whitening"
    else:
        bits = "".join(throws)[:strength_bits]
        used, note = len(throws), f"{len(throws)} throws, raw (no whitening)"

    if len(bits) < strength_bits:
        need_throws = math_ceil_throws(strength_bits, width, whiten)
        sys.exit(f"not enough entropy: {len(bits)} of {strength_bits} bits from "
                 f"{len(throws)} throws.\n  budget about {need_throws} throws of "
                 f"{width} coin(s)" + (" when whitening" if whiten else ""))

    entropy = int(bits, 2).to_bytes(strength_bits // 8, "big")
    checksum_bits = strength_bits // 32
    full = bits + f"{hashlib.sha256(entropy).digest()[0]:08b}"[:checksum_bits]
    return " ".join(words[int(full[i:i + 11], 2)] for i in range(0, len(full), 11)), note


def math_ceil_throws(need, width, whiten):
    per_throw = width / 2 if whiten else width   # whitening keeps ~half the bits
    return int(-(-need // per_throw)) + 2


def final_words(words, rolled):
    """
    Given the words you actually rolled, list every valid word for the last slot.

    BIP39's last word is mostly checksum, so it cannot be rolled -- for a
    24-word phrase exactly 8 words complete it, and you pick among them with
    one d8. This is the one place BIP39 differs from Diceware, which has no
    checksum and lets you roll every word independently.
    """
    toks = rolled.lower().split()
    target = {23: 24, 20: 21, 17: 18, 14: 15, 11: 12}.get(len(toks))
    if not target:
        sys.exit(f"give 23 rolled words (or 11/14/17/20 for a shorter phrase); got {len(toks)}")

    index = {w: i for i, w in enumerate(words)}
    bad = [t for t in toks if t not in index]
    if bad:
        sys.exit(f"not in the wordlist: {', '.join(bad)}")

    total_bits = target * 11
    strength = total_bits * 32 // 33
    checksum_bits = total_bits - strength

    rolled_bits = "".join(f"{index[t]:011b}" for t in toks)
    free = strength - len(rolled_bits)          # entropy bits still unspoken for

    out = []
    for extra in range(1 << free):
        bits = rolled_bits + f"{extra:0{free}b}"
        entropy = int(bits, 2).to_bytes(strength // 8, "big")
        digest = f"{hashlib.sha256(entropy).digest()[0]:08b}"[:checksum_bits]
        out.append(words[int(bits[len(rolled_bits):] + digest, 2)])
    return out, free


def table_entries(words, mode):
    """[(throw, word)] for a lookup table, in index order."""
    if mode == "d6":
        # 5d6 gives 7776 outcomes for 2048 words. 7776 isn't a multiple of
        # 2048, so the tail of the table has to say throw again -- the price
        # of using d6 on a list that wasn't sized for it.
        out = []
        for n in range(7776):
            faces, m = [], n
            for _ in range(5):
                faces.append(str(m % 6 + 1))
                m //= 6
            out.append(("-".join(reversed(faces)),
                        "(reroll)" if n >= 6144 else words[n % 2048]))
        rr = sum(1 for _, w in out if w == "(reroll)")
        return out, "throw 5d6", f"{rr} of 7776 throws say (reroll)"

    pattern = PATTERNS[mode]
    if sum(s.bit_length() - 1 for s in pattern) != 11:
        sys.exit(f"{mode} is not one-throw-one-word; pick a pattern worth 11 bits")

    out = []
    for i, w in enumerate(words):
        bits, faces, at = f"{i:011b}", [], 0
        for size in pattern:
            n = size.bit_length() - 1
            faces.append(str(int(bits[at:at + n], 2) + 1))
            at += n
        out.append(("-".join(faces), w))
    title = "throw " + " + ".join(f"d{s}" for s in pattern)
    return out, title, f"{len(out)} throws, one word each, no rerolls"


def dice_table(words, mode, path, cols=4, rows=58):
    """
    Diceware-style lookup table, paginated into columns so it prints short.

    Entries run DOWN each column, then to the next column, then to the next
    page -- so once you know the page, you scan one column instead of hunting
    across a row. Each page header states the range it covers.
    """
    entries, title, note = table_entries(words, mode)
    tw = max(len(t) for t, _ in entries)
    ww = max(len(w) for _, w in entries)
    per_page = cols * rows
    pages = -(-len(entries) // per_page)

    lines = []
    for p in range(pages):
        chunk = entries[p * per_page:(p + 1) * per_page]
        if p:
            lines.append("\f")
        # pad headers out to exactly the data width so nothing overruns the page
        roww = cols * (tw + 2 + ww + 4) - 4
        for left, right in ((f"BIP39 dice table -- {title}, read left to right",
                             f"page {p + 1} of {pages}"),
                            (note, f"this page: {chunk[0][0]} .. {chunk[-1][0]}")):
            gap = max(2, roww - len(left) - len(right))
            lines.append(left + " " * gap + right)
        lines.append("")

        height = -(-len(chunk) // cols)
        columns = [chunk[c * height:(c + 1) * height] for c in range(cols)]
        for r in range(height):
            row = ""
            for col in columns:
                if r < len(col):
                    t, w = col[r]
                    row += f"{t:<{tw}}  {w:<{ww}}    "
            lines.append(row.rstrip())

    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    return len(entries), pages, max(len(l) for l in lines)


def verify(words, mnemonic):
    toks = mnemonic.lower().split()
    if len(toks) not in (12, 15, 18, 21, 24):
        return False, f"word count {len(toks)} is not one of 12/15/18/21/24"

    index = {w: i for i, w in enumerate(words)}
    bad = [t for t in toks if t not in index]
    if bad:
        return False, f"not in BIP39 wordlist: {', '.join(bad)}"

    bits = "".join(f"{index[t]:011b}" for t in toks)
    strength_bits = len(bits) * 32 // 33
    checksum_bits = len(bits) - strength_bits

    entropy = int(bits[:strength_bits], 2).to_bytes(strength_bits // 8, "big")
    expected = f"{hashlib.sha256(entropy).digest()[0]:08b}"[:checksum_bits]

    if bits[strength_bits:] != expected:
        return False, "checksum invalid (words are valid but the order/selection is wrong)"
    return True, f"valid {len(toks)}-word mnemonic ({strength_bits} bits entropy)"


def audit(words, other_path):
    """Compare a wordlist scraped from elsewhere against the canonical one."""
    with open(other_path, encoding="utf-8") as f:
        other = [w.strip().lower() for w in f.read().replace(",", "\n").split() if w.strip()]

    print(f"canonical: 2048 words")
    print(f"{other_path}: {len(other)} words ({len(set(other))} unique)")

    canon = set(words)
    extra = [w for w in other if w not in canon]
    missing = [w for w in words if w not in set(other)]
    dupes = sorted({w for w in other if other.count(w) > 1})

    if not extra and not missing and not dupes and len(other) == 2048:
        print("\nMATCH: identical to the canonical BIP39 English wordlist.")
        if other != words:
            print("(same words, different order -- fine for a lookup list,")
            print(" but index-sensitive tools need canonical sort order)")
        return

    if extra:
        print(f"\nNOT in BIP39 ({len(extra)}): {', '.join(sorted(set(extra))[:40])}")
    if missing:
        print(f"\nMISSING from the site ({len(missing)}): {', '.join(missing[:40])}")
    if dupes:
        print(f"\nDUPLICATED ({len(dupes)}): {', '.join(dupes[:40])}")
    print("\nMISMATCH: do not trust this list.")


def main():
    words = load_words()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "gen"

    if cmd in ("gen", "gen12"):
        strength = 128 if cmd == "gen12" else 256
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        for _ in range(n):
            print(generate(words, strength))
    elif cmd == "verify":
        ok, msg = verify(words, " ".join(sys.argv[2:]))
        print(("OK: " if ok else "FAIL: ") + msg)
        sys.exit(0 if ok else 1)
    elif cmd == "dice":
        mode = sys.argv[2] if len(sys.argv) > 2 else "d8d4"
        if mode not in PATTERNS and mode not in GROUPS:
            sys.exit(f"unknown mode '{mode}'. try: {', '.join(list(PATTERNS) + list(GROUPS))}")

        strength = 128 if "--12" in sys.argv else 256
        raw = " ".join(a for a in sys.argv[3:] if not a.startswith("--"))
        if not raw and not sys.stdin.isatty():
            raw = sys.stdin.read()

        if not raw.strip():
            print(f"mode {mode}, {strength}-bit ({(strength + strength // 32) // 11} words)")
            print(f"  {dice_plan(mode, strength)}")
            print(f"\nthen: ./bip39.py dice {mode} 3 1 8 2 5 ...")
            return

        rolls = [int(t) for t in raw.replace(",", " ").split()]
        mnemonic, used = from_dice(words, mode, rolls, strength)
        print(mnemonic)
        print(f"# {used} dice consumed; final word carries the checksum", file=sys.stderr)
    elif cmd == "test":
        spec = sys.argv[2] if len(sys.argv) > 2 else ""
        m = re.fullmatch(r'd?(\d+)', spec)
        if not m:
            sys.exit("usage: ./bip39.py test d16 <rolls...>   (or pipe rolls on stdin)")
        sides = int(m.group(1))
        raw = " ".join(sys.argv[3:])
        if not raw.strip() and not sys.stdin.isatty():
            raw = sys.stdin.read()
        if not raw.strip():
            sys.exit(f"give me the rolls: ./bip39.py test d{sides} 3 7 1 16 ...\n"
                     f"  roll at least {sides*5}; {sides*60} for a test with real power")
        rolls = [int(t) for t in raw.replace(",", " ").split()]
        p = test_die(sides, rolls)
        sys.exit(0 if p >= 0.01 else 1)
    elif cmd == "roll":
        spec = sys.argv[2] if len(sys.argv) > 2 else ""
        m = re.fullmatch(r'd?(\d+)', spec)
        sides = int(m.group(1)) if m else None
        nums = [a for a in sys.argv[3:] if a.isdigit()]
        sides, target = plan_session(sides, int(nums[0]) if nums else None)
        logpath = f"dice-log-d{sides}.txt"
        if "--log" in sys.argv:
            logpath = sys.argv[sys.argv.index("--log") + 1]
        if "--nolog" in sys.argv:
            logpath = None
        rolls = roll_session(sides, target, logpath)
        if len(rolls) < sides * 5:
            sys.exit(f"only {len(rolls)} rolls -- need at least {sides * 5} to test at all")
        p = test_die(sides, rolls)
        sys.exit(0 if p >= 0.01 else 1)
    elif cmd == "coins":
        width = 11
        if "--width" in sys.argv:
            width = int(sys.argv[sys.argv.index("--width") + 1])
        strength = 128 if "--12" in sys.argv else 256
        whiten = "--raw" not in sys.argv
        skip = {"--width", str(width), "--12", "--raw"}
        raw = " ".join(a for a in sys.argv[2:] if a not in skip)
        if not raw.strip() and not sys.stdin.isatty():
            raw = sys.stdin.read()
        if not raw.strip():
            n = math_ceil_throws(strength, width, whiten)
            print(f"{width} coin(s) per throw, {strength}-bit seed")
            print(f"  budget ~{n} throws" + (" (whitening keeps about half the bits)"
                                             if whiten else " (raw, no whitening)"))
            print(f"\nthen: ./bip39.py coins HHTHTTHTHHT HTTHH... ")
            return
        mnemonic, note = from_coins(words, raw, width, strength, whiten)
        print(mnemonic)
        print(f"# {note}", file=sys.stderr)
    elif cmd == "final":
        cands, free = final_words(words, " ".join(sys.argv[2:]))
        print(f"{len(cands)} valid final words -- roll 1d{len(cands)} and take that line:\n")
        for i, w in enumerate(cands, 1):
            print(f"  {i:>3}  {w}")
    elif cmd == "table":
        mode = sys.argv[2] if len(sys.argv) > 2 else "d16d8"
        if mode not in PATTERNS and mode != "d6":
            sys.exit(f"unknown pattern '{mode}'. try: {', '.join(list(PATTERNS) + ['d6'])}")
        cols, rows = 4, 58
        if "--cols" in sys.argv:
            cols = int(sys.argv[sys.argv.index("--cols") + 1])
        if "--rows" in sys.argv:
            rows = int(sys.argv[sys.argv.index("--rows") + 1])
        rest = [a for a in sys.argv[3:]
                if not a.startswith("--") and a not in (str(cols), str(rows))]
        path = rest[0] if rest else f"dice-table-{mode}.txt"
        n, pages, width = dice_table(words, mode, path, cols, rows)
        fit = "fits 80-col portrait" if width <= 80 else \
              "needs landscape or a smaller font" if width <= 120 else "very wide"
        print(f"wrote {n} entries to {path}")
        print(f"  {cols} columns x {rows} rows = {pages} pages, {width} chars wide ({fit})")
    elif cmd == "audit":
        audit(words, sys.argv[2])
    elif cmd == "list":
        print("\n".join(words))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
