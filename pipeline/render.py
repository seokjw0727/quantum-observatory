"""Render crawlable, route-specific HTML for the static site."""

import html
import json
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse


def esc(value):
    return html.escape(str(value or ""), quote=True)


def date_label(value):
    if not value:
        return "Date unavailable"
    parsed = date.fromisoformat(str(value)[:10])
    return f"{parsed.strftime('%b')} {parsed.day}, {parsed.year}"


def week_label(value):
    start = date.fromisoformat(value)
    end = start + timedelta(days=6)
    return f"{start.strftime('%b')} {start.day} – {end.strftime('%b')} {end.day}, {end.year}"


def safe_url(value):
    parsed = urlparse(value or "")
    return value if parsed.scheme in {"https", "http"} and parsed.netloc and not parsed.username else "#"


def source_message(source):
    if source.get("status") == "success":
        return "Coverage available for this collection run."
    if source.get("status") == "failed":
        return "Unavailable during the latest collection; previously verified records were retained."
    if source.get("status") == "not_configured":
        return "Optional metadata enrichment is not configured."
    return source.get("note") or "Automated collection is disabled."


def header(active):
    links = [
        ("overview", "/", "Overview"),
        ("research", "/research/", "Research"),
        ("analysis", "/analysis/", "Analysis"),
        ("guides", "/guides/", "Guides"),
        ("methodology", "/methodology/", "Methodology"),
    ]
    nav = "".join(
        f'<a href="{url}" data-page="{key}"{(" aria-current=\"page\"" if key == active else "")}>{label}</a>'
        for key, url, label in links
    )
    return f'''<a class="skip" href="#main">Skip to content</a>
    <header class="site-header"><div class="header-inner">
      <a class="brand" href="/" aria-label="Quantum Observatory home"><span class="brand-mark" aria-hidden="true">q.</span><span>Quantum <strong>Observatory</strong></span></a>
      <button id="theme-toggle" class="icon-button" aria-label="Toggle color theme" title="Toggle color theme"><span class="theme-icon" aria-hidden="true"></span></button>
      <button id="menu-toggle" class="menu-toggle" aria-controls="main-nav" aria-expanded="false" aria-label="Open navigation"><span class="menu-label">Menu</span><span class="menu-lines" aria-hidden="true"><span></span><span></span></span></button>
      <nav id="main-nav" aria-label="Main navigation" tabindex="-1"><div class="nav-links">{nav}</div></nav>
    </div></header>'''


def footer(config):
    return f'''<footer class="site-footer"><span>Independent research indexing and analysis.</span><span class="footer-links">
      <a href="/about/">About</a><a href="/contact/">Contact</a><a href="/editorial-policy/">Editorial policy</a><a href="/privacy/">Privacy</a><a href="/terms/">Terms</a><a href="{esc(config['repository_url'])}" target="_blank" rel="noopener noreferrer">Source code ↗</a>
    </span></footer>'''


def shell(config, *, title, description, body, active, path, dynamic=False, schema=None, robots="index,follow"):
    origin = config["canonical_origin"].rstrip("/")
    canonical = origin + path
    build_id = str(config.get("_build_id", ""))
    asset_suffix = f"?v={esc(build_id)}" if build_id else ""
    schema_tag = ""
    if schema:
        schema_tag = '<script type="application/ld+json">' + json.dumps(schema, ensure_ascii=False).replace("<", "\\u003c") + "</script>"
    script = ("/assets/app.js" if dynamic else "/assets/common.js") + asset_suffix
    return f'''<!doctype html>
<html lang="{esc(config['language'])}">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="description" content="{esc(description)}" />
    <meta name="robots" content="{esc(robots)}" />
    <meta name="theme-color" content="#f9fafb" />
    <link rel="canonical" href="{esc(canonical)}" />
    <title>{esc(title)} · Quantum Observatory</title>
    <link rel="icon" href="/assets/favicon.svg" type="image/svg+xml" />
    <link rel="preload" href="/assets/fonts/dm-sans.woff2" as="font" type="font/woff2" crossorigin />
    <link rel="preload" href="/assets/fonts/newsreader.woff2" as="font" type="font/woff2" crossorigin />
    <link rel="stylesheet" href="/assets/style.css{asset_suffix}" />
    {schema_tag}
    <script type="module" src="{script}"></script>
  </head>
  <body data-nav="{esc(active)}" data-build-id="{esc(build_id)}">
    {header(active)}
    <main id="main" tabindex="-1">{body}</main>
    {footer(config)}
    {('<dialog id="detail-dialog" aria-labelledby="detail-title"><div id="detail-content"></div></dialog>' if dynamic else '')}
  </body>
</html>
'''


