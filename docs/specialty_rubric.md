# Specialty rubric: which specialties are "highest referral volume and highest care cost"

Status: **design plus first-pass findings from web search snippets; no dataset downloaded yet.** The sandbox cannot reach any of these sources (see `docs/SETUP.md`). Tier 1 (dentists,
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

## Findings so far (web search snippets only: treat as leads, not facts)

Weights stay at 30 / 20 / 10 / 25 / 15 (you approved them). I cannot compute the weighted score yet because most inputs have no usable
number, so this is an evidence matrix. "n/a" means nothing found.

| Specialty | Referral rate (2009, % of visits with that symptom that led to a referral) | Cost evidence | Private-practice share (AMA 2024, national) | Provisional placement |
|---|---|---|---|---|
| Gastroenterology | 17.7% (highest of the four) | NJ colonoscopy cash price averages $4,398 across 29 hospitals, range $1,088-$28,805 (aggregator) | n/a | Tier 2 |
| Orthopaedic surgery | 16.5% | Commercial total cost of care $245B (Becker's 2023, source unclear); ~$9.8M billed per physician (AMN 2021); NJ knee replacement cash price averages $15,556 across 23 hospitals, range $4,570-$69,628 (aggregator) | n/a | Tier 2 |
| Cardiology | 14.9% | Medicare allowed charges $5.65B (CY2019); commercial total cost of care $104B; ~$3.4M billed per physician | **30.7%, lowest of all specialties**: most cardiologists are not in independent practice, so fewer reachable leads | Tier 2, with a local-fit warning |
| Dermatology | 15.4% | n/a | n/a | Tier 3 |
| Medical / hematology oncology | n/a | Commercial total cost of care $190B; highest Medicare payment per provider in 2012 data (inflated by Part B drugs) | n/a | Tier 3, first |
| Ophthalmology | n/a | Among the highest Medicare payment per provider (2012 data, drug-influenced) | **70.4%, highest of all specialties**: many independent practices to reach | Tier 3, strong local fit |
| Urology, neurology, pain medicine, OB/GYN | n/a | n/a | n/a | Tier 3, no evidence yet |

Sources: [referral rates, Barnett et al. 2012 summary](https://hcp.hms.harvard.edu/publication/trends-physician-referrals-united-states-1999-2009) ·
[MedPAC data book, fee-schedule spending](https://www.medpac.gov/wp-content/uploads/2025/07/July2025_MedPAC_DataBook_Sec7_SEC.pdf) ·
[CMS expenditures and services by specialty](https://www.cms.gov/data-research/statistics-trends-reports/medicare-fee-service-parts-b-utilization-reports/medicare-utilization-part-b/expenditures-services-specialty-reports) ·
[Medicare payments per provider, 2012](https://www.medicaleconomics.com/view/the-10-specialties-with-the-highest-medicare-part-b-payments) ·
[specialty billing to commercial payers](https://beckershospitalreview.com/finance/15-specialties-ranked-by-billings-to-commercial-payers.html) ·
[AMA Physician Practice Benchmark Survey](https://www.ama-assn.org/about-ama/research/physician-practice-benchmark-survey) ·
[NJ colonoscopy prices](https://mycarecost.com/colonoscopy-cost/new-jersey) · [NJ knee replacement prices](https://mycarecost.com/knee-replacement-cost/new-jersey)

Caveats that matter:
- The referral rates measure the share of visits with a symptom that ended in a referral, not how many referrals each specialty receives.
- Medicare per-provider figures are from 2012-2013 and differ by measure; drug payments inflate oncology and ophthalmology.
- The commercial cost-of-care table has no stated data source; the NJ price figures come from a commercial aggregator and include implausible entries.
- A specialty can be expensive and still be a poor lead pool. Cardiology is the clear case: only 30.7% of cardiologists are in private practice.
- AMA figures are national. No New Jersey breakdown was found.

## Pharmacy data (as data, per your answer)

- **Medicare Part D Pharmacy Network and Pricing files** (CMS, free): every network pharmacy with its NPI, preferred / retail / mail-order flags, and plan drug
  prices (pricing excludes discounts). Large files, monthly or quarterly. Also a possible source of independent pharmacies later.
- **NADAC** (weekly acquisition cost per drug unit): what pharmacies pay, not what patients pay.
- **Cost Plus Drugs:** I found no downloadable price list; descriptions of its fee structure disagree. Check its own site.
- Retail pharmacies do not publish a standard price list, so patient-facing pharmacy prices need a separate source (not found yet).

## Next steps once the sandbox can download

1. CMS "Expenditures and Services by Specialty" CY2022/CY2023 XLSX and the by-Provider file: replace the Medicare numbers above with current totals and per-provider averages.
2. NJ hospital price files for GI, orthopaedic and cardiology codes (colonoscopy, joint replacement, echocardiogram, catheterisation).
3. AMA state-level tables, if obtainable, otherwise estimate private-practice share from NPPES sole-proprietor flags.
