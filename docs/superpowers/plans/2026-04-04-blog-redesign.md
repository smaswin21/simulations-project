# Blog Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite `blog/index.html` and `blog/site.css` to a classic academic research page style matching the approved design.

**Architecture:** Pure static HTML + CSS — no build tools, no JS framework. The HTML is rewritten top-to-bottom following the approved section order. The CSS is rewritten to use Georgia serif, a centered max-width column, and new utility classes for the video grid, diagram sections, and results grid.

**Tech Stack:** HTML5, CSS3 (no dependencies)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `blog/index.html` | Rewrite | Page structure and content |
| `blog/site.css` | Rewrite | All visual styling |

---

### Task 1: Rewrite `blog/index.html`

**Files:**
- Modify: `blog/index.html`

- [ ] **Step 1: Replace the full contents of `blog/index.html`**

Open `blog/index.html` and replace everything with:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta
      name="description"
      content="Heterogeneous MASTOC — a research project on memory, coordination, and commons governance in multi-agent simulation."
    />
    <title>TITLE</title>
    <link rel="stylesheet" href="site.css" />
  </head>
  <body>
    <main class="page">

      <!-- HERO -->
      <header class="hero">
        <h1>TITLE</h1>
        <p class="hero-author">
          <a href="https://www.linkedin.com/in/aswin-subramanian-maheswaran/" target="_blank" rel="noopener">Aswin Subramanian Maheswaran</a>
          &nbsp;&middot;&nbsp; IE University
        </p>
        <div class="button-row">
          <a href="#">Paper</a>
          <a href="https://github.com/" target="_blank" rel="noopener">Code ↗</a>
        </div>
      </header>

      <!-- VIDEOS -->
      <section class="section video-section" aria-label="Simulation videos">
        <div class="video-grid">
          <figure class="video-figure">
            <video controls>
              <source src="assets/simulation_run1.mp4" type="video/mp4" />
              Your browser does not support the video tag.
            </video>
            <figcaption>Simulation Run 1</figcaption>
          </figure>
          <figure class="video-figure">
            <video controls>
              <source src="assets/simulation_run2.mp4" type="video/mp4" />
              Your browser does not support the video tag.
            </video>
            <figcaption>Simulation Run 2</figcaption>
          </figure>
        </div>
      </section>

      <!-- ARCHITECTURE -->
      <section class="section diagram-section" id="architecture">
        <h2>Architecture</h2>
        <img
          src="assets/architecture.png"
          alt="Layered architecture diagram of the Heterogeneous MASTOC system."
          class="diagram-img"
        />
        <p class="diagram-caption">
          The system is organized in three layers: the agent layer (herders, regulator, scout), the memory layer (per-agent episodic and semantic stores), and the commons layer (shared resource pool with enforcement mechanics). Each agent is backed by an LLM and queries its own memory before acting each round.
        </p>
      </section>

      <!-- ABSTRACT -->
      <section class="section abstract-section" id="abstract">
        <h2>Abstract</h2>
        <p>
          This project models a shared pasture where herders, regulators, and a scout operate
          under different pressures. Some agents extract early, some monitor, and some try to
          stabilize the group through public signals. The core question is simple: can a commons
          remain fair and sustainable when agents remember past behavior instead of treating each
          round as socially blank?
        </p>
      </section>

      <!-- SIMULATION LOOP -->
      <section class="section diagram-section" id="simulation-loop">
        <h2>Simulation Loop</h2>
        <img
          src="assets/simulation_loop.png"
          alt="Diagram of the simulation loop showing per-round agent decision flow."
          class="diagram-img"
        />
        <p class="diagram-caption">
          Each round, agents observe the current commons state, query their memory for relevant past interactions, generate a speech act, and then submit an extraction decision. The regulator reviews extraction totals and may issue penalties. Memory is updated at the end of each round with the round's outcomes.
        </p>
      </section>

      <!-- RESULTS -->
      <section class="section results-section" id="results">
        <h2>Results</h2>
        <div class="results-grid">
          <figure>
            <img src="assets/plot1.png" alt="Result plot 1." />
          </figure>
          <figure>
            <img src="assets/plot2.png" alt="Result plot 2." />
          </figure>
          <figure>
            <img src="assets/plot3.png" alt="Result plot 3." />
          </figure>
          <figure>
            <img src="assets/plot4.png" alt="Result plot 4." />
          </figure>
        </div>
      </section>

    </main>
  </body>
</html>
```

- [ ] **Step 2: Verify HTML structure in browser**

Open `blog/index.html` directly in a browser (File → Open). Confirm:
- Title shows "TITLE"
- Author line appears below the title with a blue LinkedIn link
- Two dark pill buttons render side by side
- Two video placeholders appear side by side (broken video icon is expected — no assets yet)
- Architecture, Abstract, Simulation Loop, Results headings all appear in order

- [ ] **Step 3: Commit**

```bash
git add blog/index.html
git commit -m "feat: rewrite blog HTML to academic research page layout"
```

---

### Task 2: Rewrite `blog/site.css`

**Files:**
- Modify: `blog/site.css`

- [ ] **Step 1: Replace the full contents of `blog/site.css`**

```css
/* ── Reset & base ─────────────────────────────────── */
html {
  scroll-behavior: smooth;
}

body {
  margin: 0;
  background: #fcfcfc;
  color: #303030;
  font-family: Georgia, "Times New Roman", serif;
  line-height: 1.75;
}