def page_heading(title, description, eyebrow="QUANTUM COMPUTING & INFORMATION"):
    return f'<div class="page-heading static-heading"><div><h1>{esc(title)}</h1><p>{esc(description)}</p></div></div>'


def article_path(article):
    plural = "analysis" if article["type"] == "analysis" else "guides"
    return f"/{plural}/{article['slug']}/"


def article_card(article):
    return f'''<article class="editorial-card"><h2><a href="{article_path(article)}">{esc(article['title'])}</a></h2><p>{esc(article['summary'])}</p><div class="article-meta"><span>{esc(article['type'].title())} · {esc(article['author'])}</span><time datetime="{esc(article['updated_at'])}">Updated {date_label(article['updated_at'])}</time></div></article>'''


def reading_paths(articles):
    links=''.join(f'<li><a href="{article_path(a)}">{esc(a["title"])}</a><p>{esc(a["summary"])}</p></li>' for a in articles[:3])
    return f'<section class="reading-paths" aria-labelledby="reading-paths-title"><h2 id="reading-paths-title">Read beyond the abstract</h2><p>Our research notes separate reported results from interpretation, and explain what to check before comparing claims.</p><ul>{links}</ul></section>'


def library_introduction():
    return '<div class="library-introduction"><p>Start with a topic and a publication year. Newest first follows the earliest known public year of a linked work, rather than the date it was added here. Citations help trace established literature; they do not measure research quality.</p><p><a href="/guides/sorting-papers-without-ranking-quality/">How to use years and citation counts</a> · <a href="/analysis/">Read our research analysis</a> · <a href="/topics/error-correction/">Error-correction reading path</a></p></div>'


