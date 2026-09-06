# Quantum Observatory

A minimal, English-language research dashboard for quantum computing and quantum information. It collects public scholarly metadata weekly, links publication versions, and publishes a static website on Cloudflare Pages.

## What works

- Live arXiv collection, with pagination and a rolling overlap for updates.
- Crossref metadata for PRX Quantum, Quantum, and npj Quantum Information.
- Accepted-talk ingestion from the QIP 2026 official list, retaining conference date ranges.
- DOE OSTI technical-report discovery, a configured GAO report monitor, and an NQI PDF-index adapter with explicit failure reporting.
- Optional, budget-bounded OpenAlex DOI enrichment.
- Eight topic dictionaries, DOI/arXiv linking, immutable first-seen dates, and preserved revision events.
- Weekly research counts, topic distributions, comparison eligibility, and an archive.
- Title/author/identifier search, material/topic/source/date filters, grouped versions, pagination, CSV export, and on-demand abstract details.
- Light/dark themes, responsive layouts, keyboard navigation, native detail dialogs, and chart data tables.
- GitHub Actions for validation, weekly collection, durable data-branch updates, and Cloudflare Pages Direct Upload.

## Implementation

The initial design proposed Astro/React. The first version uses plain HTML, CSS, and JavaScript modules, with Python's standard library for collection and static generation. The weekly data architecture is unchanged. There are no Python packages or frontend dependencies to install. Wrangler runs only in the deployment job.

Requirements: Python 3.12+ and Node.js 22+.

```bash
python3 -m pipeline.collect
npm test
npm run build
npm run check
npm run preview
```

Open `http://localhost:8080`. Browser search covers titles, authors, DOI, and arXiv identifiers. Abstracts load only when a detail panel opens. Open `deliverables/quantum-observatory-preview.html` directly for a self-contained, offline review of the bundled snapshot, when supplied with the release archive.

## Repository layout

| Path | Purpose |
|---|---|
| `web/` | Static UI, chart, filters, accessibility, headers |
| `pipeline/adapters.py` | Source-specific fetching and parsing |
| `pipeline/model.py` | Normalization, classification, linking, validation |
| `pipeline/collect.py` | Collection orchestration and checkpoints |
| `pipeline/aggregate.py` | Weekly statistics and research groups |
| `pipeline/build.py` | Static routes and partitioned detail data |
| `config/sources.json` | Source URLs, limits, enabled/required flags |
| `config/topics.json` | Topic labels, colors, and keyword rules |
| `config/overrides.json` | Manual record corrections and explicit merges |
| `scripts/git_data.py` | Restore/persist the dedicated `data` branch |
| `tests/` | Data-integrity and frontend-logic tests |
| `.github/workflows/` | Validation and weekly publication |

The local `data/` directory is ignored on `main`. The `data` branch stores `records/*.jsonl`, `state.json`, and run manifests. Do not use Actions cache as the authoritative dataset. A supplied project archive may include a real local snapshot so the site can be rebuilt immediately.

## GitHub setup

1. Create a repository (suggested name: `quantum-observatory`) and push this project's `main` branch.
2. Keep `main` as the default branch. Allow the collection workflow's `GITHUB_TOKEN` to write repository contents. Branch rules must allow this workflow to update `data`; it never force-pushes or modifies `main`.
3. In repository **Settings → Secrets and variables → Actions**, configure the values below.
4. Run **Collect and publish** manually once. With no previous data branch it backfills 12 weeks. The code-validation workflow uses isolated synthetic fixtures and never deploys them.

| Name | Kind | Required for |
|---|---|---|
| `PAGES_PROJECT_NAME` | Repository variable | Enabling the deploy job |
| `CLOUDFLARE_ACCOUNT_ID` | Repository variable | Cloudflare deployment |
| `SITE_URL` | Repository variable | HTTPS production URL and verification |
| `CLOUDFLARE_API_TOKEN` | Repository secret | Account → Cloudflare Pages → Edit, scoped to the target account |
| `CONTACT_EMAIL` | Repository variable | Recommended identification in scholarly API requests |
| `OPENALEX_API_KEY` | Repository secret | Optional OpenAlex enrichment |

Never commit tokens or put them in the browser bundle. Enter secrets directly in GitHub settings; do not paste tokens into a public issue or document.

## Cloudflare Pages setup

Create a **Pages Direct Upload** project named `quantum-observatory` (or your chosen name), with production branch `main`. Do not enable a second automatic Git build for this project. The GitHub workflow builds `dist/` and uploads that exact artifact using Wrangler.

Example initial project creation from an authenticated workstation:

```bash
npx wrangler pages project create quantum-observatory --production-branch=main
```

