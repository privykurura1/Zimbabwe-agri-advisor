# ADTC Agri Advisor — Starter Knowledge Corpus (Zimbabwe)

Each entry below is written as a self-contained retrieval chunk: a farmer-facing
problem, grounded facts, and a recommended action. Use each `###` block as one
RAG document/chunk. Expand each entry with more detail and more entries before
submission — this is a scaffold, not a finished corpus.

---

## SECTION A: Natural Regions Reference (context for all advice)

### A1. Zimbabwe's Five Natural Regions (agro-ecological zones)
Zimbabwe is divided into five Natural Regions (NR I–V) based mainly on rainfall,
used as the basis for what crops/livestock systems are viable where.

- **NR I** (~2% of land, Eastern Highlands): >1,000mm rain/year, cool, high altitude.
  Suited to tea, coffee, deciduous fruit, dairy, intensive livestock, forestry.
- **NR II** (~19% of land, Mashonaland provinces, Harare): 700–1,050mm rain/year,
  Zimbabwe's main "breadbasket." Suited to maize, flue-cured tobacco, cotton,
  groundnuts, soybean, sugar beans, mixed cattle/poultry farming.
- **NR III** (~17% of land): 500–800mm rain/year, frequent mid-season dry spells.
  Semi-intensive: livestock plus drought-tolerant cash crops, sorghum, some maize.
- **NR IV** (~33–38% of land, largest region, north/south lowveld, most of
  Matabeleland): 450–650mm rain/year, unreliable, periodic drought. Semi-extensive
  livestock, drought-resistant crops (sorghum, millet) — largest communal farming
  population.
- **NR V** (driest, southern lowveld bordering Botswana/SA/Mozambique): <450mm/year.
  Extensive cattle/game ranching only; cropping unreliable without irrigation.

**Why this matters for advisory answers:** always ask or infer the farmer's
region before giving planting-date or crop-choice advice — a maize recommendation
correct for NR II can be a bad recommendation in NR IV or V.

---

## SECTION B: Cattle — Tick-Borne Diseases
Tick-borne diseases (TBDs) account for roughly 20–30% of recorded cattle deaths
annually in Zimbabwe and are the single biggest livestock health issue for
smallholder/communal farmers, who own over 80% of the national herd.

### B1. Theileriosis ("January Disease")
- **Cause:** Theileria parva, transmitted by the brown ear tick (Rhipicephalus
  appendiculatus).
- **When:** Peaks December–March (hot wet season) when tick populations are highest.
- **Symptoms:** High fever, swollen lymph nodes (especially near the ear/jaw),
  laboured breathing, discharge from eyes/nose, loss of appetite, rapid decline.
- **Action:** This is the deadliest TBD in Zimbabwe currently — treat as an
  emergency. Isolate the animal, contact a veterinary officer or dip tank
  attendant immediately. Do not wait to see if it improves.
- **Prevention:** Strict adherence to the dipping calendar (weekly dipping is
  recommended from November as tick season begins); intensify around Dec–Mar.

### B2. Anaplasmosis ("Gallsickness")
- **Cause:** Anaplasma marginale (and less severe A. centrale) bacteria, tick-
  transmitted, affects cattle, sheep, and goats.
- **Symptoms:** Fever, pale or yellowish gums/mucous membranes (anaemia,
  jaundice), weakness, reduced appetite, sometimes dark urine.
- **Action:** Contact a vet for treatment options available locally. Recovered
  animals remain lifelong carriers and can still trigger new outbreaks in the herd.
- **Note:** Indigenous (Bos indicus) breeds are more resistant than exotic
  (Bos taurus) breeds. Calves under 6 months have natural innate resistance.

### B3. Babesiosis ("Redwater")
- **Cause:** Babesia bigemina / Babesia bovis, tick-transmitted (Boophilus/
  Rhipicephalus ticks).
- **Symptoms:** Fever, red-brown/"redwater" urine (blood in urine), anaemia,
  weakness, loss of appetite.
- **Action:** Veterinary treatment needed promptly — can be fatal if untreated.

### B4. Heartwater (Cowdriosis)
- **Cause:** Ehrlichia ruminantium, transmitted by the bont tick (Amblyomma).
  Affects cattle, sheep, and goats — goats and sheep more susceptible than cattle.
- **Symptoms:** High fever, nervous signs (circling, muscle tremors, pushing
  head against objects, aggression or anxious behaviour), can progress rapidly
  to death — mortality up to 90% in susceptible animals if untreated.
- **Action:** Veterinary emergency — nervous signs plus fever in a ruminant is a
  strong heartwater indicator; seek treatment immediately.

