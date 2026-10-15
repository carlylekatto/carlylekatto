#!/usr/bin/env python3
"""
Generate Material 3 GitHub Stats & Activity Graph SVG Components
100% native in-repo script using Python standard library.
Calculates:
  1. components/stats/stats.svg (Streak & Contributions with Milestone Tiers)
  2. components/activity-graph/activity-graph.svg (Detailed 31-day Coordinate Grid Activity Graph)
"""

import os
import re
import sys
import urllib.request
from datetime import datetime, date, timedelta

USERNAME = os.getenv("GITHUB_USER", "carlylekatto")
REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATS_SVG_PATH = os.path.join(REPO_DIR, "components", "stats", "stats.svg")
GRAPH_SVG_PATH = os.path.join(REPO_DIR, "components", "activity-graph", "activity-graph.svg")

def fetch_contributions_for_year(username, year):
    """Fetch calendar HTML for a specific year and return {date_str: count}."""
    if year == date.today().year:
        url = f"https://github.com/users/{username}/contributions"
    else:
        url = f"https://github.com/users/{username}/contributions?from={year}-12-01&to={year}-12-31"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    day_counts = {}
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8")
        
        # High precision parser matching each cell component ID with its tooltip
        for m in re.finditer(r'data-date="(\d{4}-\d{2}-\d{2})"[^>]*id="([^"]+)"', html):
            date_str, comp_id = m.groups()
            tt_match = re.search(r'<tool-tip[^>]*for="' + re.escape(comp_id) + r'"[^>]*>(\d+|No)\s+contribution', html)
            if tt_match:
                count = 0 if tt_match.group(1) == "No" else int(tt_match.group(1))
                day_counts[date_str] = count
    except Exception as e:
        print(f"Warning: Failed to fetch data for year {year}: {e}", file=sys.stderr)
    return day_counts

def fmt_date(d_str, include_year=True):
    """Format 'YYYY-MM-DD' to 'Mmm DD, YYYY' or 'Mmm DD'."""
    dt = datetime.strptime(d_str, "%Y-%m-%d")
    return dt.strftime("%b %d, %Y") if include_year else dt.strftime("%b %d")

def get_streak_tier(streak):
    """Assign milestone tier and badge based on current streak count."""
    if streak >= 30:
        return "tier-supernova", "👑 Supernova"
    elif streak >= 14:
        return "tier-inferno", "🔮 Inferno"
    elif streak >= 7:
        return "tier-blaze", "🔥 Blaze"
    elif streak >= 3:
        return "tier-spark", "⚡ Spark"
    else:
        return "tier-dormant", "Rest Mode"

def monotone_cubic_bezier(pts, y_base=220.0):
    """
    Convert a sequence of (x, y) points into a monotonic cubic Bezier path (PCHIP / Fritsch-Carlson).
    Guarantees:
      1. Zero overshoot at local extrema: the peak point is the EXACT crest/apex of the curve.
      2. Perfect alignment with data dots: highlight dot sits dead-center on the peak.
      3. Perfectly flat baseline on consecutive 0-contribution days.
    """
    n = len(pts)
    if n < 2:
        return ""
    if n == 2:
        return f"M {pts[0][0]:.1f} {pts[0][1]:.1f} L {pts[1][0]:.1f} {pts[1][1]:.1f}"
    
    # Calculate secants (slopes between adjacent points)
    dxs = [pts[k+1][0] - pts[k][0] for k in range(n-1)]
    dys = [pts[k+1][1] - pts[k][1] for k in range(n-1)]
    slopes = [dys[k] / dxs[k] if dxs[k] != 0 else 0.0 for k in range(n-1)]
    
    # Calculate tangents (PCHIP condition: zero slope at peaks/valleys)
    m = [0.0] * n
    for k in range(1, n-1):
        s0 = slopes[k-1]
        s1 = slopes[k]
        if s0 * s1 <= 0:
            # Local peak, valley, or flat plateau -> horizontal tangent!
            m[k] = 0.0
        else:
            # Harmonic mean for strict monotonicity without overshoot
            m[k] = 2.0 * s0 * s1 / (s0 + s1)
            
    m[0] = slopes[0] if len(slopes) > 0 and slopes[0] * m[1] > 0 else 0.0
    m[-1] = slopes[-1] if len(slopes) > 0 and slopes[-1] * m[-2] > 0 else 0.0
    
    # Construct cubic Bezier SVG path
    d = [f"M {pts[0][0]:.1f} {pts[0][1]:.1f}"]
    for k in range(n-1):
        h = dxs[k]
        p1 = pts[k]
        p2 = pts[k+1]
        
        # When both points are flat on baseline or plateau, draw straight line
        if abs(p1[1] - p2[1]) < 0.01 and abs(m[k]) < 0.01 and abs(m[k+1]) < 0.01:
            d.append(f"L {p2[0]:.1f} {p2[1]:.1f}")
            continue
            
        cp1x = p1[0] + h / 3.0
        cp1y = p1[1] + m[k] * h / 3.0
        cp2x = p2[0] - h / 3.0
        cp2y = p2[1] - m[k+1] * h / 3.0
        
        # Clamp to avoid dipping below y_base
        cp1y = min(cp1y, y_base)
        cp2y = min(cp2y, y_base)
        
        d.append(f"C {cp1x:.1f} {cp1y:.1f}, {cp2x:.1f} {cp2y:.1f}, {p2[0]:.1f} {p2[1]:.1f}")
        
    return " ".join(d)

