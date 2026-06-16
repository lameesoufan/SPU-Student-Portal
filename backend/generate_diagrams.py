"""
SPU Portal — Test Case & Test Result Diagrams Generator
شغّلي: python generate_diagrams.py
"""

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.patches import FancyBboxPatch
import numpy as np
import os

# ═══ Setup ═══
plt.rcParams.update({
    'axes.unicode_minus': False,
    'figure.facecolor': '#FFFFFF',
    'axes.facecolor': '#FFFFFF',
    'axes.edgecolor': '#E5E7EB',
    'axes.linewidth': 0.8,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.grid': False,
    'xtick.major.size': 0,
    'ytick.major.size': 0,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'axes.labelsize': 10,
    'axes.titlesize': 16,
    'axes.titleweight': 'bold',
    'axes.titlepad': 16,
    'legend.frameon': False,
    'legend.fontsize': 9,
    'figure.dpi': 200,
    'savefig.dpi': 200,
    'savefig.bbox': 'tight',
    'savefig.facecolor': '#FFFFFF',
    'savefig.pad_inches': 0.3,
})

# Colors
C_BLUE   = '#3B82F6'
C_CYAN   = '#06B6D4'
C_PURPLE = '#8B5CF6'
C_AMBER  = '#F59E0B'
C_RED    = '#EF4444'
C_GREEN  = '#10B981'
COOL = [C_BLUE, C_CYAN, C_PURPLE, C_AMBER, C_RED, C_GREEN]
G900 = '#111827'
G700 = '#374151'
G500 = '#6B7280'
G400 = '#9CA3AF'
G300 = '#D1D5DB'
G200 = '#E5E7EB'
G100 = '#F3F4F6'
G50  = '#F9FAFB'
POS = '#10B981'
NEG = '#EF4444'

OUT = 'test-diagrams'
os.makedirs(OUT, exist_ok=True)

def clean_axis(ax, grid=True):
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    if grid:
        ax.yaxis.grid(True, alpha=0.08, color=G300)
        ax.set_axisbelow(True)

def save(fig, path, dpi=200):
    try:
        fig.tight_layout()
    except:
        pass
    fig.savefig(path, dpi=dpi, facecolor='white', bbox_inches='tight')
    plt.close(fig)
    size_kb = os.path.getsize(path) / 1024
    print(f'  {os.path.basename(path)} ({size_kb:.0f}KB)')


# ═══════════════════════════════════════════════════════════════
# DIAGRAM 1: Test Cases per Application
# ═══════════════════════════════════════════════════════════════
print("Generating Diagram 1: Test Cases per Application...")

apps = ['Accounts', 'Projects', 'Workflow', 'Project\nMgmt', 'Dy Forms', 'GitLab\nIntegration', 'Notifications']
test_counts = [29, 39, 38, 25, 15, 14, 12]
total_tests = sum(test_counts)

fig, ax = plt.subplots(figsize=(12, 6))
colors = [C_BLUE, C_CYAN, C_PURPLE, C_AMBER, C_GREEN, C_RED, '#EC4899']
bars = ax.bar(apps, test_counts, color=colors, width=0.6, zorder=3, edgecolor='white', linewidth=0.5)

for i, (bar, val) in enumerate(zip(bars, test_counts)):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.8,
            f'{val}', ha='center', va='bottom', fontsize=11, fontweight='bold', color=G900)

ax.set_ylim(0, max(test_counts) * 1.25)
ax.set_ylabel('Number of Test Cases', fontsize=11, color=G700)
ax.set_title(f'Test Cases per Application Module (Total: {total_tests})',
             loc='left', fontsize=16, fontweight='bold', color=G900)
clean_axis(ax)
save(fig, f'{OUT}/1_test_cases_per_app.png')


# ═══════════════════════════════════════════════════════════════
# DIAGRAM 2: Test Type Distribution (Donut)
# ═══════════════════════════════════════════════════════════════
print("Generating Diagram 2: Test Type Distribution...")

fig, ax = plt.subplots(figsize=(8, 8))
labels = ['Unit Tests', 'Integration Tests', 'API / Functional Tests']
values = [85, 55, 32]
colors_donut = [C_BLUE, C_CYAN, C_AMBER]

wedges, _, autotexts = ax.pie(
    values, labels=None, colors=colors_donut, autopct='%1.0f%%',
    startangle=90, pctdistance=0.78,
    wedgeprops=dict(width=0.35, edgecolor='white', linewidth=2))

for t in autotexts:
    t.set_fontsize(11)
    t.set_fontweight('bold')

