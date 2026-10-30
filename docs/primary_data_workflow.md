# Primary data workflow

The footprint starts on database values and improves as supplier data arrives. Every change is
checked, can be traced and can be undone.

## Checks before a supplier PCF is used

| Check | If it fails |
|---|---|
| The material is in the BOM, from the supplier the BOM names | Rejected |
| The value is above zero and the declared unit converts to kg | Rejected |
| The reference period ended no more than 3 years before the reference date | Rejected |
| A method is stated | Rejected |
| The boundary is cradle-to-gate | Rejected |
| DQR is 1 to 5 and primary share is 0 to 1, if given | Rejected |
| The value is 0.2× to 5× the database value | Needs a reviewer comment |
| There is a database value to compare with | Needs a reviewer comment |

All problems are reported together. A rejected submission leaves the current value in use, and it is
kept with its reasons. The limits are in `config/method.yaml` and `config/product_pet_diecut.yaml`.

Records in an uploaded `supplier_pcf.json` go through the same checks, under the user `file import`.
A record that needs a comment is rejected there and can be entered again by hand with one.

## Replacing and undoing

An accepted PCF becomes a new version, and it replaces all the factors mapped to that material.
Nothing is ever deleted. Undo moves the material back to an earlier version or to the database value,
so the result returns to exactly what it was, and the move itself is logged.

Each inventory line using supplier data traces to its version (`supplier_pcf:V0001`).

## Audit trail

`timestamp, user, material, supplier, field, old_value, new_value, reason, version_id`

Each accepted change logs the fields that differ. Rejections and undos are logged too. The user name
is typed in and not verified, because the app has no logins.

## Storage

| Where the app runs | Backend | What happens |
|---|---|---|
| On your own computer | `SQLiteStore`, `data/app.db` | Work is kept between sessions. Database triggers block changes to history |
| Anywhere else, such as Streamlit Community Cloud | `SessionStore` | Work lasts for the session. Download your progress and upload it next time |

The app picks the backend from the address it is being visited on, so a visitor to a shared host can
never write to a shared file. `BOM_TO_PCF_STORAGE=sqlite` or `session` overrides this. Both backends
refuse a save or restore that would remove or change saved history. Start fresh is the deliberate
exception, described below.

The progress file also holds the review decisions and review log.

## Primary data share

| Part of the footprint | How much counts as primary |
|---|---|
| Supplier PCF with a stated primary share | That share of its impact |
| Supplier PCF with no stated share | None, reported separately as unknown |
| Site quantities with a database factor | None |
| Database values | None |

An input is primary only if both its activity data and its emission factor are (PACT Methodology 3.0,
section 4.2.2; TfS PCF Guideline 3.0, section 5.2.11.1). See [methodology.md](methodology.md).

## Starting again

Start fresh is at the bottom of the Primary data page. Locally it moves `data/app.db` to
`data/app-archive-<date>.db`, so no history is destroyed. When hosted it clears the session.

## Limits

- A record's DQR is used for all three dimensions, because the form takes one score.
- Each material has one value in use, so buying one material from several suppliers is not modelled.
- Two tabs stay in step because the app re-reads saved data on every page run. If two saves collide at
  the same instant, the later one is refused with a message, and history is not overwritten.
- Restoring into a local database with different saved history is refused. To start again, move or
  delete `data/app.db`.
