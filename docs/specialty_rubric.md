# Specialty rubric: which specialties are "highest referral volume and highest care cost"

Status: **design only, no data pulled yet.** The sandbox cannot reach any of these sources (see `docs/SETUP.md`). Tier 1 (dentists,
physical therapists, mental health, primary care) is fixed by you. This rubric ranks the candidates for tiers 2 and 3.

## Inputs, in order of weight

| # | Input | Public source | What it measures | Weight |
|---|---|---|---|---|
| 1 | Medicare spend by specialty | CMS [Medicare Physician & Other Practitioners - by Provider](https://catalog.data.gov/dataset/medicare-physician-other-practitioners-by-provider) (per NPI: allowed amount, payment, standardized payment, with medical vs drug sub-totals; [methodology](https://data.cms.gov/sites/default/files/2025-04/MUP_PHY_RY25_202350312_Methodology_508.pdf)). Cross-check: CMS PHYSSUPP 6 table (allowed charges by specialty) | Total and per-provider Medicare dollars | 30% |
| 2 | Hospital prices | Each hospital's machine-readable file under [45 CFR Part 180](https://www.cov.com/-/media/files/corporate/publications/2019/11/cms-releases-final-hospital-price-transparency-rule-and-proposes-transparency-rule-for-health-plans.pdf): gross charge, discounted cash price, payer-specific negotiated rates, de-identified min/max, for 300+ shoppable services | What commercial payers and cash patients pay for procedures a specialty drives (e.g. colonoscopy, echocardiogram, joint replacement) | 20% |
| 3 | Drug cost | Medicare drug-type sub-totals from input 1, plus [NADAC](https://catalog.data.gov/dataset/nadac-national-average-drug-acquisition-cost-2025) (weekly average pharmacy acquisition cost per unit; CSVs on `download.medicaid.gov`) | Specialties whose care is drug-heavy (oncology, rheumatology, ophthalmology injectables) | 10% |
| 4 | Referral volume | Published studies: GI, orthopaedic and cardiovascular complaints are among the most common reasons for specialist referral ([Ontario study](https://pmc.ncbi.nlm.nih.gov/articles/PMC5567435); small samples) | How often primary care sends patients to the specialty | 25% |
| 5 | Local fit | Computed from your own pulls: share of NJ providers that are sole proprietors (NPPES) and share with a confirmed web-presence gap (Places) | Whether the specialty has reachable, underserved practices | 15% |

Each input is converted to a percentile rank across specialties (0-100), weighted, and summed. Top quartile = tier 2, next quartile = tier 3.
Weights are my starting guess; change them in this file.

## Clinics and pharmacies: what I found

- **Independent clinics:** I found no federal or New Jersey rule requiring a practice to post a self-pay price list. Practices must give
  uninsured and self-pay patients a **Good Faith Estimate** when a service is scheduled at least three days ahead (No Surprises Act; patients
  can dispute a bill $400 or more above it). So clinic prices exist only as the few practices that choose to publish a menu. Use them as a
  sample and as a signal that a practice is open about pricing, **not** as a ranking input. Verify against the NJ Department of Health and
  Department of Banking and Insurance.
- **Pharmacies:** retail pharmacies do not publish a price list. NADAC is the best public proxy (what pharmacies pay, not what patients pay).

## What I need to run it

Network access to `data.cms.gov`, `www.cms.gov`, `download.medicaid.gov`, plus each NJ hospital's website for its price file (or you
download the files and put them in the repo / Google Drive). Hospital files are large and inconsistent: expect a data-cleaning step per hospital.

## Not established

- Exact column names in the by-Provider file (search results did not show them; check the data dictionary before coding).
- Whether the 2025-2026 hospital price file fields are all in force (compliance dates ran from 2024 to 2025 per secondary sources; check CMS).
- Commercial (non-Medicare) cost by specialty. Hospital files are the only public proxy and are noisy.