### B5. General tick control guidance (applies across B1–B4)
- Communal dip tanks (government-run, ~4,000 nationally) are the primary control
  method — attend scheduled dipping without gaps.
- Increase dipping frequency to weekly at the start of the hot wet season
  (~November) to interrupt the tick breeding cycle before peak season.
- Cost is a real barrier for smallholders (~US$2/animal/year dipping fee); do not
  assume the farmer can afford intensive chemical control — mention lower-cost
  or community-pooled options if known.

---

## SECTION C: Poultry — Common Diseases
Backyard/smallholder poultry surveys in Zimbabwe found Infectious Bronchitis in
85% and Newcastle Disease in 27% of tested flocks — ND's lower detection rate
is partly because it kills so fast that fewer infected birds survive to be
sampled. In tropical Africa generally, Newcastle Disease causes over 70%
mortality in unvaccinated village flocks when it strikes, making it the most
economically significant poultry disease across the region.

### C1. Newcastle Disease (ND)
- **Cause:** A highly contagious paramyxovirus. Spreads rapidly — often
  90-100% of a flock infected within days of introduction.
- **Symptoms:** Variable, but commonly: respiratory distress (gasping,
  coughing), greenish watery diarrhea, drop in egg production and/or
  thin-shelled misshapen eggs, and in later stages nervous signs (twisted
  neck/head, paralysis, tremors). Sudden deaths with few warning signs are
  common in unvaccinated flocks.
- **Action:** No effective treatment once infected — focus is prevention.
  If ND is suspected, isolate the flock immediately, avoid moving birds
  on/off the property, and contact a veterinary/extension officer, since
  ND is a reportable disease. Routine vaccination (e.g. I-2 vaccine, heat
  stable and suited to village conditions without a strict cold chain) is
  the primary effective control — studies show vaccinated flocks have
  dramatically higher survival and egg production than unvaccinated ones.

### C2. Infectious Bronchitis (IB)
- **Cause:** A coronavirus affecting the respiratory tract; found to be the
  single most common disease detected in Zimbabwean backyard flock testing.
- **Symptoms:** Coughing, sneezing, nasal discharge, watery eyes, reduced
  egg production, and in laying birds, misshapen or poor-quality eggshells.
  Generally lower mortality than ND but can be severe in young chicks.
- **Action:** No specific cure — supportive care (warmth, reduce stress,
  ensure access to water) while the flock recovers. Watch closely for
  secondary bacterial infections. Vaccination is available and effective
  where accessible.

### C3. Coccidiosis
- **Cause:** Protozoan parasite (Eimeria species), spread via droppings —
  thrives in damp, dirty litter conditions.
- **Symptoms:** Bloody or watery diarrhea, ruffled feathers, lethargy,
  pale comb/wattles (anemia), reduced growth in young birds, huddling.
  Birds under 10-14 days old are generally not yet susceptible; risk rises
  as chicks start actively pecking at litter.
- **Action:** Keep litter dry and clean — this is the single most effective
  prevention measure. Anticoccidial treatment is available and effective if
  caught early; consult an animal health worker for dosing since untreated
  outbreaks can cause high mortality in young birds.

### C4. Fowl Typhoid / Pullorum Disease
- **Cause:** Salmonella bacteria (S. Gallinarum for fowl typhoid, S.
  Pullorum for pullorum disease) — closely related, similar presentation.
- **Symptoms:** In young chicks: diarrhea, weakness, high mortality. In
  adult birds (fowl typhoid specifically): depression, pale comb, reduced
  appetite, greenish-yellow diarrhea, sudden deaths.
- **Action:** Treatment is generally not recommended even if birds survive,
  since survivors often become lifelong carriers and can silently infect
  future generations of the flock through eggs. Prevention is the priority
  — source new birds from a clean, disease-tested flock where possible, and
  isolate/cull affected birds to protect the rest of the flock.

### C5. General smallholder poultry biosecurity (applies across C1–C4)
- Isolate any new or sick birds before introducing them to the flock.
- Keep housing dry, well-ventilated, and litter clean — this alone reduces
  risk of coccidiosis and limits secondary infections riding on top of
  viral disease.
- Limit contact with wild birds and control rodents/pests around housing.
- Because veterinary access is often limited in rural areas, prevention
  (vaccination where available, biosecurity, clean housing) matters more
  than treatment — most of these diseases have no reliable cure once
  established in the flock.

---

## SECTION E: Goats & Sheep — Common Diseases

### E1. Gastrointestinal Parasites (Haemonchus, Eimeria)
- **Cause:** Haemonchus contortus (a blood-feeding stomach worm) and Eimeria
  (coccidia) are the two most common internal parasites found in Zimbabwean
  goats. A study across all five of Zimbabwe's Natural Regions found high
  rates of both, with the highest risk in NR I, II, and III, and infection
  peaking in the wet season.
