# AI-assisted matching and expert validation

Matching a BOM description to an emission factor is a judgement call that changes the result. So
software proposes and a person decides.

## How a match is made

1. **Text matching always runs.** It compares each description with the terms in
   `data/mappings/candidates.yaml` and proposes the top 3, with a similarity score.
2. **AI is optional.** With an API key and the optional `anthropic` package, a reviewer can ask for a
   ranked suggestion with a rationale and confidence. It is off by default, and the session has a
   call limit (`config/matching.yaml`).
3. **A person decides.** Each material gets Approve, Reject or Choose other, with a comment.

The scores are for ranking. A high text score only means the words are similar, not that the factor
fits the material.

## What is sent to the AI

Only the BOM description, its unit and the candidate list (ID and label). No prices, supplier names,
material numbers, quantities or emission factor values are sent. A test checks this.

## What each decision does

| State | Effect on the result |
|---|---|
| Pending | The top suggestion is used provisionally, and the result stays in draft |
| Approve | The suggestion is used |
| Choose other | The reviewer's choice is used |
| Reject | No factor is used. The material is reported as a gap, and the result is a partial draft |

A final, non-draft result only ever uses approved matches. Provisional use exists so that a visitor
can see a footprint before reviewing, and the draft label stays until every material has a decision.

## Review log

Every decision is added to the log and earlier entries are never changed:
`timestamp, bom_item, suggestion, source, confidence, decision, chosen, reviewer, comment`.

`chosen` is an addition to the planned fields, recording the reviewer's own pick. The reviewer name is
typed in and not verified, because the app has no logins. The log lasts for the session and can be
downloaded. Lasting storage arrives with the primary data workflow.

## If the AI fails

A failed request, a refusal, a malformed answer or a candidate that does not exist are all ignored,
and the text match stays in place. Nothing depends on the AI being available.

## Limits

- Text matching is tuned on the terms in the candidate list, so new materials may match poorly. A low
  score is the signal to look harder.
- The AI path is tested against a simulated API, not the live service.
