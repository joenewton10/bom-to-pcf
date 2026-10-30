# Environmental claims check

**This is a guidance aid, not legal advice.** It checks wording against simple rules, and it cannot
judge whether a real claim is lawful. All results here are illustrative and should not support real
claims.

## How a claim is checked

Rules are in `config/claims_rules.yaml` and run in this order.

| Order | Verdict | When | Basis |
|---|---|---|---|
| 1 | ❌ Not supported | Offset-based claims such as "climate neutral" or "net zero" | Directive (EU) 2024/825, Annex I point 4c, and recital 12 |
| 2 | ❌ Not supported | Generic claims such as "eco-friendly", "green" or "sustainable" | Annex I point 4a, and recital 9 |
| 3 | ❌ Blocked | Any other claim while the result is a draft | This tool's rule |
| 4 | ⚠️ Needs more | Comparisons, such as "20% lower than" | This tool's rule: needs a documented benchmark with the same boundary and method |
| 5 | ⚠️ Needs more | Claims about one aspect, such as "made with recycled PET" | Annex I point 4b |
| 6 | ✅ Supported | A figure matching this result, with its boundary and ISO 14067 | Specific claims are not generic, recital 9 |
| 7 | ⚠️ Needs more | Anything else, which goes to a person | This tool's rule |

Banned wording is reported ahead of draft status, because resolving the draft would not make it allowable.

## The legal basis, as checked

Read directly from the [Official Journal text of Directive (EU) 2024/825](https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=OJ:L_202400825) on 2026-10-30.

- **In force:** Member States had to apply it from 27 September 2026.
- **Point 4a** bans a generic environmental claim where the trader cannot demonstrate recognised excellent
  environmental performance relevant to the claim.
- **Point 4b** bans a claim about the entire product when it concerns only a certain aspect.
- **Point 4c** bans claiming, based on offsetting, that a product has a neutral, reduced or positive
  greenhouse gas impact.

**It amends business-to-consumer law.** Directive 2005/29/EC covers unfair business-to-consumer practices. A
die-cut insulation part is usually sold between businesses, so the directive may not apply directly. The
tool applies its rules anyway, as a sensible standard. This question needs a lawyer for any real product.

**Member State rules differ.** This is the directive, not any national law transposing it.

## The Green Claims Directive

The Commission's proposal, COM(2023) 166, is not law. The Commission announced in June 2025 that it intended
to withdraw it, and later said it had not formally done so. Secondary sources checked on 2026-10-30 disagree
on whether it is now withdrawn or blocked, and the Parliament's tracker page could not be opened. These rules
do not rely on it.

## What it cannot do

- It reads wording only. It does not see images or context, which can also make a claim misleading.
- A pattern can miss a claim or catch one wrongly, so unrecognised claims go to a person.
- "Supported" means the figure matches this tool's result. It does not mean the claim is lawful.
