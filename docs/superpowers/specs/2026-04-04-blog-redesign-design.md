# Blog Redesign Design Spec
Date: 2026-04-04

## Goal

Redesign `blog/index.html` and `blog/site.css` to match a classic academic research project page style, inspired by https://locross93.github.io/HM-Website/.

---

## Hero Section

- **Title**: `TITLE` (placeholder — will be replaced with final paper title)
- **Author line** (below title): `Aswin Subramanian Maheswaran` as a clickable LinkedIn link · `IE University` as plain text
- **Buttons**: `Paper` and `Code ↗` — pill-shaped dark buttons, centered, same row
- Typography: Georgia serif, centered, clean academic feel

---

## Section Order

1. Hero (title, author, buttons)
2. Videos (2×1 grid)
3. Architecture (diagram + description)
4. Abstract
5. Simulation Loop (diagram + description)
6. Results (4 plots, 2×2 grid)

---

## Section Details

### Videos
- Two `<video>` players side by side (1fr 1fr grid)
- Placeholder labels: "Simulation Run 1", "Simulation Run 2"
- No autoplay; native browser controls

### Architecture
- `<h2>Architecture</h2>`
- Image placeholder for layered architecture diagram (`assets/architecture.png`)
- Short description paragraph below the image (placeholder text)

### Abstract
- `<h2>Abstract</h2>`
- Existing placeholder paragraph text, max-width ~760px, centered

### Simulation Loop
- `<h2>Simulation Loop</h2>`
- Image placeholder for simulation loop diagram (`assets/simulation_loop.png`)
- Short description paragraph below (placeholder text)

### Results
- `<h2>Results</h2>`
- 2×2 grid of four `<img>` placeholders (`assets/plot1.png` … `assets/plot4.png`)

---

## Typography & Style

- Font: Georgia, serif for headings and body (academic feel)
- Body background: `#fcfcfc`
- Body text: `#303030`
- Author link color: `#2380e8`
- Section headings: centered, `font-size: ~2rem`, `font-weight: 700`
- Buttons: `background: #222`, white text, `border-radius: 999px`, padding `10px 20px`
- Max content width: `860px`, centered

---

## Files Changed

- `blog/index.html` — full rewrite of structure
- `blog/site.css` — update to add Georgia serif, video grid, results grid; keep existing utility classes where still applicable

---

## What Is NOT Changing

- `blog/assets/` directory structure (existing images remain)
- URL/path of the blog page
- Any Python/simulation code