ax.text(0, 0.06, str(total_tests), ha='center', va='center',
        fontsize=32, fontweight='bold', color=G900)
ax.text(0, -0.1, 'Total Tests', ha='center', va='center', fontsize=12, color=G500)

ax.legend(wedges, [f'{l} ({v})' for l, v in zip(labels, values)],
          loc='center left', bbox_to_anchor=(1, 0.5), fontsize=11)
ax.set_title('Test Type Distribution', loc='center', pad=20,
             fontsize=16, fontweight='bold', color=G900)
save(fig, f'{OUT}/2_test_type_distribution.png')


# ═══════════════════════════════════════════════════════════════
# DIAGRAM 3: Test Coverage per Application
# ═══════════════════════════════════════════════════════════════
print("Generating Diagram 3: Test Coverage per Application...")

fig, ax = plt.subplots(figsize=(12, 6))
apps_cov = ['Notifications', 'Project\nMgmt', 'Workflow', 'Projects', 'Accounts', 'Dy Forms', 'GitLab\nIntegration']
coverage = [100, 90, 87, 82, 85, 80, 56]
overall = 77

bar_colors = []
for c in coverage:
    if c >= 90:   bar_colors.append(C_GREEN)
    elif c >= 75: bar_colors.append(C_BLUE)
    elif c >= 60: bar_colors.append(C_AMBER)
    else:         bar_colors.append(C_RED)

bars = ax.barh(apps_cov, coverage, color=bar_colors, height=0.6, zorder=3, edgecolor='white', linewidth=0.3)

for bar, val in zip(bars, coverage):
    ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2,
            f'{val}%', va='center', fontsize=11, fontweight='bold',
            color=G900 if val >= 75 else C_RED)

ax.axvline(x=overall, color=G700, linewidth=2, linestyle='--', zorder=2)
ax.text(overall + 1, len(apps_cov) - 0.3, f'Overall: {overall}%',
        fontsize=11, fontweight='bold', color=G700)

ax.set_xlim(0, 110)
ax.set_xlabel('Coverage (%)', fontsize=11, color=G700)
ax.set_title('Code Coverage by Application Module', loc='left', fontsize=16, fontweight='bold', color=G900)
clean_axis(ax, grid=True)
ax.xaxis.grid(True, alpha=0.08, color=G300)
save(fig, f'{OUT}/3_test_coverage_per_app.png')


# ═══════════════════════════════════════════════════════════════
# DIAGRAM 4: Test Results Summary (All Pass)
# ═══════════════════════════════════════════════════════════════
print("Generating Diagram 4: Test Results Summary...")

fig, ax = plt.subplots(figsize=(12, 6))
apps_res = ['Accounts', 'Projects', 'Workflow', 'Project\nMgmt', 'Dy Forms', 'GitLab\nIntegration', 'Notifications']
passed = [29, 39, 38, 25, 15, 14, 12]
failed = [0, 0, 0, 0, 0, 0, 0]

x = np.arange(len(apps_res))
width = 0.35

bars_p = ax.bar(x - width/2, passed, width, color=C_GREEN, label='Passed', zorder=3, edgecolor='white', linewidth=0.5)
bars_f = ax.bar(x + width/2, failed, width, color=C_RED, label='Failed', zorder=3, edgecolor='white', linewidth=0.5)

for bar, val in zip(bars_p, passed):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
            str(val), ha='center', va='bottom', fontsize=10, fontweight='bold', color=C_GREEN)

ax.set_xticks(x)
ax.set_xticklabels(apps_res)
ax.set_ylim(0, max(passed) * 1.25)
ax.set_ylabel('Number of Test Cases', fontsize=11, color=G700)
ax.set_title(f'Automated Test Results - All 172 Tests Passed (100% Pass Rate)',
             loc='left', fontsize=15, fontweight='bold', color=G900)
ax.legend(loc='upper right', fontsize=10)
clean_axis(ax)
save(fig, f'{OUT}/4_test_results_summary.png')


# ═══════════════════════════════════════════════════════════════
# DIAGRAM 5: Performance Test - Response Time Comparison
# ═══════════════════════════════════════════════════════════════
print("Generating Diagram 5: Performance Test Response Times...")

fig, ax = plt.subplots(figsize=(12, 6))
test_types = ['Load Test\n(50 users)', 'Spike Test\n(100 users)', 'Stress Test\n(200 users)']
p50 = [8, 9, 8]
p95 = [75, 1000, 74]
p99 = [6500, 28000, 6800]

x = np.arange(len(test_types))
width = 0.25