def render_article(config, article, related):
    path = article_path(article)
    sections = []
    for section in article["sections"]:
        paragraphs = "".join(f"<p>{esc(p)}</p>" for p in section.get("paragraphs", []))
        bullets = ""
        if section.get("bullets"):
            bullets = "<ul>" + "".join(f"<li>{esc(item)}</li>" for item in section["bullets"]) + "</ul>"
        citations=''.join(f'<a href="#source-{i}">Source {i}</a> ' for i in section.get('source_indexes',[]))
        citation_html=f'<p class="section-sources">{citations}</p>' if citations else ''
        sections.append(f'<section><h2>{esc(section["heading"])}</h2>{paragraphs}{bullets}{citation_html}</section>')
    sources = "".join(
        f'<li id="source-{i}"><a href="{esc(safe_url(source["url"]))}" target="_blank" rel="noopener noreferrer">{esc(source["label"])} ↗</a><p>{esc(source.get("note", ""))}</p></li>'
        for i,source in enumerate(article["sources"],1)
    )
    paper=article.get('paper')
    paper_html=(f'<section class="paper-focus" aria-labelledby="paper-focus-title"><h2 id="paper-focus-title">Paper in focus</h2><p><a href="{esc(safe_url(paper["url"]))}" target="_blank" rel="noopener noreferrer">{esc(paper["title"])}</a></p><p>{esc(paper["authors"])} · {esc(paper["year"])} · {esc(paper["version"])}</p><p>Source-based editorial reading. Experimental results have not been independently reproduced by Quantum Observatory.</p></section>' if paper else '')
    related_html = "".join(article_card(item) for item in related[:3])
    body = f'''<article class="longform">
      <nav class="breadcrumbs" aria-label="Breadcrumb"><a href="/">Overview</a><span>/</span><a href="/{'analysis' if article['type'] == 'analysis' else 'guides'}/">{esc(article['type'].title())}</a></nav>
      <header class="article-header"><h1>{esc(article['title'])}</h1><p class="article-dek">{esc(article['description'])}</p><div class="article-byline"><span>By {esc(article['author'])}</span><span>Published <time datetime="{esc(article['published_at'])}">{date_label(article['published_at'])}</time></span><span>Updated <time datetime="{esc(article['updated_at'])}">{date_label(article['updated_at'])}</time></span></div></header>
      <aside class="article-summary"><strong>What this answers</strong><p>{esc(article['summary'])}</p></aside>
      {paper_html}
      <div class="article-body">{''.join(sections)}</div>
      <section class="references" aria-labelledby="references-title"><h2 id="references-title">Sources and further reading</h2><ol>{sources}</ol></section>
      <p class="correction-note">Found an error or a source we should consider? <a href="{esc(config['contact_url'])}" target="_blank" rel="noopener noreferrer">Open a correction request ↗</a>. Material changes are recorded with the article’s updated date.</p>
    </article><section class="related-editorial" aria-labelledby="related-title"><div class="section-heading"><div><h2 id="related-title">Continue reading</h2><p>Related guides and analysis from the observatory.</p></div></div><div class="editorial-grid">{related_html}</div></section>'''
    schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": article["title"],
        "description": article["description"],
        "datePublished": article["published_at"],
        "dateModified": article["updated_at"],
        "author": {"@type": "Organization", "name": article["author"]},
        "publisher": {"@type": "Organization", "name": config["publisher_name"]},
        "mainEntityOfPage": config["canonical_origin"].rstrip("/") + path,
    }
    return shell(config, title=article["title"], description=article["description"], body=body, active="analysis" if article["type"] == "analysis" else "guides", path=path, schema=schema)


def render_listing(config, articles, kind):
    plural = "analysis" if kind == "analysis" else "guides"
    title = "Research analysis" if kind == "analysis" else "Research reading guides"
    description = "Source-based readings of quantum research, alongside comparisons of the observatory’s corpus and its limits." if kind == "analysis" else "Practical ways to read quantum research claims, versions, benchmarks, and publication data."
    cards = "".join(article_card(article) for article in articles if article["type"] == kind)
    body = page_heading(title, description) + f'<div class="editorial-grid listing-grid">{cards}</div>'
    return shell(config, title=title, description=description, body=body, active=plural, path=f"/{plural}/")


