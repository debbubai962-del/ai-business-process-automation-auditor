\# Security and privacy



| Risk | Control |

|---|---|

| API key exposure | Read only from environment variables. Stored with `repr=False`. Never rendered, logged or placed in an error message (tested). `.env` is git-ignored. |

| Business data sent to a third party | Only an aggregated evidence pack is sent, never rows, case IDs or file contents. The pack is viewable in the app, capped in size, and checked before sending. |

| Prompt injection via data values | Category labels are stripped of control characters, angle brackets, braces and backticks, and truncated. The prompt tells the model the evidence is data, not instructions. |

| Hallucinated numbers | Every number in AI text is matched against the evidence. Untraceable figures are shown to the user. |

| Malicious files | Extension allow-list, 50 MB cap (also enforced by Streamlit), read in memory, never executed. No macro execution. |

| Spreadsheet formula injection | Text cells beginning with `=`, `+`, `-`, `@` are neutralised in the Excel workbook and audit CSV (tested by scanning the workbook for formula cells). |

| HTML/XSS in reports | All values are HTML-escaped. The report has no scripts. The in-app preview uses an isolated `data:` frame. |

| Data persistence | Nothing is written to disk. Everything lives in the session and is cleared with it. |

| Over-reliance on AI | Every output is labelled. Recommendations are marked as decision support to be validated by business owners. |

| Unhandled errors leaking details | Streamlit error details are turned off. AI failures show a fixed message and fall back to the rule-based brief. |



\## Deploying publicly

Anyone using a public deployment with your API key can spend your credit. Either leave the key out (the app runs in no-AI mode) or use a key with a low spending limit.

