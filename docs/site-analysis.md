# Workplace Relations decisions site analysis

Checked 2026-09-05 against the public site using normal HTTP requests with a descriptive User-Agent. No authentication, CAPTCHA bypass, proxy rotation, or browser automation was used.

## Confirmed search flow

- Search page: `https://www.workplacerelations.ie/en/search/?advance=true`
- The page is server-rendered HTML. The form is `POST` to the same URL and uses ASP.NET hidden state, but a normal `GET` search URL is also accepted and is easier for Scrapy to replay.
- Verified GET shape:
  `?decisions=1&from=01/01/2024&to=31/01/2024&legislationsub=&body=15376`
- Date inputs use `dd/mm/yyyy`.
- Pagination adds `pageNumber=N`; results show 10 items per page.
- Each result is `li.each-item` with:
  - identifier: `h2.title a[title]` (fallback link text)
  - published date: `span.date`
  - description: `p.description[title]`
  - detail URL: `h2.title a[href]` (fallback `.btn[href]`)
- Result count is in `div.searchhead`, for example `Shows 1 to 10 of 234 results`.

## Body values

The search form exposes four checkboxes under `CB2`:

| Body | submitted value |
| --- | ---: |
| Employment Appeals Tribunal | 2 |
| Equality Tribunal | 1 |
| Labour Court | 3 |
| Workplace Relations Commission | 15376 |

Observed January searches: WRC 234 results (2024), Labour Court 45 (2024), Equality Tribunal 4 (2013), and Employment Appeals Tribunal 74 (2010). These counts were used to confirm all four paths and pagination.

## Detail and document behavior

Detail pages are under `/en/cases/<year>/<month>/...`. WRC, Labour Court, and Equality Tribunal examples returned HTML decision pages. Their legal content is in `div.content`. Search metadata supplies the published date; the page itself may contain a dated decision/recommendation but does not expose one uniform `Published` label.

Employment Appeals Tribunal examples expose `a.download[href]` links to `/en/eat_import/...pdf`. The spider follows this link and uses response `Content-Type`, PDF magic bytes, and URL suffix as evidence for the file type. If no download link exists, the detail HTML itself is the Landing source.

The result/detail pages do not require JavaScript for the request flow. `robots.txt` was available and includes disallow entries for uppercase `/en/Cases/` and imported paths; the implementation leaves Scrapy's robots setting enabled and uses the site's observed lowercase public URLs. This should be reviewed if the site changes its robots rules.