def render_error_correction_topic(config,articles):
    readings=[a for a in articles if a.get('paper') and 'error-correction' in a.get('topics',[])]
    tasks={
        '2408.13687':('Repeated logical storage','Task, code distance, decoder conditions, and error denominator'),
        '2312.03982':('Encoded circuits and sampling','Encoding, output metric, acceptance rule, and attempted trials'),
        '2404.02280':('Encoded versus unencoded circuit outputs','Physical baseline, failure definition, and selection conditions'),
    }
    rows=''.join(f'<tr><th scope="row"><a href="{article_path(a)}">{esc(a["paper"]["authors"])}</a></th><td>{esc(tasks[a["paper_ids"][0]][0])}</td><td>{esc(tasks[a["paper_ids"][0]][1])}</td></tr>' for a in readings)
    body=page_heading('Quantum error correction: a reading path','Three source-based readings, selected to compare experimental questions rather than rank hardware.')
    body+='''<article class="policy-copy"><h2>Start with the experiment you need to understand</h2><p>This reading path is for readers who encounter claims about logical qubits and want to know which experimental task supports them. We select a memory demonstration, an encoded-circuit and sampling study, and an encoded-versus-unencoded circuit comparison. The selection is editorial: these are useful examples of different questions, not a complete survey, a list of the newest papers, or a quality ranking.</p><p>Before following a headline number, choose your own question. Are you studying how a stored state survives repeated correction, how a particular encoded circuit performs, or how a logical task compares with its physical baseline? Write the question down. Then use the corresponding reading below as a guide to the original paper’s methods.</p><h2>A comparison worksheet</h2><p>Each row identifies a reading question and the conditions we recommend carrying into a comparison. Open the analysis to find the original source, manuscript version, reported findings, and our interpretation.</p></article>'''
    body+=f'<p id="worksheet-scroll-hint" class="table-scroll-hint">Swipe the worksheet sideways to see all three columns. With a keyboard, focus the worksheet and use the left and right arrow keys.</p><div class="table-wrap topic-comparison" role="region" aria-labelledby="worksheet-caption" aria-describedby="worksheet-scroll-hint" tabindex="0"><table><caption id="worksheet-caption">Selected readings and comparison questions</caption><thead><tr><th scope="col">Paper authors</th><th scope="col">Reading question</th><th scope="col">Record alongside the claim</th></tr></thead><tbody>{rows}</tbody></table></div>'
    body+='''<article class="policy-copy"><h2>Use the worksheet instead of a single score</h2><p>For each candidate paper, record the measured output, error denominator, code or encoding, decoder, trial acceptance rule, and the baseline used. Preserve unknown fields. If two papers evaluate different tasks, explain the difference before calculating a ratio or comparing the numbers. Our recommended approach is to treat such studies as complementary evidence until a shared comparison is justified.</p><p>For example, a research meeting about memory scaling should begin with the storage protocol and its error definition. A meeting about retained sampling outputs should begin with the output metric and trial accounting. These suggested review workflows are our interpretation; they are not claims of independent reproduction or additional experimental capabilities.</p><h2>Explore beyond these selected readings</h2><p>The collected research library covers selected public sources and a recent collection window. These earlier papers provide context and may fall outside that window. Use publication years to locate periods in the library and citation order to trace indexed discussion. Missing coverage or a missing citation measurement should remain an uncertainty in your notes.</p><p><a href="/research/?week=all&amp;topic=error-correction&amp;kind=papers">Browse collected error-correction papers</a> · <a href="/guides/sorting-papers-without-ranking-quality/">Understand year and citation order</a> · <a href="/guides/comparing-error-correction-results/">Compare error-correction results</a></p></article>'''
    body+=reading_paths(readings)
    return shell(config,title='Quantum error correction: a reading path',description='A curated reading path comparing logical memory, encoded circuits, and physical baselines, with original sources and explicit limits.',body=body,active='analysis',path='/topics/error-correction/')


def research_item(record):
    kind = record["kind"].replace("_", " ").title()
    authors = ", ".join(record.get("authors", [])[:4]) or "Author metadata unavailable"
    citations=''
    if record['kind'] in {'preprint','journal_article','conference_paper'}:
        count=record.get('citations')
        citations=(f'<div class="item-citations"><span class="citation-count">{count:,} indexed citations</span><span>{esc(record.get("citations_source"))} · retrieved {date_label(record.get("citations_as_of"))}</span></div>' if count is not None else '<div class="item-citations"><span class="citation-missing">Citations not indexed</span></div>')
    return f'''<li class="research-item"><div class="item-date">{esc((record.get('date') or record.get('first_published') or 'Undated')[:10])}</div><div class="item-body"><div class="item-heading"><span class="kind-badge">{esc(kind)}</span><span class="item-source">{esc(record.get('venue') or record['source'])}</span></div><h3><a href="{esc(safe_url(record['url']))}" target="_blank" rel="noopener noreferrer">{esc(record['title'])}</a></h3><p class="item-authors">{esc(authors)}</p>{citations}</div><span class="item-open" aria-hidden="true">↗</span></li>'''