img,
video {
  display: block;
  max-width: 100%;
}

a {
  color: #2380e8;
  text-decoration: none;
}

a:hover {
  text-decoration: underline;
}

/* ── Page column ──────────────────────────────────── */
.page {
  width: min(860px, calc(100% - 40px));
  margin: 0 auto;
  padding: 40px 0 80px;
}

/* ── Hero ─────────────────────────────────────────── */
.hero {
  text-align: center;
  padding-bottom: 32px;
  border-bottom: 1px solid #e8e8e8;
}

.hero h1 {
  margin: 0 auto 12px;
  max-width: 720px;
  font-size: clamp(1.8rem, 4vw, 2.6rem);
  font-weight: 700;
  line-height: 1.15;
  letter-spacing: -0.01em;
  font-family: Georgia, serif;
}

.hero-author {
  margin: 0 0 20px;
  font-size: 1rem;
  color: #555;
  font-family: Georgia, serif;
}

.hero-author a {
  color: #2380e8;
}

/* ── Buttons ──────────────────────────────────────── */
.button-row {
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: 10px;
}

.button-row a {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 100px;
  padding: 10px 20px;
  border-radius: 999px;
  background: #222;
  color: #fff;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: 0.95rem;
  font-weight: 500;
}

.button-row a:hover {
  background: #000;
  text-decoration: none;
}

/* ── Sections ─────────────────────────────────────── */
.section {
  margin-top: 64px;
}

.section h2 {
  margin: 0 0 24px;
  text-align: center;
  font-size: 1.9rem;
  font-weight: 700;
  letter-spacing: -0.015em;
  font-family: Georgia, serif;
}

/* ── Videos ───────────────────────────────────────── */
.video-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.video-figure {
  margin: 0;
}

.video-figure video {
  width: 100%;
  border: 1px solid #ddd;
  background: #000;
  border-radius: 4px;
}

.video-figure figcaption {
  margin-top: 6px;
  text-align: center;
  font-size: 0.88rem;
  color: #777;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

/* ── Diagram sections ─────────────────────────────── */
.diagram-img {
  width: 100%;
  border: 1px solid #e0e0e0;
  background: #fff;
  border-radius: 4px;
}

.diagram-caption {
  margin: 14px auto 0;
  max-width: 720px;
  font-size: 0.93rem;
  color: #555;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  line-height: 1.65;
}

/* ── Abstract ─────────────────────────────────────── */
.abstract-section p {
  margin: 0 auto;
  max-width: 720px;
  font-size: 1rem;
  color: #3d3d3d;
  line-height: 1.8;
}

/* ── Results ──────────────────────────────────────── */
.results-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.results-grid figure {
  margin: 0;
}

.results-grid img {
  width: 100%;
  border: 1px solid #e0e0e0;
  background: #fff;
  border-radius: 4px;
}

/* ── Responsive ───────────────────────────────────── */
@media (max-width: 640px) {
  .page {
    width: calc(100% - 28px);
    padding-top: 24px;
  }

  .video-grid,
  .results-grid {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 2: Verify styles in browser**

Reload `blog/index.html`. Confirm:
- Serif font throughout headings and body
- Title is large and centered
- Author line is smaller, gray, LinkedIn link is blue
- Paper / Code buttons are dark pills, centered
- Video grid is side-by-side on desktop, stacked on narrow viewport
- Section headings are centered
- Results grid is 2×2 on desktop, stacked on narrow viewport

- [ ] **Step 3: Commit**

```bash
git add blog/site.css
git commit -m "feat: rewrite blog CSS to academic serif style with video and results grids"
```

---

### Task 3: Update meta description and page title

**Files:**
- Modify: `blog/index.html` (head section only)

This task is already complete if Task 1 was followed exactly — the `<title>` is `TITLE` and the meta description is updated. Verify and commit only if you made any corrections.

- [ ] **Step 1: Confirm `<title>` reads `TITLE` and meta description is updated**

In `blog/index.html` lines 7–10, confirm:
```html
<title>TITLE</title>
```
and the description meta tag does not mention "commons governance, architecture" (old copy).

- [ ] **Step 2: Commit if any correction was needed**

```bash
git add blog/index.html
git commit -m "fix: update page title and meta description"
```

---

### Task 4: Smoke-test full page

- [ ] **Step 1: Open in browser and walk through every section**

Open `blog/index.html` in Chrome or Firefox. Check each section top to bottom:

| Section | Expected |
|---|---|
| Hero | Title "TITLE", author with LinkedIn link, two dark pill buttons |
| Videos | Two side-by-side video elements (broken source is OK) |
| Architecture | `<h2>Architecture</h2>`, broken image placeholder, description paragraph |
| Abstract | `<h2>Abstract</h2>`, paragraph at readable width |
| Simulation Loop | `<h2>Simulation Loop</h2>`, broken image placeholder, description paragraph |
| Results | `<h2>Results</h2>`, 2×2 grid of broken image placeholders |

- [ ] **Step 2: Resize browser to < 640px width**

Confirm video grid and results grid collapse to single column.

- [ ] **Step 3: Click LinkedIn link**

Confirm it opens `https://www.linkedin.com/in/aswin-subramanian-maheswaran/` in a new tab.

- [ ] **Step 4: Final commit**

```bash
git add blog/index.html blog/site.css
git commit -m "feat: blog redesign complete — academic style with videos, diagrams, results"
```
