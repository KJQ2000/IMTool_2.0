# 🗺️ Improvement Roadmap

Based on the 360-degree audit, here is an actionable roadmap to modernize and scale the IMTool app.

## 🚧 1. Top 3 "Tech Debt" Areas to Fix Immediately

1. **Floating Point Arithmetic Drift**: Convert all price calculation logic (Gold, Labor, Totals) from Python `float` to `decimal.Decimal`. Apply `ROUND_HALF_UP` consistently. If the database uses `REAL` or `FLOAT` for columns like `stk_gold_cost`, migrate them to `NUMERIC(10, 2)`.
2. **Server-Side Data Processing**: Replace all blind `fetch_all` queries with paginated, server-side filtered queries. The current `st.dataframe` memory footprint will crash the app when the inventory grows.
3. **Optimistic Concurrency Lock**: Add a `last_update` timestamp check into `save_table_changes()`. If user A and user B edit the same row simultaneously, user B should see a "Data modified by another user" error instead of silently overwriting user A's work.

---

## 🏛️ 2. Strategy for Handling "Historical Data"

Currently, the `sale` and `booking` records duplicate some pricing data from `stock`, which is a good standard pattern. However, to guarantee historical immutability:

**Strategy: "Hard Snapshotting"**
- A stock item has a `stk_gold_cost` (the cost when purchased).
- But the daily gold market rate fluctuates.
- When an item is sold, the exact market rate used for that specific transaction must be permanently snapshot in the `sale` table alongside the line item.
- Do **not** join a live "settings" table to calculate past profits. Instead, compute the `profit` at the exact moment of sale and permanently write it to the `sale` (or a `sale_items`) table (which we partially do now via `update_status_sold` profit computation).
- **Enforcement:** Use Postgres row-level triggers to `DENY UPDATE` on a `sale` record once it is finalized, making it an immutable ledger.

---

## ✨ 3. Premium UI/UX Features for a Luxury Brand

To elevate the app's feel to match a 90-year heritage of gold craftsmanship and trust:

1. **Sleek, Skeleton Loading States & Micro-Animations**
   - Instead of standard blocking spinners, implement skeleton loaders (using `st.empty` and placeholder CSS) while queries fetch. Add very subtle `opacity` fade-ins to tables using injected CSS. The app should feel snappy, fast, and weightless.

2. **Advanced, Dynamic Analytical Dashboards**
   - Move beyond raw tables by introducing a "CEO Dashboard." Use interactive charting libraries (like Streamlit's integration with Plotly or Altair) with curated color palettes (e.g., deep charcoal background, subtle gold/bronze accents). Show a real-time heatmap of "Top Selling Patterns" and an interactive trend line of daily profit margins. The UI should instantly convey control and high-level insight.
