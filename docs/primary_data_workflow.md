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
refuse a save or restore that would remove or change saved history.

The progress file also holds the review decisions and review log.

## Limits

- A supplier PCF counts in full towards the primary data share, even if the supplier reports that only
  part of its own footprint is primary. The supplier's figure is stored but not yet used in that share.
- A record's DQR is used for all three dimensions, because the form takes one score.
- Each material has one value in use, so buying one material from several suppliers is not modelled.
- Using the local app in two browser tabs at once is not supported: the second tab's save is refused
  rather than overwriting the first tab's history.
- Restoring into a local database with different saved history is refused. To start again, move or
  delete `data/app.db`.
