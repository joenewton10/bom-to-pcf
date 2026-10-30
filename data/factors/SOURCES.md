# Emission factor sources

Every `source_id` in `emission_factors.csv` has a section here. All sources were accessed on
2026-10-30. "Checked in" says where the value was read.

## UBA_CC13_2025

Icha, P., Lauf, T. *Entwicklung der spezifischen Treibhausgas-Emissionen des deutschen Strommix in
den Jahren 1990 - 2024*. Climate Change 13/2025, Umweltbundesamt, 2025.
<https://www.umweltbundesamt.de/publikationen/entwicklung-der-spezifischen-treibhausgas-11>

Checked in: report, Table 1. A UBA web page has since revised direct CO2 for 2024 and added 2025,
but gives no value including upstream chains, so this report's figure is used.

## UBA_CC35_2021

Umweltbundesamt. Life cycle assessment of wind and photovoltaic power. Climate Change 35/2021.

Checked in: Energiezukunft's article on the study, not the study itself.
<https://www.energiezukunft.eu/erneuerbare-energien/solarenergie/aktuelle-oekobilanzen-von-wind-und-solarstrom>

## DESNZ_2025

UK Department for Energy Security and Net Zero. *Greenhouse gas reporting: conversion factors 2025*,
flat format. <https://www.gov.uk/government/publications/greenhouse-gas-reporting-conversion-factors-2025>

Checked in: flat file. Row IDs 1_100_1004_6_1, 11_100_1004_6_1, 27_304_3140_14_1, 28_907_3140_14_1.

## APR_2020

Association of Plastic Recyclers. Comparison of virgin and recycled resin life cycle results, May 2020.
It reports Franklin Associates studies, including one for NAPCOR on virgin PET.
<https://plasticsrecycling.org/wp-content/uploads/2024/08/APR-Recycled-vs-Virgin-LCA-May2020.pdf>

Checked in: the APR document. Cross-check: an NIH summary gives 2.19-2.733 kg CO2e/kg PET resin,
citing Franklin Associates and the Committee of PET Manufacturers in Europe (2017).
<https://nems.nih.gov/Documents/PETWaterBottlesEnvironmentalImpact.pdf>

## IVK_2014

Industrieverband Klebstoffe e.V. *Typical "Product Carbon Footprint" (PCF)-Values for Industrial
Adhesives*. 2014 (year from file metadata).
<https://www.klebstoffe.com/wp-content/uploads/2020/04/M-RS_2014-29_Typische_PCF_Werte_engl_v3_PDFv2__final_.pdf>

Checked in: the leaflet's summary table, cradle-to-gate.

## FEFCO_2021

FEFCO. *The carbon footprint of corrugated packaging 2021*. 15 July 2022.
<https://www.fefco.org/sites/default/files/files/The%20carbon%20footprint%20of%20corrugated%20packaging%202021.pdf>

Checked in: the results table.

## PE_ECOPROFILE_2026

Plastics Europe. *Eco-profile of Polyolefins: HDPE, LDPE, LLDPE, PP*. January 2026.
<https://plasticseurope.org/sustainability/circularity/life-cycle-thinking/eco-profiles-set/>

Checked in: the report's LCIA results table. Climate change uses EF 3.1, based on IPCC 2021.

## VASQUEZ_2022

Vásquez, M., Vásquez-Ibarra, L., Musule, R., Iriarte, A. Carbon footprint of wooden and plastic
pallets: A quantification with different software tools. *Maderas. Ciencia y tecnología* 24(45), 2022.
<https://www.redalyc.org/journal/485/48575019045/html>

Checked in: the article, Chilean case study, 1200 × 1000 mm pallet.

## CALC_FILM_PROXY

Own calculation from sourced values, not a published factor. Electricity for extrusion × German grid:
0.5 × 0.427 = 0.2135 kg CO2e per kg film.

- 0.5 kWh/kg is the midpoint of the 0.4-0.6 kWh/kg typical extrusion process load in Kent, R.
  *Energy Management in Plastics Processing: A Signposting Guide*. British Plastics Federation, 2011.
  <https://tangram.co.uk/wp-content/uploads/BPF-Energy-Management-in-Plastics-Processing.pdf>
- 0.427 kg CO2e/kWh is `EL_DE_GRID`, see UBA_CC13_2025.

## CALC_LINER_PROXY

Own calculation from sourced values, not a published factor. For 1 m² of the 60 g/m² liner in
`config/product_pet_diecut.yaml`:

(58.75 g paper × 0.462 + 1.25 g silicone × 6.36) / 60 g = 0.585 kg CO2e per kg liner.

- 0.462 kg CO2e/kg is the cradle-to-gate fossil footprint of average European sack kraft paper in
  2024. CEPI Eurokraft and EUROSAC, *European paper sacks reduce carbon footprint by 9% between 2021
  and 2024*, fact sheet, 16 April 2026 (analysis by RISE).
  <https://www.eurosac.org/fileadmin/pdf/pdf_press_releases/2026-04-16_Fact-sheet_ESG-Carbon-footprint-2024.pdf>
- 6.36 kg CO2e/kg is cradle-to-gate PDMS rubber/resin, average global production. denkstatt for the
  Global Silicone Council, *Update of the Si-Chemistry Carbon Balance, SILICAB 2 Nutshell Report*,
  2024, Table 9.
  <https://www.silicones.eu/wp-content/uploads/2024/10/240718-GSC-Nutshell-Report-incl.-Appendix.pdf>
- 1.25 g/m² silicone coat weight is an assumption, not a sourced value. It is the middle of the
  0.5-2 g/m² range seen in supplier trade material. That full range moves the factor only from
  0.51 to 0.66 kg CO2e/kg.

## CALC_PET_STOICH

Own calculation, not a published factor. PET's repeat unit is C10H8O4 (192.17 g/mol). Complete
combustion gives 10 × 44.01 / 192.17 = 2.29 kg fossil CO2 per kg PET.
