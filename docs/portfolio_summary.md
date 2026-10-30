# bom-to-pcf: portfolio summary

Live app: [bom-to-pcf.streamlit.app](https://bom-to-pcf.streamlit.app/) · [Code](https://github.com/joenewton10/bom-to-pcf)

Most of what you need for a product carbon footprint already exists in a manufacturer's systems: the bill of
materials, the routing, the energy use. What's missing is a repeatable way to turn that into a number you can
defend. I built this tool to try that, using a die-cut PET film part, the kind of precision converting work I
see every day. The numbers are illustrative. The method is the part I care about.

You start with a mock SAP export. The tool cleans it up, checks the mass balance and suggests an emission factor
for each material, but a person has to approve each match before the result stops being a draft. It then ranks
which supplier to ask for data first and writes the request. When a supplier PCF comes in, it gets checked before
it replaces the database value, and every swap is logged and can be undone. There's also a scenario and Monte
Carlo view, a 36-variant product family, a claims check against EU rules, and a PACT export validated against the
official schema.

The decision I'd most like to talk about is the demo's primary data share, which is 0%. My first version counted
metered site electricity as primary and showed 21%. Then I read PACT 3.0 and the TfS guideline properly. Both say
an input is only primary if the activity data and the emission factor are, and a grid factor from a database
isn't. So I changed it. A lower number I can defend beats a higher one I can't, and it also shows why supplier
data matters.

Some of this is still weak, and the repo says so. Two factors are proxies I built because I couldn't find public
data, the PET resin figure is from the US, and the sources don't share one GWP basis. The full list is in
[data_gaps.md](data_gaps.md).

It's written in Python with Streamlit, pydantic, pandas, Plotly and SQLite. There are 400+ tests, including a
hand-calculated reference case, and CI runs on Python 3.11 and 3.14. This is mock data and not a verified PCF.
