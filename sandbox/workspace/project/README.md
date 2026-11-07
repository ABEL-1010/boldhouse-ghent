# Atlas

Atlas is the internal reporting service of OurCompany. It collects usage metrics from our
products and turns them into weekly dashboards for the product teams.

## Getting started
1. Install Python 3.12 and `uv`.
2. Copy the config: `cp .env.example .env` and ask the team lead for the values.
3. Run the service: `uv run atlas serve`.

## Project layout
- `atlas/collectors/` pulls metrics from each product.
- `atlas/reports/` builds the weekly dashboards.
- `atlas/scheduler/` runs the nightly jobs.

## Open issues
- The nightly export sometimes times out on large tenants.
- The scheduler has no retry on transient database errors.
- Report emails do not render well in Outlook.

## Contributing
Open a merge request and ask someone from the team for review. Keep changes small.
