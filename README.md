# BIP39 Seed Kit

Tools for generating a Bitcoin seed phrase from **physical dice**, so the entropy
never comes from a computer's random number generator.

The guiding principle: **a computer is only ever asked to do deterministic work.**
It computes a SHA-256 checksum over words you already chose with dice. It never
generates randomness. That matters because deterministic work is *verifiable* —
run it twice on two machines and compare — while randomness is not. A backdoored
RNG produces output indistinguishable from a good one; a backdoored checksum gets
caught on the first cross-check.

---

## Contents

| file | what it is |
|---|---|
| `bip39.py` | the toolkit — dice, coins, verify, final word, tables, die testing |
| `english.txt` | canonical BIP39 English wordlist, hash-checked on every run |
| `dice-table-d16d8.txt` | **primary lookup table** — one throw of d8+d16+d16 per word — **9 pages** |
| `dice-table-d8d4.txt` | alternative — 3d8 + 1d4 per word — 9 pages |
| `dice-table-d6.txt` | 5d6 per word, with reroll rows (21% of throws) — 45 pages |
| `bip39-wordlist.html` | searchable wordlist page, opens in any browser offline |

Plus one file you download yourself — **Seed Tool**, a second implementation that
also derives addresses. It isn't shipped here (it's GPL-3.0, and you should get
the signed release from its author rather than a copy vendored by a stranger).
See [Seed Tool](#seed-tool) below.

`bip39.py` looks for `english.txt` in its own directory. Keep the folder together.

---

## Why d8 + d16 + d16

A BIP39 word is **11 bits**, because the list has 2048 words and 2^11 = 2048.

A die contributes whole bits only if its face count is a power of two:
d2 = 1 bit, d4 = 2, d8 = 3, d16 = 4.

For one throw to equal exactly one word, the bits in your hand must sum to
exactly 11. Since **11 is prime**, no set of *identical* dice can do it except
eleven coins. Mixed sets that work:

| dice | bits | count |
|---|---|---|
| **d8 + d16 + d16** | 3+4+4 | **3 — fewest possible** |
| d8 + d8 + d8 + d4 | 3+3+3+2 | 4 |
| d8 + d16 + d4 + d4 | 3+4+2+2 | 4 |
| eleven coins | 1×11 | 11 |

d6, d10, d12 and d20 carry factors of 3 or 5 that 2048 does not, so they can
never divide it evenly — they always require rerolls.

**Reading a throw** (use three different colors so place value is fixed):

```
index = 256 × (d8 − 1) + 16 × (d16a − 1) + (d16b − 1)
```

Lowest throw `1·1·1` → 0 → `abandon`. Highest `8·16·16` → 2047 → `zoo`.
Or just look the throw up in `dice-table-d16d8.txt`.

### Printing the table

`dice-table-d16d8.txt` is laid out in **4 columns across 9 pages**, 80 characters
wide — it prints on US Letter or A4 portrait in any monospace font without
wrapping. Entries run **down each column**, then to the next column, then to the
next page, so once you're on the right page you scan a single column. Every page
header states the range it covers (`this page: 1-1-1 .. 1-15-8`), and pages are
separated by form feeds so printers break cleanly.

```
./bip39.py table d16d8              # 4 columns, 9 pages, 80 wide
./bip39.py table d16d8 --cols 3     # 3 columns, 12 pages, 75 wide
./bip39.py table d16d8 --rows 66    # denser pages if your printer allows
```

Print it double-sided and it's five sheets of paper. Keep a spare copy with your
dice — the table is not secret, only your rolls are.

---

## Why you roll 23 words, not 24

A 24-word phrase is 264 bits: **256 bits of entropy + an 8-bit SHA-256 checksum.**
Words 1–23 carry 253 entropy bits. Word 24 holds the last 3 entropy bits plus
all 8 checksum bits — so it is *determined* by the first 23.

Roll all 24 blind and there is a 255-in-256 chance the phrase is invalid.

Exactly **8** words can ever complete a 24-word phrase. So:

1. Roll 23 words with the dice.
2. Run `final` to get the 8 candidates.
3. **Roll the d8 once more** to pick among them.

That last roll is real entropy, not a formality — the 8 candidates differ in 3
entropy bits and produce 8 completely different wallets. Write down which you chose.

Total: **70 dice throws.** 23 throws of 3 dice, plus one final d8.

---

## The procedure

```
1.  Test your dice                    ./bip39.py test d16 <rolls...>
2.  Throw d8+d16+d16, look up word    dice-table-d16d8.txt      ×23
3.  Compute the candidates            ./bip39.py final "<23 words>"
4.  Roll 1d8, take that line          ← word 24
5.  Confirm                           ./bip39.py verify "<24 words>"
6.  Cross-check in Seed Tool          seedtool-2.3.0.html
7.  Derive addresses in Seed Tool     ← compare against your wallet after import
```

Steps 2 and 4 need no computer at all. Steps 3 and 5 take seconds — do them on an
air-gapped machine, ideally twice on two different machines.

Step 7 is what proves the wallet actually used *your* seed rather than quietly
substituting its own: import the phrase, then check the wallet's first receive
address matches what Seed Tool derived offline.

**Cross-check at the binary level, not the dice level.** Tools disagree about
which die face maps to zero, so feed the same 256 entropy bits to both `bip39.py`
and Seed Tool and require identical words. A mismatch means a convention
difference to resolve *before* trusting either.

---

## Commands

```
./bip39.py roll d16 500              interactive: roll, type, repeat, then test
./bip39.py test d16 3 7 1 16 ...     same test, rolls given on the command line
./bip39.py dice d16d8                show the roll plan
./bip39.py dice d16d8 5 12 3 ...     70 numbers (d8 first in each triple) -> phrase
./bip39.py final "<23 words>"        the 8 valid final words
./bip39.py verify "<24 words>"       checksum check
./bip39.py table d16d8               regenerate the lookup table (4 cols, 9 pages)
./bip39.py table d16d8 --cols 3      3 columns instead (12 pages, narrower)
./bip39.py coins HHTHTTHTHHT ...     eleven coins per word, von Neumann whitened
./bip39.py coins --raw ...           skip whitening
./bip39.py audit somelist.txt        compare a wordlist against the standard
./bip39.py gen                       CSPRNG seed (testing only, NOT for funds)
```

Add `--12` for a 12-word phrase. All modes are pure standard library — no
installs, no network.

Other dice modes: `d8d4`, `d16d8d4`, `d8d4coin`, `coin`, `d6`, `d16x3`, `d8x4`, `d4x6`.

---

## Testing your dice

```
./bip39.py roll
```

Run it with no arguments and it walks you through the whole thing — asks what die
you have, works out what each roll count would actually buy you, and lets you
choose:

```
  How many sides does your die have? > 16

  Testing a d16. How thorough do you want to be?

     #   rolls     catches a    catches a    approx
                 doubled face    +50% face      time
     1      80          19%           8%       5 min   bare minimum -- test only just valid
     2     406          85%          25%      27 min   catches a badly defective die
     3     712          99%          45%      47 min   near-certain on a doubled face
     4    1529         100%          85%     102 min   catches subtle bias too

  Pick 1-4, or type any roll count you prefer.
  How many rolls? [2] >
```

Option 2 is the sensible default. Skip ahead with `./bip39.py roll d16` (menu
only) or `./bip39.py roll d16 406` (straight to rolling).

**Bigger dice need MORE rolls, not fewer** — the opposite of what intuition
suggests. A d6 reaches "catches a defective die" in 141 rolls; a d16 needs 406.
Spreading the same rolls over more faces thins out each count, and the extra
degrees of freedom raise the bar again:

| die | minimum valid | catches a doubled face | catches a +50% face |
|---|---|---|---|
| d4 | 20 | 101 | 330 |
| d6 | 30 | 141 | 486 |
| d8 | 40 | 187 | 664 |
| **d16** | 80 | **406** | 1529 |
| d20 | 100 | 535 | 2037 |

Then it prompts for each roll, counts down what's left, and runs the test when
you finish:

```
  [  47/500]   453 left > 12
  [  48/500]   452 left > 3 9 16      <- several at once is fine
  [  51/500]   449 left > u           <- undo the last one
```

Every entry is written immediately to `dice-log-d16.txt`, so a crash or a closed
terminal costs you nothing — rerun the same command and it offers to resume.
Type `q` to stop early and test what you have.

Running face counts are deliberately **not** shown while you collect. Seeing that
a face is "behind" nudges how you throw, and that dependence is precisely what
the test is supposed to catch.

Reports a chi-square goodness-of-fit test, flags outlier faces, and checks whether
consecutive rolls look dependent (which catches lazy rolling, not bad dice).
`./bip39.py test d16 <rolls...>` does the same on rolls you already have.

**Why the menu matters.** 5×sides makes the test statistically *valid* — it does
not make it *sensitive*. At the bare minimum of 80 rolls, a d16 with one face
coming up twice as often gets caught less than one time in five. The numbers come
from a non-central chi-square power calculation, cross-checked against direct
simulation and carrying a 10% safety margin, since an under-powered test that
looks adequate is the failure worth avoiding.

**And the reassuring part** — bias small enough to escape detection costs almost
nothing, because entropy degrades gently:

| one face over-represented by | resulting seed strength |
|---|---|
| fair | 256 bits |
| +20% | 239 bits |
| +50% | 219 bits |
| +100% | 194 bits |

Even a grossly biased die leaves you far above the 128-bit security floor. The
test is there to catch a manufacturing defect, not to chase perfection.

Note: about **5% of perfectly fair dice fail at p<0.05 by chance.** Retest before
condemning one.

If a die tests badly and you want a mathematical guarantee instead of a
statistical one, use `coins` mode — von Neumann whitening produces provably
unbiased output from *any* biased source, as long as throws are independent. It
costs about twice the throws.

---

## Verification

`english.txt` is hash-checked on every run — `bip39.py` refuses to start if it
does not match:

```
2f5eed53a4727b4bf8880d8f3f199efc90e58503646d9ff8eff3a2ed3b24dbda  english.txt
```

<a name="seed-tool"></a>
### Seed Tool

A second, independent BIP39 implementation that also derives addresses — which is
what lets you confirm a wallet used *your* seed. Not bundled here; fetch it from
the author:

- Web version — <https://bitcoiner.guide/seed/>
- Source — <https://github.com/BitcoinQnA/seedtool>

```
# pinned to the version this README documents
curl -LO https://github.com/BitcoinQnA/seedtool/releases/download/2.3.0/index.html
curl -LO https://github.com/BitcoinQnA/seedtool/releases/download/2.3.0/signature.txt
curl -L -o key.asc https://github.com/BitcoinQnA/seedtool/raw/main/RELEASE-SIGNING-KEY.asc

sha256sum index.html
# eaac7484c1d579d0ffc70fb2e71e01e39a972aba940294b86e2a5187305573e9

gpg --import key.asc && gpg --verify signature.txt
# Good signature from "QnA <qna@bitcoiner.guide>"
```

Fingerprint: `EB3D 738B EC6A 873A C274 5292 CF4F E215 EA66 63AC`

**Confirm that fingerprint through an independent channel** — the bitcoiner.guide
site or QnA's public accounts — not only the repo the key came from. A key
fetched from the same place as the file it validates proves little.

Swap `2.3.0` for `latest` to get newer releases, but then the pinned hash above
will not match — verify by signature instead, since that works for any version.

**Audit notes on 2.3.0** (checked when this README was written): zero external
resource loads — no scripts, stylesheets or images fetched from anywhere. Its six
`eval` calls are library boilerplate (js-sha256's Node detection, the browserify
`vm` shim) plus two false positives from a method *named* `eval` in the Shamir
code. There is exactly one `fetch()`, a user-initiated DNS-over-HTTPS lookup for
name resolution — **don't use that feature**; air-gapped it cannot fire. Re-audit
any version you download yourself.

---

## The air-gapped machine

Removing the drive is worth more than any OS choice: a machine with no storage
medium cannot persist anything regardless of software intent.

- Used ThinkPad — service manuals published, WiFi is an M.2 card you unscrew
- **Remove: drive, WiFi card, WWAN card, Bluetooth module.** Cover camera and mic
- Boot Tails from a USB with a **physical write-protect switch**, flipped on
- Tails over plain Ubuntu here: it overwrites RAM on shutdown, Ubuntu doesn't
- Second USB for this kit. Verify hashes each session
- `lsblk` after boot to confirm no internal storage
- Full shutdown when done — never suspend
- **Handwrite the seed.** No printers (they have memory), no photos (phones have radios)

The USB is now your persistent artifact — everything you worried about on the SSD
applies to it. The write-protect switch is the hardware answer.

---

## Don't

- Type 23 words into any online "last word calculator" — with only 8 possibilities
  remaining, that hands over the whole seed
- Trust a wallet's acceptance as proof of good entropy — it only proves the
  checksum is right
- Use a shuffling machine as your randomness source; it's the same unauditable
  black box you're avoiding
- Use `gen` for real funds — that's the OS CSPRNG, which is the thing dice replace
- Assume the 8 final candidates are interchangeable — they're 8 different wallets

## If you help someone else

RAM-only protects against forensics. It does not protect them from **you**. If
you are in the room while their words are on screen, the seed passed through a
human who remembers things.

Hand over the kit and let them operate it, or leave the room for entry and reveal.
And if their coins ever move, you are the obvious suspect regardless of what
actually happened.

---

## Reference numbers

```
2048 words           = 2^11, so 11 bits per word
24 words             = 264 bits = 256 entropy + 8 checksum
23 words             = 253 bits; the last 3 entropy bits ride in word 24
70 throws            = 23 × (d8+d16+d16) + 1 final d8
8 candidates         for word 24, always
11.7%                of genuine 23-word draws repeat a word — repeats are normal
1 in 256             random orderings of 24 valid words passes the checksum
4 characters         uniquely identify every word in the list
```

---

## Credits and licences

- **BIP-0039** — the standard itself, and `english.txt`, from
  [bitcoin/bips](https://github.com/bitcoin/bips/tree/master/bip-0039).
- **[Seed Tool](https://github.com/BitcoinQnA/seedtool)** by BitcoinQnA
  (bitcoiner.guide) — GPL-3.0. Linked, not redistributed.
- **[iancoleman/bip39](https://github.com/iancoleman/bip39)** — MIT. The tool
  Seed Tool forked from, and the origin of the offline-single-file approach.
- **Bayer & Diaconis**, *Trailing the Dovetail Shuffle to its Lair* (1992) — the
  riffle-shuffle mixing results quoted in the card notes.

Everything else in this repository is original work, released under the **MIT
Licence** — see [LICENSE](LICENSE). `bip39.py` has no dependencies beyond the
Python standard library and makes no network calls.

Nothing here is financial advice, and the software carries no warranty. You are
generating keys that control real money; verify every step yourself, on hardware
you trust, before putting funds behind a seed.