bars1 = ax.bar(x - width, p50, width, color=C_BLUE, label='P50 (Median)', zorder=3, edgecolor='white', linewidth=0.5)
bars2 = ax.bar(x, p95, width, color=C_AMBER, label='P95', zorder=3, edgecolor='white', linewidth=0.5)
bars3 = ax.bar(x + width, p99, width, color=C_RED, label='P99', zorder=3, edgecolor='white', linewidth=0.5)

for bars, vals in [(bars1, p50), (bars2, p95), (bars3, p99)]:
    for bar, val in zip(bars, vals):
        label = f'{val/1000:.0f}s' if val >= 1000 else f'{val}ms'
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(p99)*0.01,
                label, ha='center', va='bottom', fontsize=8, color=G700)

ax.set_xticks(x)
ax.set_xticklabels(test_types)
ax.set_ylim(0, max(p99) * 1.15)
ax.set_ylabel('Response Time (ms)', fontsize=11, color=G700)
ax.set_title('Performance Test - Response Time Comparison (P50 / P95 / P99)',
             loc='left', fontsize=14, fontweight='bold', color=G900)
ax.legend(loc='upper left', fontsize=10)
clean_axis(ax)
save(fig, f'{OUT}/5_performance_response_times.png')


# ═══════════════════════════════════════════════════════════════
# DIAGRAM 6: Key Endpoints Response Times
# ═══════════════════════════════════════════════════════════════
print("Generating Diagram 6: Key Endpoints Response Times...")

fig, ax = plt.subplots(figsize=(14, 7))
endpoints = [
    '/api/notifications/',
    '/api/projects/ideas/browse/',
    '/api/project-management/board/',
    '/api/departments/',
    '/api/doctors/',
    '/api/workflow/templates/',
    '/api/workflow/pending/',
    '/api/projects/proposals/mine/',
]
load_p95 = [19, 42, 47, 26, 38, 45, 37, 23]
stress_p95 = [25, 45, 58, 35, 42, 40, 28, 31]

x = np.arange(len(endpoints))
width = 0.35

bars1 = ax.bar(x - width/2, load_p95, width, color=C_BLUE, label='Load Test (50 users)', zorder=3, edgecolor='white', linewidth=0.5)
bars2 = ax.bar(x + width/2, stress_p95, width, color=C_PURPLE, label='Stress Test (200 users)', zorder=3, edgecolor='white', linewidth=0.5)

for bars in [bars1, bars2]:
    for bar in bars:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.5,
                f'{bar.get_height():.0f}', ha='center', va='bottom', fontsize=8, color=G400)

ax.set_xticks(x)
ax.set_xticklabels(endpoints, rotation=25, ha='right', fontsize=9)
ax.set_ylim(0, max(stress_p95) * 1.3)
ax.set_ylabel('Response Time P95 (ms)', fontsize=11, color=G700)
ax.set_title('Key API Endpoints - P95 Response Time (Load vs Stress)',
             loc='left', fontsize=14, fontweight='bold', color=G900)
ax.legend(loc='upper left', fontsize=10)
clean_axis(ax, grid=True)
ax.xaxis.grid(True, alpha=0.05, color=G300)
save(fig, f'{OUT}/6_endpoint_response_times.png')


# ═══════════════════════════════════════════════════════════════
# DIAGRAM 7: Quality Metrics KPI Cards
# ═══════════════════════════════════════════════════════════════
print("Generating Diagram 7: Quality Metrics KPI Cards...")

metrics = [
    {'label': 'Test Coverage', 'value': '77%', 'change': '172 Tests', 'positive': True},
    {'label': 'Defect Density', 'value': '0.65', 'change': 'defects/KLOC', 'positive': True},
    {'label': 'P50 Response', 'value': '8ms', 'change': 'Median Latency', 'positive': True},
    {'label': 'Failure Rate', 'value': '0%', 'change': 'All Tests Pass', 'positive': True},
]

n = len(metrics)
fig, axes = plt.subplots(1, n, figsize=(4*n, 3.2))
if n == 1: axes = [axes]

for ax, m in zip(axes, metrics):
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
    bg = FancyBboxPatch((0.05, 0.05), 0.9, 0.9,
        boxstyle='round,pad=0.05', facecolor=G50, edgecolor=G200, linewidth=0.8)
    ax.add_patch(bg)
    ax.text(0.5, 0.78, m['label'], ha='center', va='center', fontsize=11, color=G500)
    ax.text(0.5, 0.48, m['value'], ha='center', va='center', fontsize=26, fontweight='bold', color=G900)
    ax.text(0.5, 0.18, m['change'], ha='center', va='center', fontsize=10,
            color=POS if m.get('positive', True) else NEG, fontweight='bold')