Set `SITE_URL` to the returned HTTPS Pages URL, or a custom domain attached to the project. The deploy job verifies that `/data/manifest.json` serves the exact expected `build_id`, which fingerprints the dataset, application, pipeline, and configuration. This also distinguishes code-only rebuilds of the same collection run. The workflow does not consider upload completion alone to be proof that the correct version is being served.

No deployed URL is implied by the source bundle. Account configuration and a successful workflow run are still required.

## Weekly behavior

- Schedule: Monday 09:17 Asia/Seoul, expressed as UTC cron `17 0 * * 1`.
- Reporting boundary: Monday 00:00 KST, with an exclusive next-Monday end.
- First run: 12-week backfill; conferences and configured report pages may include older records.
- Subsequent runs: source-specific successful checkpoint minus 14 days. Early-month runs revisit at least 12 weeks.
- Required-source failure: successful checkpoints and published data remain unchanged; diagnostics are retained as a workflow artifact.
- Optional-source failure: other records may publish, with missing coverage shown in Methodology.
- Production data is persisted only after a valid build. An upload failure can be retried without collecting again.
- GitHub scheduled events may be delayed, dropped, or disabled after long inactivity in public repositories. Manual dispatch remains available. The UI marks snapshots older than eight days as overdue.

To rebuild/deploy code changes without recollecting: manually run **Collect and publish**, set `collect` to false, and leave `deploy` true. A push to `main` that changes the application, pipeline, configuration, deployment scripts, or publication workflow triggers collection and a validated rebuild. Deployment runs when the Cloudflare variables and secret are configured. Documentation-only and test-only pushes run code validation without publishing.

## Counting and scientific limitations

- Only explicit DOI/arXiv relationships or manual overrides merge research. Title similarity is not sufficient. Some unlinked versions will remain separate until an identifier becomes available.
- `first_published` is the earliest known publication among linked paper records. Talks and reports never shift this date.
- A v2 update is a revision, not a new research work.
- Multi-topic counts overlap. Topic labels reflect lexical rules rather than an expert quality assessment.
- Current/incomplete weeks, zero baselines, and mismatched source coverage do not receive growth percentages.
- Publication metadata reconstructed today is not a historical snapshot of what was known then. First-seen history begins when this collector starts.
- QIP accepted entries are not proof that each presentation was delivered. Conference-year URLs require an explicit config update. The exact individual talk time is not invented.
- OSTI uses its API-provided publication calendar date. NQI PDFs without an explicit date stay undated, and remain discoverable under all dates. Upload-path dates are never treated as publication dates.
- GAO is a configured-page monitor, not an exhaustive new-report search. DOE OSTI supplies automated technical-report discovery.
- Crossref abstracts are not redistributed by default. arXiv abstract display links to its original record; PDFs remain at their source.
- OpenAlex is optional. Without a key, the UI reports it as unconfigured. Its enrichment budget is capped in `sources.json`.
- The index is loaded once; details are split into source/hash shards. The build checks Pages asset size and count limits. Large future corpora should move long-term partitions to R2 and introduce a search API.

## Manual corrections

```json
{
  "records": {
    "record-id": {"topics": ["error-correction"]}
  },
  "merge": [["record-id-one", "record-id-two"]]
}
```

Use actual stable record IDs from the index. Rebuild after changes. Record the reason in the Git commit. The source data remains attributable to its original URL.

## Recovery

1. If collection fails, inspect the diagnostic artifact and source-specific status. Re-run after the source recovers; the successful checkpoint has not advanced.
2. If deployment fails after data persistence, run the workflow with `collect=false`.
3. If a new site version is faulty, restore a known-good Pages deployment, or rebuild from its recorded source/data commits. Do not reset/force-push data history to recover a website.

## Verification included

Tests exercise timezone boundaries, version idempotency, DOI linking, false title matches, undated records, failed-source preservation, partial dates, conference parsing, report-type filtering, search/grouping, unsafe URLs, CSV injection, and empty chart series. Artifact checks verify every route and asset, unique IDs, linked-record integrity, matching run IDs, detail shards, and file limits.

Browser visual/end-to-end testing has not been performed in this environment. Test the deployed preview on desktop/mobile before treating the first deployment as production-ready for a broader audience.

## Source documentation

- [arXiv API](https://info.arxiv.org/help/api/user-manual.html)
- [arXiv API terms](https://info.arxiv.org/help/api/tou.html)
- [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/)
- [QIP 2026 accepted papers](https://qip2026.lu.lv/programme/accepted-papers/)
- [OSTI API](https://www.osti.gov/api/v1/docs)
- [GAO report](https://www.gao.gov/products/gao-26-107759)
- [OpenAlex authentication](https://help.openalex.org/api/authentication/)
- [GitHub schedules](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
- [Cloudflare Pages CI upload](https://developers.cloudflare.com/pages/how-to/use-direct-upload-with-continuous-integration/)