def render_dynamic(config, page, summary, records, manifest, articles):
    last_complete = next((w for w in summary["weeks"] if w["id"] == summary["last_complete_week"]), summary["weeks"][-2])
    available = sum(1 for source in manifest["sources"] if source.get("enabled") and source.get("kind") != "enrichment" and source.get("status") == "success")
    material = sum(1 for source in manifest["sources"] if source.get("enabled") and source.get("kind") != "enrichment")
    freshness = f'<div class="status-line"><span><span class="status-mark"></span>Last collected {date_label(summary["generated_at"])}</span><span>{available} of {material} collection sources available · <a href="/methodology/">View coverage</a></span></div>'
    if page == "overview":
        featured = articles[0]
        cards = "".join(article_card(a) for a in articles[:3])
        body = page_heading("Research overview", "A weekly view of quantum computing and quantum information research.") + freshness
        body += f'''<section class="stats" aria-label="Weekly statistics"><div class="stat"><div class="stat-label">New research</div><div class="stat-value">{last_complete['research']:,}</div><div class="stat-note">Unique linked works</div></div><div class="stat"><div class="stat-label">Conference talks</div><div class="stat-value">{last_complete['talks']:,}</div><div class="stat-note">Accepted contributions</div></div><div class="stat"><div class="stat-label">Reports</div><div class="stat-value">{last_complete['reports']:,}</div><div class="stat-note">Known dates only</div></div><div class="stat"><div class="stat-label">Active topics</div><div class="stat-value">{sum(v > 0 for v in last_complete['topics'].values())}</div><div class="stat-note">Topics can overlap</div></div></section>
        <section class="editorial-feature"><h2><a href="{article_path(featured)}">{esc(featured['title'])}</a></h2><p>{esc(featured['summary'])}</p><a class="text-link" href="{article_path(featured)}">Read the full analysis →</a></section>
        <section aria-labelledby="static-research"><div class="section-heading"><div><h2 id="static-research">Recent research</h2><p>Recent papers and reports from selected public sources. Follow each title to the original material.</p></div><a class="text-link" href="/research/">Explore all research ↗</a></div><div class="research-panel"><ol class="research-list">{''.join(research_item(r) for r in records[:10])}</ol></div></section>
        <section class="related-editorial" aria-labelledby="editorial-title"><div class="section-heading"><div><h2 id="editorial-title">Read the evidence</h2><p>Guides and analysis that explain how to interpret the index.</p></div></div><div class="editorial-grid">{cards}</div></section>'''
        title, desc, path = "Research overview", "Weekly quantum computing research, evidence-led analysis, and transparent coverage notes.", "/"
    elif page == "research":
        body = page_heading("Explore research", "Find papers, conference contributions, and reports, then follow each item to its original source.") + freshness
        body += library_introduction()
        body += f'''<p class="enhancement-note">Use the research library to compare publication years, trace indexed citations, and follow linked versions to their sources.</p><section aria-labelledby="research-heading"><div class="section-heading"><div><h2 id="research-heading">Research library</h2><p>Showing a recent sample from {len(records):,} source records.</p></div></div><div class="research-panel"><ol class="research-list">{''.join(research_item(r) for r in records[:20])}</ol></div></section>'''
        body += reading_paths(articles)
        title, desc, path = "Explore research", "Search and filter quantum computing papers, conference contributions, and reports with linked publication versions.", "/research/"
    elif page == "archive":
        weeks = "".join(f'<a class="archive-card" href="/?week={esc(w["id"])}"><span class="small-label">{esc(w["status"].replace("_", " "))}</span><h2>{week_label(w["id"])}</h2><div class="archive-count">{w["research"]:,}<span>research works</span></div><p>{w["talks"]} conference talks · {w["reports"]} reports</p></a>' for w in reversed(summary["weeks"]))
        body = page_heading("Weekly archive", "Return to a reporting period and explore its research.") + freshness + '<p class="chart-note archive-note">Historical periods can change when late-indexed publications or explicit version links are discovered.</p><div class="archive-grid">' + weeks + "</div>"
        title, desc, path = "Weekly archive", "Browse weekly quantum research counts and open each period in the research observatory.", "/archive/"
    else:
        source_items = "".join(f'<li><div class="source-head"><a href="{esc(safe_url(s["url"]))}" target="_blank" rel="noopener noreferrer">{esc(s["name"])} ↗</a><span class="source-status {esc(s["status"])}">{esc(s["status"].replace("_", " "))}</span></div><p>{esc(source_message(s))}</p></li>' for s in manifest["sources"])
        body = page_heading("Sources & methodology", "Understand what is collected, how it is counted, and where coverage ends.") + freshness
        body += f'''<div class="method-grid"><article class="prose"><h2>What this observatory measures</h2><p>Quantum Observatory follows selected public sources in quantum computing and quantum information. The current snapshot contains {summary['totals']['records']:,} source records grouped into {summary['totals']['research']:,} research works, plus conference contributions and reports. These counts describe this corpus, not all research worldwide.</p><h2>Research works and versions</h2><p>A research work is assigned to the week of its earliest known public appearance. An arXiv revision is not counted as a new paper. A journal record is grouped with a preprint only when an explicit DOI, arXiv identifier, or reviewed override connects them. Similar titles alone are not merged.</p><h2>Coverage before comparison</h2><p>A week runs from Monday 00:00 to the next Monday 00:00 in Korea Standard Time. Current periods, failed sources, and periods without matching coverage do not receive growth percentages. A failed source is missing coverage, not evidence that no research appeared.</p><h2>Topic classification</h2><p>Eight published keyword dictionaries classify titles and available abstracts. A work can receive more than one topic, so topic totals and shares overlap. These rules support discovery; they are not judgments of scientific quality.</p><h2>Conference and report limits</h2><p>Conference entries describe accepted contributions and do not prove that a presentation occurred. Report dates are used only when a source supplies them. Upload paths are not interpreted as publication dates, and undated records remain discoverable only in all-date views.</p><h2>Years and indexed citations</h2><p>Publication year is the earliest known public year of a linked work. Partial journal years are kept without inventing a day. Citation sorting uses one measurement per work: OpenAlex when available, otherwise Crossref. Counts show their provider and actual retrieval date; source coverage differs and unknown counts are not zeros. The bounded enrichment budget refreshes the oldest DOI snapshots first.</p><p><a href="/guides/sorting-papers-without-ranking-quality/">Read the sorting guide</a> before interpreting the order as evidence.</p><h2>Reproducibility</h2><p>Source checkpoints, stable identifiers, classification rules, run manifests, and content hashes are preserved. The <a href="/guides/reproducing-an-observatory-comparison/">reproducibility guide</a> explains how to export a view and record its limits.</p><p><a href="/data/summary.json">Download statistics JSON</a> · <a href="/data/manifest.json">View collection manifest</a></p></article><aside><section class="panel"><div class="panel-heading"><div><h2>Source coverage</h2><p>Latest collection attempt</p></div></div><ul class="source-list">{source_items}</ul></section></aside></div>'''
        title, desc, path = "Sources & methodology", "How Quantum Observatory collects, links, classifies, and counts quantum research, including known coverage limits.", "/methodology/"
    return shell(config, title=title, description=desc, body=f'<div id="app">{body}</div><noscript><p class="notice">Interactive search and filters require JavaScript. The page content and source links above remain available.</p></noscript>', active=page, path=path, dynamic=True)


