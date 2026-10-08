\# AI Business Process Automation Auditor



!\[tests](https://github.com/YOUR-USERNAME/ai-business-process-automation-auditor/actions/workflows/tests.yml/badge.svg)



\*\*Upload a raw operational export and get an evidence-backed diagnosis of where a process loses time and money, and which parts are worth automating.\*\*



It is a decision-support product for Operations Managers, Process Excellence teams and transformation consultants. It is not a dashboard and not a chatbot. Python computes every number. The AI only interprets pre-computed findings, and every figure it writes is checked against them.



!\[Executive brief](docs/screenshots/08-executive-brief.png)



\## What it does



```

Raw CSV / Excel

&#x20;  -> Data quality audit and safe auto-cleaning (with audit trail)

&#x20;  -> Process discovery (column mapping, event log)

&#x20;  -> Process health (cycle time, SLA, rework, variants)

&#x20;  -> Bottleneck detection (frequent vs severe)

&#x20;  -> Root-cause analysis (statistical, fact vs hypothesis)

&#x20;  -> Automation opportunity engine (transparent scoring, "no automation" when right)

&#x20;  -> Business impact simulator (editable assumptions, current vs improved)

&#x20;  -> Executive brief + 30/60/90-day plan (AI or rule-based, numbers verified)

&#x20;  -> Report, workbook, audit trail, evidence pack

```



| | |

|---|---|

| !\[Data quality](docs/screenshots/01-data-quality.png) | !\[Bottlenecks](docs/screenshots/04-bottlenecks.png) |

| !\[Automation matrix](docs/screenshots/06-automation-matrix.png) | !\[Simulator](docs/screenshots/07-simulator.png) |



\## Why it is different



\*\*1. Trust is built in.\*\* Every output carries one of five labels: `DATA FACT`, `CALCULATED METRIC`, `BUSINESS ESTIMATE`, `AI INTERPRETATION`, `HYPOTHESIS`. Observed facts and explanations are never mixed.



\*\*2. Deterministic first, AI second.\*\* The AI never sees raw rows. It receives a small aggregated \*evidence pack\* (viewable in the app before anything is sent). After it replies, \*\*every number in its text is checked against the evidence\*\*, and untraceable figures are flagged.



\*\*3. It knows when not to automate.\*\* Automation is never recommended just because a step is slow. A step that is rare, highly variable and judgement-heavy is screened out, and the reason is shown.



\*\*4. Nothing is changed silently.\*\* Safe formatting fixes are applied and logged (\*original issue, action taken, records affected\*). Anything that could change a business conclusion is flagged for a human, and the original upload is never modified.



\*\*5. It degrades honestly.\*\* With missing columns it reports what it cannot compute instead of guessing. With no AI key it still produces a full rule-based brief.



\## Validated against known ground truth



The demo data is synthetic, with problems planted on purpose, so the engines can be checked against a known answer:



| Planted in the data | Found by the app |

|---|---|

| Manager Approval is the bottleneck | Primary bottleneck: longest step in 98% of cases, 84% of all step time |

| Finance Ops approvals are about 1.8x slower, worse on Mondays and Fridays | Department and day-of-week flagged, with the Finance Ops x Monday/Friday hotspot visible in the heatmap |

| Exception Review is slow but judgement-heavy | "Occasional severe delay", \*\*not recommended for automation\*\* |

| Data Entry and Three-Way Match are repetitive and rule-based | Ranked quick wins (RPA, rule-based automation) |

| Invoice value, vendor type and time of day have no effect | Reported as "no meaningful effect" |

| \~2% duplicates, mixed date formats, misspelled categories, impossible timestamps | Detected, fixed or flagged, with a full audit trail |



76 automated tests cover this, plus hand-calculated checks of every formula.



\## Architecture



```mermaid

flowchart LR

&#x20; U\[Upload] --> Q\[Data quality engine]

&#x20; Q --> M\[Mapping and event log]

&#x20; M --> E1\[Metrics]

&#x20; M --> E2\[Bottlenecks]

&#x20; M --> E3\[Root causes]

&#x20; M --> E4\[Automation engine]

&#x20; E4 --> S\[Impact simulator]

&#x20; E1 \& E2 \& E3 \& E4 \& S --> B\[Evidence pack]

&#x20; B --> A\[AI layer via OpenRouter]

&#x20; B --> R\[Rule-based brief]

&#x20; A --> V\[Number-grounding validator]

&#x20; R --> V

&#x20; V --> X\[Report, workbook, audit trail]

```



Engines are pure Python with no Streamlit imports, so they are unit-testable. See \[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and \[docs/METHODOLOGY.md](docs/METHODOLOGY.md).



\## Tech stack



Python 3.11, Streamlit, Pandas, NumPy, SciPy, Plotly, Pydantic, openpyxl, OpenAI SDK pointed at OpenRouter, pytest, GitHub Actions.



\## Run it locally



```

conda create -n process-auditor python=3.11 -y

conda activate process-auditor

pip install -r requirements.txt

copy .env.example .env          # then add your OpenRouter key (optional)

python sample\_data\\generate\_demo\_data.py

streamlit run app.py

```



Click \*\*Demo: messy\*\* to try it without any data. Without an API key the app runs in no-AI mode.



```

python -m pytest -q             # 76 tests

python tools\\benchmark.py       # timings

```



\## Security and privacy



API key only in environment variables and never displayed. Raw data never sent to the AI (aggregates only, inspectable). Uploaded files held in memory only. Labels from data are sanitised against prompt injection. Exports are escaped against HTML and spreadsheet-formula injection. See \[docs/SECURITY.md](docs/SECURITY.md).



\## Project structure



```

app.py            entry point

config/           settings and scoring defaults

models/           typed result objects

engines/          ingestion, quality, mapping, metrics, bottlenecks, root\_cause, automation, impact

ai/               evidence pack, prompts, client, validator, rule-based fallback

services/         session state, caching, analysis bundle

reporting/        HTML report, Excel workbook, audit trail

ui/               pages, components, theme

sample\_data/      synthetic data generator (seeded, reproducible)

tests/            76 tests

docs/             architecture, methodology, security, interview guide

```



\## Limitations and roadmap



\- Hands-on effort is estimated from recorded step durations (25% share, capped at 30 minutes by default) because timestamps cannot show touch time. It is an editable assumption.

\- Statistics show that groups differ, not why. Explanations are labelled hypotheses to confirm with process owners.

\- Analyses one process at a time, with no persistence or user accounts.

\- Next: process-flow graph, conformance checking, saved projects, multi-period trend comparison.



\## License



MIT. See \[LICENSE](LICENSE).

