# Numbered draw tabs (0000–2047)

2048 printable tabs, one per BIP39 word index. Draw one from a bag, look the
number up on the wordlist page, write the word down, **put the tab back**, mix,
repeat 23 times.

> **Read the caveat before printing 60 hours of plastic.** A 2048-object bag is
> the one randomizer in this kit you cannot test — verifying its uniformity would
> take roughly 10,000 draws and you only make 23 per seed. Dice are testable in a
> few hundred rolls and remain the recommended method. See the main README.
> These exist because a physical draw is a method people will actually use.

---

## What's here

| file | |
|---|---|
| `tabs-plate-01.3mf` … `tabs-plate-15.3mf` | 144 tabs each (last one has 32) |
| `manifest.csv` | which number is on which plate and slot, sorted by number |
| `make-tabs.py` | regenerates everything; edit the constants at the top |

Each plate contains **two bodies**: `base` (the discs) and `digits` (the numerals,
occupying only the top 0.6 mm). Same geometry, two filaments.

---

## Printing on a Bambu P1S

Plates are **228 × 228 mm**, sized to leave ~14 mm margin on the 256 × 256 bed.

1. **Import** `tabs-plate-01.3mf`. Two objects appear at identical coordinates,
   named `base` and `digits`.
2. **Select both, then Assemble them into a single object.** They become two
   parts that move together.
3. Assign the **`digits`** part to your second filament.
4. Slice at **0.2 mm layer height**, 0.4 mm nozzle, **100 % infill**.
5. No supports. Brim only if you get lifting.

The 3MF is deliberately plain — no embedded materials or colour metadata, since
that is the least portable corner of the format and slicers disagree about it.
Assigning two filaments by hand is one click and always works.

### If the 3MF won't import

Generate STLs instead. They are not committed here because binary STL is roughly
eight times the size of the compressed 3MF (~37 MB for the full set), but the
generator will write them on demand:

```
./make-tabs.py --stl          # every plate, 3MF + two STLs each
./make-tabs.py 1 --stl        # just plate 1
```

That gives `tabs-plate-01-base.stl` and `tabs-plate-01-digits.stl`. Import both,
**do not move either**, and assign the digits file to your second filament. They
share an origin, so they line up as long as nothing gets dragged or auto-arranged.

> ### ⚠️ Do not use Auto Arrange
> The two bodies are aligned by their coordinates, nothing else. Auto-arrange
> will move them independently and your digits will end up floating beside the
> discs instead of inside them. Assemble first (step 2), *then* arrange if you
> must.

**Layer height matters.** The colour region is 0.6 mm deep, which is exactly 3
layers at 0.2 mm and 4 at 0.15 mm. At 0.28 mm the boundary lands mid-layer and
the slicer will round it.

**Print plate 01 first and stop.** Check the digits are legible and the tabs
release cleanly before committing to the other fourteen.

### With an AMS

The swaps are automatic. Digits live in the top 3 layers, so expect roughly
**6 swaps per plate, ~90 for the whole run**, and around **56 g of purge**. Set
your flush volumes low if the two colours are close in tone.

### Without an AMS

Insert a filament-change pause at **1.4 mm** — that's where the digits start.
One pause per plate, swap colour, resume. The digits print entirely above that
height, so you never need to swap back.

---

## Cost of the full run

| | |
|---|---|
| tabs | 2048 across 15 plates |
| material | **~1.02 kg** PLA (0.50 g per tab) |
| plate | 144 tabs, ~72 g |
| time | **~60 hours** total, roughly 4 h per plate |

---

## Design notes

**Why a colour swap instead of embossed or engraved text.** Embossing adds
material and engraving removes it, so `1111` and `8888` end up with different
masses — about **1.6 % spread** across the set, and heavier tabs migrate
downward when you mix. A colour swap keeps the geometry *identical*: the only
difference is the density delta between two pigments, roughly 2 % of a much
smaller volume. Measured spread drops to **0.033 %**, about 0.2 mg on a 0.50 g
tab. That is ~50× more uniform, and it removes mass as a real objection.

**Why seven-segment digits and not a font.** Every segment is a plain rectangle,
so the enclosed areas in `0 4 6 8 9` are 1.4 mm rectangular gaps — 3.5 extrusions
wide, far too big to bridge over or fill in. A real typeface at 3 mm would give
you mushy counters and `8` indistinguishable from `0`. Strokes are 0.8 mm =
exactly two 0.4 mm extrusions, so they print as clean double walls on any slicer
rather than relying on variable-width extrusion.

**Why the numbering is shuffled across plates.** Print quality drifts over a
60-hour run — spool changes, nozzle wear, position on the plate, ambient
temperature. Tabs printed together are physically a cohort. If plate 1 held
0000–0143, that drift would line up with a contiguous block of the wordlist, and
any tendency of the bag to favour one cohort would favour one region of the
vocabulary. Shuffling decorrelates physical variation from index. The shuffle
uses a fixed seed, so the run is reproducible and auditable.

**Zero-based on purpose.** BIP39 indices run 0–2047, so the number on the tab is
the index you look up directly. Numbering 1–2048 would force a subtract-one on
every single draw.

---

## Using them

- **Draw with replacement.** Put each tab back and re-mix before the next draw.
  BIP39 slots are independent and **11.7 % of genuine 23-word draws repeat a
  word** — drawing without replacement makes repeats impossible, which no real
  seed guarantees.
- **Record the order.** Position matters entirely.
- **Mix mechanically, not by hand.** A sealed jar rolled on the floor, a bingo
  cage, anything that tumbles. Hand-shaking leaves whatever went in last near the
  top.
- **Tip one out; don't reach in.** After all that mixing, reaching into the
  container re-introduces exactly the bias the tumbling removed. Real lottery
  machines eject a ball — nobody reaches in.
- **Fix your protocol before you start.** "Roll for 30 seconds," decided in
  advance. Not "until it looks mixed" — your judgement of sufficiently-mixed
  drifts as you get impatient around draw 18.
- **You still cannot roll word 24.** Draw 23, then compute the eight valid final
  words and pick one with a d8. See the main README.
