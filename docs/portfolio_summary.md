# bom-to-pcf: portfolio summary

**Automated product carbon footprints, from bill of materials to supplier data.**

Live app: link to be added after deployment · [Code](https://github.com/joenewton10/bom-to-pcf)

I built this tool to show how a cradle-to-gate product carbon footprint can be calculated from the data a
manufacturer already has, and how it can improve as suppliers send real data. The example is a die-cut PET
film part, based on the kind of precision converting work I see every day. All numbers are illustrative.

**What it does.** It cleans a SAP-style BOM export and checks the mass balance. It suggests an emission factor
for each material, and a person approves each one. It then calculates the footprint with its primary data
share and data quality rating, ranks which supplier to ask for data first, and creates the requests.
Incoming supplier PCFs are checked before they replace database values, with every change logged and
reversible. It also runs scenarios, Monte Carlo and a 36-variant product family, checks environmental claims
against EU rules, and exports a PACT file validated against the official schema.

**Method choices I can defend.** I checked the method against PACT Methodology 3.0 and the TfS PCF Guideline
3.0, and changed the tool where they disagreed with my first plan. For example, a site's metered electricity
multiplied by a database factor counts as 0% primary data, because both the activity data and the emission
factor must be primary. So the demo honestly starts at 0%. Where public data was missing, I built labelled
proxies, and the remaining gaps and differences from PACT are documented openly.

**Built with** Python, Streamlit, pydantic, pandas, Plotly and SQLite. It has 400+ automated tests, a
hand-calculated reference case and continuous integration on Python 3.11 and 3.14.

**Limits.** This is mock data and not a verified PCF. It shows method and workflow, not a real product's footprint.
