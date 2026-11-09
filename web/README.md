# Visual architecture explorer

`index.html` is a static, browser-based view of the project: the repository explorer, architecture and versions, the Bronze–Silver–Gold data flow, the metric registry, how an investigation works, and evaluations. It reflects the repository's documented status; it does not read the database or run the agent.

**Future interactive tab:** Ask AI, inspect generated SQL and evidence, choose configured model runtime. This is **not implemented yet**. A static HTML page can visualize documents, but live database/LLM queries and private GitHub synchronization require appropriately authorized services or a trusted local backend. Never put API keys or private-repository tokens in browser assets.

Start with an inspectable static UI and preserve core analytics functionality independent of the UI.
