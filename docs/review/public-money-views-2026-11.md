# Ready-made views for the Public money topic: draft for Finance and Compliance review

**Status: approved and published 2026-11-05.** Francis answered "approved" and, asked what it covered, "Both, publish them": the Finance/Compliance approval of the wording and his approval of the set (HANDOFF decision 86). The views are in `dictionary_src/domains.json` as written below. This file keeps the draft as it was reviewed.

Prepared 2026-11-05 for Finance and Compliance review (decision 20: Spanish text about federal grant money is reviewed before it is published).

## Why these views wait

The Explore tab gives each topic two to four ready-made views (navigation plan PR 6, decision 81). Each view has a name and a short note in English and Spanish. A view also names its data sources. For Public money, the notes describe federal awards and FEMA funding, and the Spanish names terms that are held for review: obligation, federal share, Public Assistance, Individual Assistance and federal awards expended. The topic page therefore shows no views for Public money until this draft is approved. The Analysis tab's own "Public money" preset is unchanged.

## What is needed

- **Finance and Compliance:** approve or correct the English and Spanish names and notes below.
- **Francis:** approve the set of views (which datasets, how they are drawn).

Once both are approved, the views go into `dictionary_src/domains.json` (`presets` of `public-money`). `catalog.py` checks them, and `tests/presets.test.js` checks each dataset and scale against the engine.

## The draft views

The notes describe what each shading or circle shows. They state no conclusion (decision 72). Every dataset below is already on the map, with its own dictionary entry. "Per resident" is the scale `perCapita`, which each of these datasets offers.

### 1. Federal money per resident

- **Name:** "Federal money per resident" / "Fondos federales por residente"
- **Note (EN):** Shading: federal awards of all types per resident (USAspending). Circles: FEMA Public Assistance obligated (federal share).
- **Note (ES):** Sombreado: adjudicaciones federales de todo tipo por residente (USAspending). Círculos: Asistencia Pública de FEMA, fondos obligados (parte federal).
- **Shows:** `fed_awards_total` shaded per resident (`perCapita`); `fema_pa_obligated` as circles.
- This is the Analysis tab's "Public money" preset, as published today.

### 2. FEMA disaster funding

- **Name:** "FEMA disaster funding" / "Fondos de FEMA por desastres"
- **Note (EN):** Shading: FEMA Public Assistance obligated (federal share), per resident. Circles: FEMA Individual Assistance approved for households.
- **Note (ES):** Sombreado: Asistencia Pública de FEMA, fondos obligados (parte federal), por residente. Círculos: Asistencia Individual de FEMA aprobada para los hogares.
- **Shows:** `fema_pa_obligated` shaded per resident (`perCapita`); `fema_ia_amount` as circles.

### 3. Federal money the municipio government spent

- **Name:** "Federal money spent by the municipio government" / "Fondos federales gastados por el gobierno municipal"
- **Note (EN):** Shading: federal awards the municipio government reported as spent in its single audit, per resident (Federal Audit Clearinghouse).
- **Note (ES):** Sombreado: fondos federales gastados que el gobierno municipal informó en su auditoría única, por residente (Federal Audit Clearinghouse).
- **Shows:** `fac_expended` shaded per resident (`perCapita`).

## Points to check

- Each Spanish note above uses the Spanish of a held glossary term: obligation (fondos obligados), federal share (parte federal), Public Assistance (Asistencia Pública), Individual Assistance (Asistencia Individual), single audit (auditoría única) and federal awards expended (fondos federales gastados). The wording follows the glossary's Spanish for these terms, which is held for the same review.
- USAspending places an award where the agency says the work is done or the benefit goes (place of performance), so San Juan's figure can include money meant for the whole island. The dictionary entry of `fed_awards_total` says so; the view's note does not repeat it. Review whether view 1's note should.
- No view ranks municipalities or compares them with need. The Knowledge Area page "FEMA disaster funding and need" does that, with its own review.
