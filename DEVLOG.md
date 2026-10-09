# Dev log

Running notes on what broke, what was surprising, and how it was caught.

## Day 1: planning and scaffold

- Defined the scope: five companies, six metrics, and three stages (loader, summarizer, checker).
- Main design decision: Python computes all figures and changes, the LLM only writes narrative, and every figure it cites is checked against the database.
- Reviewed the structure of EDGAR's company facts data. The biggest trap, found before writing any loader code, is that each fact's `fy` field is the fiscal year of the filing, not of the value. One 10-K reports several years of income statement figures, all tagged with the same `fy`. The plan is to identify periods by their `start` and `end` dates instead (see DESIGN.md).
- Wrote the fetch and exploration scripts and tested them offline against a mock company facts file. First live run against EDGAR is still to do.
- Hit a setup issue: Homebrew no longer installs on Intel Macs. Development will continue on a Windows PC.

**Next:** choose the companies and record why; run the exploration script on live data; finalize the revenue tag priority for each company.