fig.suptitle('Software Quality Metrics - SPU Portal', fontsize=18, fontweight='bold', color=G900, y=1.02)
save(fig, f'{OUT}/7_quality_metrics_kpi.png')


# ═══════════════════════════════════════════════════════════════
# DIAGRAM 8: Performance Test Summary - RPS & Users
# ═══════════════════════════════════════════════════════════════
print("Generating Diagram 8: Performance Test Summary...")

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
test_names = ['Load\n(50 users)', 'Spike\n(100 users)', 'Stress\n(200 users)']
rps = [21, 27, 40]
total_reqs = [6363, 4884, 23863]

bars = ax1.bar(test_names, rps, color=[C_BLUE, C_CYAN, C_PURPLE], width=0.5, zorder=3, edgecolor='white', linewidth=0.5)
for bar, val in zip(bars, rps):
    ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
             f'{val}', ha='center', va='bottom', fontsize=12, fontweight='bold', color=G900)
ax1.set_ylim(0, max(rps) * 1.25)
ax1.set_ylabel('Requests per Second', fontsize=11, color=G700)
ax1.set_title('Throughput (RPS)', loc='left', fontsize=14, fontweight='bold', color=G900)
clean_axis(ax1)

bars2 = ax2.bar(test_names, total_reqs, color=[C_BLUE, C_CYAN, C_PURPLE], width=0.5, zorder=3, edgecolor='white', linewidth=0.5)
for bar, val in zip(bars2, total_reqs):
    ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(total_reqs)*0.01,
             f'{val:,}', ha='center', va='bottom', fontsize=11, fontweight='bold', color=G900)
ax2.set_ylim(0, max(total_reqs) * 1.2)
ax2.set_ylabel('Total Requests', fontsize=11, color=G700)
ax2.set_title('Total Requests Processed', loc='left', fontsize=14, fontweight='bold', color=G900)
clean_axis(ax2)

fig.suptitle('Performance Test Summary - 0% Failure Rate Across All Tests',
             fontsize=15, fontweight='bold', color=G900, y=1.02)
save(fig, f'{OUT}/8_performance_summary.png')


# ═══════════════════════════════════════════════════════════════
# DIAGRAM 9: Defect Density & Bug Summary
# ═══════════════════════════════════════════════════════════════
print("Generating Diagram 9: Defect Analysis...")

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

categories = ['SPU Portal', 'Industry\nStandard\n(Good)', 'Industry\nStandard\n(Acceptable)']
densities = [0.65, 2.0, 5.0]
bar_colors = [C_GREEN, C_BLUE, C_AMBER]

bars = ax1.bar(categories, densities, color=bar_colors, width=0.5, zorder=3, edgecolor='white', linewidth=0.5)
for bar, val in zip(bars, densities):
    ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
             f'{val}', ha='center', va='bottom', fontsize=12, fontweight='bold', color=G900)
ax1.set_ylim(0, 6.5)
ax1.set_ylabel('Defects per KLOC', fontsize=11, color=G700)
ax1.set_title('Defect Density vs Industry Standard', loc='left', fontsize=14, fontweight='bold', color=G900)
clean_axis(ax1)

bug_types = ['Logic\nErrors', 'Performance\nIssues', 'Data\nHandling', 'Integration\nIssues']
bug_counts = [3, 2, 1, 1]
bug_colors = [C_BLUE, C_AMBER, C_CYAN, C_RED]

bars2 = ax2.bar(bug_types, bug_counts, color=bug_colors, width=0.5, zorder=3, edgecolor='white', linewidth=0.5)
for bar, val in zip(bars2, bug_counts):
    ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
             str(val), ha='center', va='bottom', fontsize=12, fontweight='bold', color=G900)
ax2.set_ylim(0, max(bug_counts) * 1.5)
ax2.set_ylabel('Number of Defects', fontsize=11, color=G700)
ax2.set_title('Defects by Category (Total: 7)', loc='left', fontsize=14, fontweight='bold', color=G900)
clean_axis(ax2)

fig.suptitle('Defect Analysis - KLOC: 10.79 | Total Defects: 7 | Density: 0.65/KLOC',
             fontsize=14, fontweight='bold', color=G900, y=1.02)
save(fig, f'{OUT}/9_defect_analysis.png')


print("\n" + "="*60)
print("  All 9 diagrams generated successfully!")
print(f"  Output folder: {os.path.abspath(OUT)}/")
print("="*60)