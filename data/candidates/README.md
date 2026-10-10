# Candidate lists (kept private)

The lead lists for named practices are not stored in the public version of this repo. `tools/run_lists.py` and `tools/build_review.py` read CSV files in this folder,
named `<segment>_practices.csv` and `<segment>_individuals.csv` (segments: cardiology, ophthalmology, pt, dentist, mental_health, primary_care).

Columns: `practice, specialty, city, address, phone, priority, evidence, source, providers, size_override, review, check, kind, segment, subspecialty, size_basis`.
`kind` is `practice` or `individual`; `priority` is 1-3; `size_override` is Solo/Small/Medium/Large or blank; `size_basis` starts with Evidence or Suspected.
The CSV files here are git-ignored so they cannot be committed by accident.