def get_y_ticks(max_val):
    """
    Calculate round ticks for the Y-axis with a FIXED number of intervals (7 rows).
    This guarantees that with dx == dy, every grid cell is ALWAYS 100% square.
    """
    if max_val <= 7:
        step = 1
    elif max_val <= 14:
        step = 2
    elif max_val <= 21:
        step = 3
    elif max_val <= 35:
        step = 5
    elif max_val <= 70:
        step = 10
    else:
        raw_step = (max_val + 6) // 7
        step = ((raw_step + 4) // 5) * 5
    top = step * 7
    ticks = [i * step for i in range(8)]
    return ticks, top, step

def generate_activity_graph_svg(last_31_days, day_counts):
    """Generate detailed Activity Graph with a completely square grid."""
    data = [(d, day_counts.get(d, 0)) for d in last_31_days]
    counts = [c for _, c in data]
    max_count = max(counts) if counts else 0
    
    ticks, top_val, step = get_y_ticks(max_count)
    
    # Square Grid Dimensions: dx == dy == 23.0px
    cell_size = 23.0
    dx = cell_size
    dy = cell_size
    
    num_pts = len(data)  # 31 data points (days 0..30)
    num_cols = 31        # 31 column intervals (32 grid lines, includes 1 extra right column)
    num_rows = 7         # 7 row intervals (8 grid lines)
    
    x_start = 65.0
    x_grid_end = x_start + num_cols * dx  # 65.0 + 31 * 23.0 = 778.0
    y_base = 220.0
    y_top = y_base - num_rows * dy        # 220.0 - 7 * 23.0 = 59.0
    y_height = y_base - y_top
    
    # Generate Horizontal Grid Lines and Y-axis Tick Numbers
    h_lines = []
    y_labels = []
    for val in ticks:
        y = y_base - (val / top_val) * y_height
        h_lines.append(f'<line x1="{x_start:.1f}" y1="{y:.1f}" x2="{x_grid_end:.1f}" y2="{y:.1f}" class="grid-line" stroke-dasharray="3, 3" />')
        y_labels.append(f'<text x="56" y="{y + 4:.1f}" class="axis-tick-y">{val}</text>')
    
    h_lines_str = "\n    ".join(h_lines)
    y_labels_str = "\n    ".join(y_labels)
    
    # Generate Vertical Grid Lines (32 lines total, covering full width)
    v_lines = []
    for j in range(num_cols + 1):
        x = x_start + j * dx
        v_lines.append(f'<line x1="{x:.1f}" y1="{y_top:.1f}" x2="{x:.1f}" y2="{y_base:.1f}" class="grid-line" stroke-dasharray="3, 3" />')
    v_lines_str = "\n    ".join(v_lines)
    
    # Generate X-axis Day Numbers and Data Points
    x_labels = []
    pts = []
    highest_c = -1
    peak_idx = -1
    
    for i, (d_str, c) in enumerate(data):
        x = x_start + i * dx
        y = y_base - (c / top_val) * y_height
        pts.append((x, y, d_str, c))
        if c > highest_c:
            highest_c = c
            peak_idx = i
            
        day_num = str(int(d_str.split('-')[2]))
        x_labels.append(f'<text x="{x:.1f}" y="241" class="axis-tick-x">{day_num}</text>')
    
    x_labels_str = "\n    ".join(x_labels)
    
    # Generate Spline Line and Dots
    line_path = monotone_cubic_bezier([(p[0], p[1]) for p in pts], y_base=y_base)
    
    dots_svg = []
    for i, (x, y, d_str, c) in enumerate(pts):
        is_peak = (i == peak_idx and highest_c > 0)
        dot_r = 5.0 if is_peak else 3.5
        dot_class = "data-dot-peak" if is_peak else "data-dot"
        dots_svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{dot_r}" class="{dot_class}"><title>{d_str}: {c} contributions</title></circle>')
    
    dots_str = "\n    ".join(dots_svg)

    svg_template = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 280" width="100%" height="280" fill="none">
  <defs>
    <style>
      :root {{
        /* Light Theme */
        --md-sys-color-surface-container: #F7F2FA;
        --md-sys-color-outline-variant: #D0C9D6;
        --md-sys-color-on-surface: #1D1B20;
        --md-sys-color-outline: #79747E;
        --graph-line: #0077B6;
        --graph-point: #0096C7;
        --graph-point-stroke: #FFFFFF;
        --grid-line-color: rgba(121, 116, 126, 0.22);
      }}

      @media (prefers-color-scheme: dark) {{
        :root {{
          /* Dark Theme */
          --md-sys-color-surface-container: #1E1A22;
          --md-sys-color-outline-variant: #3B3442;
          --md-sys-color-on-surface: #E6E0E9;
          --md-sys-color-outline: #938F99;
          --graph-line: #38BDF8;
          --graph-point: #38BDF8;
          --graph-point-stroke: #1E1A22;
          --grid-line-color: rgba(147, 143, 153, 0.20);
        }}
      }}

      /* Base Surface Card */
      .m3-surface {{
        fill: transparent;
        stroke: none;
      }}

      /* Title */
      .chart-title {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        font-size: 16px;
        font-weight: 700;
        letter-spacing: 0.15px;
        fill: var(--md-sys-color-on-surface);
        text-anchor: middle;
      }}

      .axis-title {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.2px;
        fill: var(--md-sys-color-on-surface);
        text-anchor: middle;
      }}

      .axis-tick-y {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        font-size: 11px;
        font-weight: 700;
        fill: var(--md-sys-color-on-surface);
        text-anchor: end;
      }}

      .axis-tick-x {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        font-size: 11px;
        font-weight: 700;
        fill: var(--md-sys-color-on-surface);
        text-anchor: middle;
      }}

      /* Grid Lines */
      .grid-line {{
        stroke: var(--grid-line-color);
        stroke-width: 1px;
      }}

      /* Curve and Points */
      .activity-curve {{
        stroke: var(--graph-line);
        stroke-width: 3.2px;
        stroke-linecap: round;
        stroke-linejoin: round;
        fill: none;
      }}

      .data-dot {{
        fill: var(--graph-point);
        stroke: var(--graph-point-stroke);
        stroke-width: 1.5px;
        cursor: pointer;
        transition: r 0.2s ease;
      }}

      .data-dot:hover {{
        r: 5.5px;
      }}

      .data-dot-peak {{
        fill: var(--graph-point);
        stroke: var(--graph-point-stroke);
        stroke-width: 2px;
        cursor: pointer;
        filter: drop-shadow(0 0 4px var(--graph-line));
      }}
    </style>
  </defs>

  <!-- M3 Surface Container (800x280, rx=28) -->
  <rect x="1" y="1" width="798" height="278" rx="28" class="m3-surface" />

  <!-- ==================== TOP TITLE ==================== -->
  <text x="400" y="38" class="chart-title">Katt's Contribution Graph</text>

  <!-- ==================== 2D GRID ==================== -->
  <!-- Horizontal Grid Lines -->
  <g id="h-grid">
    {h_lines_str}
  </g>

  <!-- Vertical Grid Lines -->
  <g id="v-grid">
    {v_lines_str}
  </g>

  <!-- ==================== AXIS LABELS ==================== -->
  <!-- Y-Axis Rotated Title and Numbers -->
  <text x="24" y="142" class="axis-title" transform="rotate(-90, 24, 142)">Contributions</text>
  <g id="y-ticks">
    {y_labels_str}
  </g>

  <!-- X-Axis Day Numbers and 'Days' Label -->
  <g id="x-ticks">
    {x_labels_str}
  </g>
  <text x="421.5" y="265" class="axis-title">Days</text>

  <!-- ==================== CURVE AND DATA POINTS ==================== -->
  <!-- Spline Curve -->
  <path d="{line_path}" class="activity-curve" />

  <!-- All 31 Data Points -->
  <g id="data-points">
    {dots_str}
  </g>
