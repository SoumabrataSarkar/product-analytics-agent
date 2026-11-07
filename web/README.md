# Visual architecture explorer — planned

This folder will hold a browser-based, Finder/Windows Explorer-inspired view of the repository's folders and documentation.

**Proposed documentation tabs:** Repository explorer; architecture/versions; Bronze–Silver–Gold data flow; Metric Registry; How RCA works; evaluations.

**Future interactive tab:** Ask AI, inspect generated SQL and evidence, choose configured model runtime. This is **not implemented yet**. A static HTML page can visualize documents, but live database/LLM queries and private GitHub synchronization require appropriately authorized services or a trusted local backend. Never put API keys or private-repository tokens in browser assets.

Start with an inspectable static UI and preserve core analytics functionality independent of the UI.
