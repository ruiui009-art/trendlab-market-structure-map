# TrendLab Market Structure Map

An evidence-first market-breadth view for crypto researchers.

> A market-breadth map that reveals whether a crypto move is broad, large-cap-led, or concentrated in a few CMC categories.

Built for the **Data and Visualisation** track of the Build with CMC API Hackathon.

## What it answers

A green crypto headline does not necessarily mean a broad market. The app compares:

- the share of positive assets in a normalized top-100 CMC universe;
- median 24-hour performance and market-cap-weighted 24-hour performance;
- leadership divergence between those two measures;
- CMC global metrics, selected category data, and the CMC Altcoin Season Index.

The output is descriptive: `Broad advance`, `Narrow large-cap leadership`, `Broad weakness`, or `Mixed structure`. It is not a price forecast, a capital-flow claim, or trading advice.

## CMC API endpoints

| Endpoint | Use |
| --- | --- |
| `GET /v3/cryptocurrency/listings/latest` | Top-100 non-stable universe, breadth, median, weighted return. |
| `GET /v1/global-metrics/quotes/latest` | BTC/ETH dominance, total and altcoin market cap, volume. |
| `GET /v1/cryptocurrency/categories` | Category-level average price, market-cap and volume changes. |
| `GET /v1/altcoin-season-index/latest` | CMC's own Altcoin Season Index. |

The UI includes a timestamped endpoint, parameter, HTTP-status, and response-excerpt drawer for each input. It intentionally does not expose a generic CMC proxy or API key.

## Methodology

1. Request the first 150 CMC-ranked assets with CMC `tags`.
2. Exclude only assets tagged `stablecoin`; keep the first 100 eligible assets by CMC rank.
3. Calculate:

```text
Breadth = positive 24h assets / eligible assets * 100
Median return = median(percent_change_24h)
Weighted return = sum(market_cap * percent_change_24h) / sum(market_cap)
Leadership divergence = weighted return - median return
```

4. Use visible heuristic thresholds:

```text
Broad advance      breadth >= 65% and median return > 0
Narrow leadership  weighted return > 0, breadth < 50%, divergence >= 1pp
Broad weakness     breadth <= 35% and median return < 0
Mixed structure    otherwise
```

CMC categories can overlap. The app never adds category market caps together and never calls category changes a measured capital flow.

### Category cross-check

A category is marked `Confirmed` only when its CMC average price change, market-cap change, and volume change are all positive. `Price only` means the average price moved up but at least one of the other two fields does not confirm it. This is a reproducible research lead, not proof of capital flow, causality, or future returns.

### Research brief

The UI can copy a timestamped research brief built from the displayed snapshot. It includes market posture, breadth, leadership divergence, confirmed/unconfirmed category observations, and an editorial limitation. It is a starting point for human research, not content ready for publication or an automated recommendation.

### Snapshot monitor

The interface compares the latest CMC snapshot with the previous snapshot viewed in the same browser. It shows changes in posture, breadth, market-cap-weighted return, and median return. The comparison is stored only in browser local storage; it does not create a server-side history or claim intra-period market data.

## What CMC made possible / limitations

CMC makes it possible to compare a single timestamped market snapshot across ranked assets, global metrics, categories, and the Altcoin Season Index. Without a common source, the breadth calculation would mix incompatible universes and update times.

The API does not prove capital flows, causality, or future returns. The app therefore labels its result as a descriptive snapshot and exposes inputs instead of inventing a prediction. During local development CMC's shared Keyless API returned `429`; that is why the product uses server-side caching, exponential backoff, clear stale/unavailable states, and a campaign-upgraded key for the hackathon demo.

## Run locally

Requires Python 3. No packages need to be installed.

```bash
python3 -m unittest
npm run test:brief
python3 server.py
```

Open [http://127.0.0.1:4174](http://127.0.0.1:4174).

Without a key the server uses CMC's Keyless Public API for local experimentation. For the hackathon and deployment, set the CMC account key upgraded through the campaign only in the process environment:

```bash
export CMC_API_KEY="key-from-password-manager"
python3 server.py --host 0.0.0.0
```

Never commit a key, pass it in a query string, or show it in a video. `.env.example` intentionally contains no secret and dotfiles are blocked by the development server.

## Demo evidence checklist

1. Start the server with the campaign-upgraded CMC key in the environment.
2. Refresh the page and show the market posture, breadth distribution, and category table changing from a real CMC response.
3. Open the four CMC evidence drawers: endpoint, parameters, HTTP status, CMC response timestamp, credit count, and response excerpt are visible.
4. Show the methodology drawer and explain why a broad move differs from narrow large-cap leadership.
5. Do not record the terminal, browser network headers, or hosting settings where the key could appear.

## Production notes

- The browser requests only `/api/market-structure`; it never calls CMC directly.
- Server cache TTL is 15 minutes for listings/global metrics and 60 minutes for categories/Altcoin Season.
- Transient `429` and `5xx` failures retry with exponential backoff. Cached data is explicitly labeled `stale`; unavailable core data does not produce a market regime.
- Cache and normalized response fields keep CMC data inside the end-user product rather than offering a standalone data service.

## Deploy

The included `Dockerfile` runs on any container host. Configure `CMC_API_KEY` only as a server-side environment secret and let the platform provide `PORT`; the server defaults to `4174` locally. Do not add a key to Docker build arguments, repository variables, or client-side configuration.

### Render Blueprint

1. Create a public GitHub repository from this directory and push the default branch.
2. In Render, create a new **Blueprint** and connect that GitHub repository.
3. Render reads `render.yaml`, builds the Dockerfile, and prompts for `CMC_API_KEY`. Enter the existing campaign-upgraded key only in that secret field.
4. Deploy, then open the generated `onrender.com` URL. A successful refresh shows `KEYED CMC` in the header and four evidence entries with HTTP status and CMC timestamps.

The Blueprint uses Render's `free` plan for the hackathon demo. Confirm the current plan terms in Render before creating it; free services can have availability and cold-start limits that are not suitable for a production SLA.

## Originality disclosure

`WhyNot Trend Lab` existed before this hackathon as a BTC/ETH technical and macro-risk page using other sources. This repository is a new, isolated CMC market-structure module. Its CMC integration, methodology, evidence drawer, and interface are purpose-built for this hackathon.