</svg>"""
    return svg_template

def calculate_stats(username):
    """Calculate all-time total contributions, streaks, date ranges and milestone tier."""
    all_days = {}
    current_year = date.today().year

    # GitHub account created in 2021
    for year in range(2021, current_year + 1):
        days = fetch_contributions_for_year(username, year)
        all_days.update(days)

    if not all_days:
        print("Error: No contribution data retrieved.", file=sys.stderr)
        return None

    sorted_dates = sorted(all_days.keys())
    total_contributions = sum(all_days.values())

    first_date = "2021-11-28"
    total_range = f"{fmt_date(first_date)} – Present"

    # Calculate longest streak with start/end date range
    longest_streak = 0
    best_start = None
    best_end = None

    cur_streak = 0
    cur_start = None

    for d in sorted_dates:
        if all_days[d] > 0:
            if cur_streak == 0:
                cur_start = d
            cur_streak += 1
            if cur_streak > longest_streak:
                longest_streak = cur_streak
                best_start = cur_start
                best_end = d
        else:
            cur_streak = 0
            cur_start = None

    longest_range = f"{fmt_date(best_start)} – {fmt_date(best_end)}" if best_start and best_end else "N/A"

    # Calculate active current streak and range
    today_str = date.today().strftime("%Y-%m-%d")
    current_streak = 0
    cur_streak_start = None

    past_dates = [d for d in sorted_dates if d <= today_str]
    if past_dates:
        rev_dates = list(reversed(past_dates))
        for i, d in enumerate(rev_dates):
            cnt = all_days.get(d, 0)
            if i == 0 and d == today_str and cnt == 0:
                continue
            if cnt > 0:
                current_streak += 1
                cur_streak_start = d
            else:
                break

    tier_class, tier_name = get_streak_tier(current_streak)

    if current_streak > 1 and cur_streak_start:
        current_date = f"{fmt_date(cur_streak_start, include_year=False)} – {fmt_date(today_str, include_year=False)} · {tier_name}"
    else:
        current_date = f"{fmt_date(today_str, include_year=False)} · {tier_name}"

    # Extract last 31 days (exact 31 days sequence)
    last_31_days = [(date.today() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30, -1, -1)]

    return {
        "total_contributions": total_contributions,
        "total_range": total_range,
        "current_streak": current_streak,
        "current_date": current_date,
        "longest_streak": longest_streak,
        "longest_range": longest_range,
        "tier_class": tier_class,
        "tier_name": tier_name,
        "all_days": all_days,
        "last_31_days": last_31_days,
    }

def update_stats_svg(stats):
    """Update components/stats/stats.svg with calculated numbers, ranges, and tier class."""
    if not os.path.exists(STATS_SVG_PATH):
        print(f"Error: SVG file not found at {STATS_SVG_PATH}", file=sys.stderr)
        return

    with open(STATS_SVG_PATH, "r", encoding="utf-8") as f:
        svg_content = f.read()

    total_formatted = f"{stats['total_contributions']:,}"
    current_formatted = str(stats['current_streak'])
    longest_formatted = str(stats['longest_streak'])

    svg_content = re.sub(
        r'(class="center-hero\s+)[^"]*(")',
        rf'\g<1>{stats["tier_class"]}\g<2>',
        svg_content
    )
    svg_content = re.sub(
        r'(id="stat-total-contribs">)(.*?)(</text>)',
        rf'\g<1>{total_formatted}\g<3>',
        svg_content
    )
    svg_content = re.sub(
        r'(id="stat-total-range">)(.*?)(</text>)',
        rf'\g<1>{stats["total_range"]}\g<3>',
        svg_content
    )
    svg_content = re.sub(
        r'(id="stat-current-streak">)(.*?)(</text>)',
        rf'\g<1>{current_formatted}\g<3>',
        svg_content
    )
    svg_content = re.sub(
        r'(id="stat-current-date">)(.*?)(</text>)',
        rf'\g<1>{stats["current_date"]}\g<3>',
        svg_content
    )
    svg_content = re.sub(
        r'(id="stat-longest-streak">)(.*?)(</text>)',
        rf'\g<1>{longest_formatted}\g<3>',
        svg_content
    )
    svg_content = re.sub(
        r'(id="stat-longest-range">)(.*?)(</text>)',
        rf'\g<1>{stats["longest_range"]}\g<3>',
        svg_content
    )

    with open(STATS_SVG_PATH, "w", encoding="utf-8") as f:
        f.write(svg_content)

    print(f"Successfully updated {STATS_SVG_PATH}")

def update_activity_graph_svg(stats):
    """Render components/activity-graph/activity-graph.svg."""
    os.makedirs(os.path.dirname(GRAPH_SVG_PATH), exist_ok=True)
    svg_content = generate_activity_graph_svg(stats["last_31_days"], stats["all_days"])
    with open(GRAPH_SVG_PATH, "w", encoding="utf-8") as f:
        f.write(svg_content)
    print(f"Successfully rendered {GRAPH_SVG_PATH}")

def main():
    print(f"Fetching GitHub activity & stats for user: {USERNAME}...")
    stats = calculate_stats(USERNAME)
    if stats:
        update_stats_svg(stats)
        update_activity_graph_svg(stats)
        print("All components generated successfully!")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