- **Symptoms — Haemonchus:** pale gums/inner eyelids (anemia, since this
  parasite feeds on blood), weakness, swelling under the jaw ("bottle jaw"),
  weight loss. Diarrhea is usually NOT a Haemonchus symptom on its own — if
  diarrhea is present, suspect a mixed infection with another parasite type.
- **Symptoms — Eimeria (coccidiosis in goats):** watery or bloody diarrhea,
  poor growth, dehydration, most severe in young kids.
- **Who's most at risk:** young animals are consistently the most
  susceptible in both parasites; risk is highest during the wet season.
- **Action:** Check inner eyelid/gum color regularly as a simple anemia
  screen (pale = concern, especially combined with weakness or jaw
  swelling). Deworming treatment is effective but growing parasite
  resistance to common dewormers is a recognized regional problem — rotate
  treatment types where possible and consult an animal health worker rather
  than treating repeatedly with the same product if it stops working.
  Keeping animals off heavily grazed, wet pasture reduces reinfection risk.

### E2. Heartwater in Goats and Sheep
- Goats and sheep are generally MORE susceptible to heartwater than cattle
  (see Section B4 for full disease detail — same tick-borne cause, same
  urgent nervous-sign symptoms: fever, circling, tremors, pushing against
  objects). Because small ruminants can decline faster than cattle with this
  disease, any goat or sheep showing fever plus nervous signs should be
  treated as an even more time-critical emergency — seek veterinary help
  immediately, do not wait to see if it resolves.

### E3. Peste des Petits Ruminants (PPR) — Regional Awareness
- **Cause:** A highly contagious viral disease of goats and sheep
  (related to the now-eradicated rinderpest virus), with mortality that can
  reach 90% in unprotected herds where it is established.
- **Status:** PPR is established and actively monitored in parts of East,
  Central, and West Africa. Its presence specifically within Zimbabwe is
  not well established in available surveillance data as of this writing —
  farmers should be aware of it as a regional risk rather than treat it as
  confirmed locally present. If in doubt, defer to current guidance from
  the Department of Veterinary Services.
- **Symptoms:** high fever, discharge from eyes/nose, mouth sores/erosions,
  diarrhea, pneumonia (coughing) — sudden death is possible in young kids
  especially.
- **Action:** Because of its severity and reportable status where confirmed,
  any goat/sheep flock showing this symptom combination should be isolated
  immediately and reported to a veterinary officer rather than treated
  informally.

### E4. General smallholder goat/sheep husbandry (applies across E1–E3)
- Check young animals more frequently than adults — they are consistently
  the highest-risk group across the parasites and diseases above.
- Avoid grazing on the same wet, low-lying pasture repeatedly during rainy
  season, since this is where parasite larvae concentrate.
- Isolate any newly acquired or visibly sick animal before mixing it with
  the rest of the herd/flock.

---

## SECTION D: Crops

### D1. Maize — Fall Armyworm
- **Cause:** Spodoptera frugiperda, an invasive pest first confirmed in
  Zimbabwe/Southern Africa around 2016–2017, now endemic and a major recurring
  threat to maize.
- **Symptoms:** Ragged holes in leaves, "windowpaning" on young leaves, frass
  (caterpillar droppings) visible in the whorl, damaged growing point.
- **Action:** Scout fields regularly from emergence; early detection is critical.
  Recommend integrated management (approved pesticides, timing sprays for early
  larval stages, and where relevant, biological/cultural controls) — advise
  farmer to confirm current approved chemical options with local extension, as
  registered products change.

### D2. Maize/Tobacco/Groundnuts — Planting Windows by Region
- **NR I/II:** Main maize/tobacco planting window is with the onset of the
  rains, typically mid-October to November, timed to soil moisture rather than
  a fixed calendar date.
- **NR III–V:** Farmers should prioritise short-season, drought-tolerant
  varieties; planting should follow confirmed rainfall onset rather than
  calendar date, given erratic rains in these regions.
- **Caveat for the model:** Do not give a fixed calendar date as a hard rule —
  actual planting should follow rainfall onset, which varies year to year. Frame
  advice as "typical window is X, but wait for reliable rains before planting."

### D3. Tobacco — Zimbabwe context
- Zimbabwe's second-largest foreign currency earner after gold; flue-cured
  tobacco grown mainly in NR II.
- Curing is heavily firewood-dependent in smallholder systems, a known
  deforestation driver — if a farmer asks about curing, this is worth
  flagging alongside technical curing advice.