def render_policy_page(config, slug):
    contact = esc(config["contact_url"])
    repo = esc(config["repository_url"])
    pages = {
        "about": ("About Quantum Observatory", "What the observatory does, who publishes it, and where its claims stop.", '''<div class="policy-copy"><p>Quantum Observatory is an independent, open research index for quantum computing and quantum information. It combines source-linked scholarly metadata with practical guides and evidence-led analysis.</p><h2>What we publish</h2><p>The research library helps readers find papers, conference contributions, and public reports. Editorial articles include source-based readings of specific papers, practical comparison worksheets, and guides to versions, counts, and benchmarks. We do not reproduce publisher PDFs or present automated topic tags as scientific evaluation.</p><h2>Who is responsible</h2><p>Quantum Observatory is the publication byline and the maintainer of this site. The public repository is maintained under the GitHub account <a href="https://github.com/seokjw0727" target="_blank" rel="noopener noreferrer">seokjw0727</a>. That byline identifies the publisher; it does not claim a university affiliation, professional credential, or independent peer review. The source repository exposes the collection and counting rules so readers can inspect how results are produced.</p><h2>Independence</h2><p>The site is not affiliated with arXiv, Crossref, QIP, the U.S. government, journals, or the researchers whose work appears in the index. External names and links identify sources. No ranking or inclusion should be read as an endorsement.</p><p><a href="/editorial-policy/">Read the editorial policy</a> or <a href="''' + contact + '''" target="_blank" rel="noopener noreferrer">report an error ↗</a>.</p></div>'''),
        "contact": ("Contact and corrections", "How to report a factual error, broken source, privacy concern, or data correction.", '''<div class="policy-copy"><p>The public issue tracker is the contact channel for Quantum Observatory. Use it for factual corrections, missing links, duplicate records, accessibility problems, and questions about this site’s data or policies.</p><p><a class="button primary" href="''' + contact + '''" target="_blank" rel="noopener noreferrer">Open a GitHub issue ↗</a></p><h2>Before you submit</h2><p>Include the affected page, the statement or record that needs attention, and a primary source when one is available. Do not include private, confidential, or sensitive personal information: issue reports are public on GitHub.</p><h2>What happens next</h2><p>Reports are checked against the cited source and the stored record. Material editorial corrections update the article date; metadata corrections are recorded through the project’s reviewable override process. A source’s own metadata may remain unchanged even when this site adds a clarification.</p><h2>Privacy requests</h2><p>The site has no contact form or user account. For a privacy concern, describe only what is necessary in the issue. If a public issue would disclose sensitive information, use GitHub’s repository-owner contact options without posting the data publicly.</p></div>'''),
        "editorial-policy": ("Editorial policy", "How Quantum Observatory selects sources, checks claims, uses automation, and records corrections.", '''<div class="policy-copy"><h2>Purpose</h2><p>Editorial work should help a reader judge evidence, reproduce a comparison, or understand where a claim stops. Articles must add analysis rather than restating abstracts or replacing the original paper.</p><h2>Sources and attribution</h2><p>Claims are traced to primary papers, official documentation, or the observatory’s versioned dataset whenever possible. Links do not transfer copyright. We quote sparingly, write explanations in our own words, and do not republish figures or full abstracts unless their terms clearly permit it.</p><h2>Review and uncertainty</h2><p>Before release, an article is checked for working sources, internally consistent dates and quantities, clear separation between reported results and our interpretation, and visible limitations. A Quantum Observatory byline identifies the publisher and is not a claim of academic peer review or professional certification.</p><h2>Automation and AI</h2><p>Software collects metadata, links records using explicit identifiers, calculates aggregates, and applies published topic rules. Automated output cannot silently become editorial judgment. If generative tools assist drafting or code, the maintainer remains responsible for checking every published claim and source.</p><h2>Conflicts and commercial influence</h2><p>Source inclusion, editorial conclusions, and corrections are not sold. If sponsorship, affiliate links, or another material relationship is introduced, it must be disclosed beside the affected content. Advertising, if enabled later, will be visually separate and will not determine coverage.</p><h2>Source-based research readings</h2><p>Paper readings identify their original source and manuscript version. Reported experimental findings are separated from our interpretation and illustrative exercises. The Quantum Observatory byline identifies the publication; these readings do not claim independent experimental reproduction or peer review.</p><h2>Corrections</h2><p>Material corrections change the visible updated date and preserve an explanation when the original conclusion is affected. Metadata fixes remain attributable to their source or to a documented local override. Send a correction through the <a href="''' + contact + '''" target="_blank" rel="noopener noreferrer">public issue tracker ↗</a>.</p></div>'''),
        "privacy": ("Privacy policy", "The data this site stores, the services that process requests, and the current advertising status.", '''<div class="policy-copy"><p><strong>Effective: September 6, 2026.</strong> This policy describes the current public build of Quantum Observatory.</p><h2>Information handled by this site</h2><p>Quantum Observatory does not provide user accounts, a contact form, or an email newsletter. The browser stores one preference, <code>qo-theme</code>, in local storage so the light or dark theme can persist. The value stays on the device and is not sent to the site by application code.</p><h2>Hosting logs</h2><p>The site is delivered through Cloudflare Pages. Like other web hosts and network providers, Cloudflare may process request data such as IP address, browser information, requested URL, timestamps, and security signals to deliver and protect the service. Quantum Observatory does not currently run a separate audience analytics product.</p><h2>External links</h2><p>Links to papers, public agencies, and GitHub take readers to services with their own privacy practices. The public contact channel is GitHub Issues; anything submitted there can be public and is processed under GitHub’s terms and privacy statement.</p><h2>Advertising status</h2><p>This build does not load Google AdSense or another advertising network. It therefore does not set advertising cookies through site code. Before advertising is enabled, this policy will be updated to describe Google’s data use, applicable cookies or identifiers, and consent choices. Where required, a Google-certified consent platform will be used before personalized advertising requests.</p><h2>Your choices</h2><p>You can remove the saved theme preference through your browser’s site-data controls. You can browse the editorial pages without enabling JavaScript; interactive research filters require it. Privacy questions can be raised through the <a href="''' + contact + '''" target="_blank" rel="noopener noreferrer">public issue tracker ↗</a> without including sensitive information.</p></div>'''),
        "terms": ("Terms of use", "Terms for using the site, research metadata, downloads, and editorial material.", '''<div class="policy-copy"><p><strong>Effective: September 6, 2026.</strong> By using Quantum Observatory, you agree to use the service lawfully and to respect the rights attached to source material.</p><h2>Research information</h2><p>The site is an index and explanatory publication, not scientific, legal, financial, or investment advice. Metadata can be incomplete, delayed, or corrected. Follow the original source before relying on a result, and do not treat topic labels, counts, or citation metadata as an assessment of research quality.</p><h2>Copyright and source rights</h2><p>Quantum Observatory’s original explanatory text and code are distinct from third-party paper titles, author names, abstracts, identifiers, and linked materials. Those materials remain subject to their sources’ terms and applicable law. A link or citation does not grant permission to redistribute the underlying work.</p><h2>Downloads and automation</h2><p>CSV and JSON downloads are provided for research and verification. Use them in a way that does not overload the site or evade limits imposed by upstream sources. Preserve source attribution when presenting derived results.</p><h2>Availability and changes</h2><p>The service is provided without a guarantee of uninterrupted availability or complete coverage. Routes, data sources, and these terms may change as the project develops. Material policy changes receive a new effective date.</p><h2>Questions</h2><p>Review the <a href="/methodology/">methodology</a>, inspect the <a href="''' + repo + '''" target="_blank" rel="noopener noreferrer">source repository ↗</a>, or use the <a href="''' + contact + '''" target="_blank" rel="noopener noreferrer">public issue tracker ↗</a>.</p></div>'''),
    }
    title, description, content = pages[slug]
    body = page_heading(title, description, eyebrow="QUANTUM OBSERVATORY") + content
    return shell(config, title=title, description=description, body=body, active="", path=f"/{slug}/")


def write_page(root, route, value):
    path = Path(root) / route / "index.html" if route else Path(root) / "index.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
