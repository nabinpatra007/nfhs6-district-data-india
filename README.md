# NFHS-6 District-Level Data (India) — Independent Compilation

District-level indicators from India's **National Family Health Survey-6 (NFHS-6, 2023–24)**, parsed from the **official IIPS State and District Fact Sheet PDFs** into CSV format.

This repository is an **independent, unofficial compilation** and is **not produced or endorsed by the International Institute for Population Sciences (IIPS) or the Ministry of Health and Family Welfare (MoHFW).**

## What's included

* **35 NFHS-6 State/UT CSV files** covering all surveyed States/UTs
* **1 consolidated dataset:** `all_india_nfhs6_district.csv`
* Python scripts used for PDF parsing and consolidation

> **Note:** Manipur is not included because NFHS-6 did not conduct the survey there.

## Data source

The underlying data are published by the **International Institute for Population Sciences (IIPS), Mumbai**, under the **Ministry of Health and Family Welfare, Government of India**, as PDF fact sheets.

The data in this repository are **parsed directly from those PDF fact sheets into CSV format**. No survey data were collected, generated, or independently estimated by this project.

**Official source:**
https://iipsindia.ac.in/content/nfhs-projects

## Data fields

| Column                         | Description                                                                   |
| ------------------------------ | ----------------------------------------------------------------------------- |
| `state`                        | State/UT name                                                                 |
| `district`                     | District name                                                                 |
| `category`                     | Indicator category                                                            |
| `indicator_no`                 | Indicator number                                                              |
| `indicator`                    | Indicator description                                                         |
| `nfhs6_value`                  | NFHS-6 (2023–24) value                                                        |
| `nfhs5_value`                  | NFHS-5 (2019–21) value, where available                                       |
| `small_sample_flag`            | Small-sample flag from the source                                             |
| `boundary_change_single_round` | Indicates districts without a valid NFHS-5 comparison due to boundary changes |

## Provisional data

The NFHS-6 fact sheets used in this repository contain **provisional results**. IIPS cautions users regarding interpretation and comparison of some indicators, particularly those affected by small sample sizes.

For important research or publication, please verify values against the original IIPS fact sheets.

## Citation

Please cite both the original source and this repository when using the data.

### Original source

> International Institute for Population Sciences (IIPS). *National Family Health Survey-6 (NFHS-6), 2023–24: State and District Fact Sheets*. Mumbai: IIPS.

### Parsed dataset

> Patra, N. K. (2026). *NFHS-6 District-Level Data (India): Independent Compilation*. GitHub.

## License

**Code:** MIT License.

**Data:** The CSV files are parsed from publicly available NFHS-6 fact sheets published by IIPS. The MIT License applies to the original code in this repository and does **not** relicense the underlying NFHS-6 source material.

Users should refer to the original IIPS/NFHS-6 source and comply with any applicable terms of use.

## Contributing

Found a parsing error or data discrepancy?

Please open an issue with the relevant **State/UT, district, indicator, and source PDF reference**.

Contributions to improve the parsing scripts are welcome.
