/**
 * Accessibility report generator.
 *
 * @file report-generator.ts
 * @location frontend/tests/accessibility/report-generator.ts
 */

import fs from "fs";
import path from "path";

interface Violation {
  id: string;
  impact: string;
  description: string;
  help: string;
  helpUrl: string;
  nodes: Array<{
    target: string[];
    html: string;
    failureSummary: string;
  }>;
}

interface Report {
  timestamp: string;
  totalViolations: number;
  totalChecks: number;
  violations: Violation[];
  summary: {
    critical: number;
    serious: number;
    moderate: number;
    minor: number;
  };
}

export class AccessibilityReportGenerator {
  private reportDir: string;

  constructor(reportDir: string = "./playwright-report/accessibility") {
    this.reportDir = reportDir;
  }

  generateReport(violations: Violation[]): Report {
    const report: Report = {
      timestamp: new Date().toISOString(),
      totalViolations: violations.length,
      totalChecks: 0,
      violations,
      summary: {
        critical: 0,
        serious: 0,
        moderate: 0,
        minor: 0,
      },
    };

    // Count violations by impact
    violations.forEach((v) => {
      const impact = v.impact || "unknown";
      switch (impact) {
        case "critical":
          report.summary.critical++;
          break;
        case "serious":
          report.summary.serious++;
          break;
        case "moderate":
          report.summary.moderate++;
          break;
        case "minor":
          report.summary.minor++;
          break;
      }
    });

    return report;
  }

  saveReport(
    report: Report,
    filename: string = "accessibility-report.json",
  ): void {
    // Create directory if it doesn't exist
    if (!fs.existsSync(this.reportDir)) {
      fs.mkdirSync(this.reportDir, { recursive: true });
    }

    const filePath = path.join(this.reportDir, filename);
    fs.writeFileSync(filePath, JSON.stringify(report, null, 2), "utf-8");
    console.log(`✅ Accessibility report saved to: ${filePath}`);
  }

  saveHTMLReport(
    report: Report,
    filename: string = "accessibility-report.html",
  ): void {
    const html = this.generateHTML(report);
    const filePath = path.join(this.reportDir, filename);
    fs.writeFileSync(filePath, html, "utf-8");
    console.log(`✅ Accessibility HTML report saved to: ${filePath}`);
  }

  generateHTML(report: Report): string {
    return `
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Accessibility Report</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #1a1a2e;
      color: #e0e0e0;
      padding: 20px;
      margin: 0;
    }
    .container {
      max-width: 1200px;
      margin: 0 auto;
    }
    h1 {
      color: #fff;
      border-bottom: 2px solid #2a2a4e;
      padding-bottom: 16px;
    }
    .stats {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 16px;
      margin: 24px 0;
    }
    .stat-card {
      background: #2a2a4e;
      padding: 16px;
      border-radius: 8px;
      text-align: center;
    }
    .stat-card .value {
      font-size: 32px;
      font-weight: bold;
    }
    .stat-card .label {
      color: #8888aa;
      font-size: 14px;
    }
    .stat-card.critical .value { color: #ff4757; }
    .stat-card.serious .value { color: #ff6b81; }
    .stat-card.moderate .value { color: #ffa502; }
    .stat-card.minor .value { color: #2ed573; }
    .stat-card.total .value { color: #4a6cf7; }

    .violation {
      background: #2a2a4e;
      border-radius: 8px;
      padding: 16px;
      margin: 12px 0;
      border-left: 4px solid #4a6cf7;
    }
    .violation.critical { border-left-color: #ff4757; }
    .violation.serious { border-left-color: #ff6b81; }
    .violation.moderate { border-left-color: #ffa502; }
    .violation.minor { border-left-color: #2ed573; }

    .violation-title {
      font-size: 18px;
      font-weight: bold;
      margin-bottom: 8px;
    }
    .violation-desc {
      color: #8888aa;
      margin-bottom: 8px;
    }
    .violation-help {
      font-size: 14px;
      color: #4a6cf7;
    }
    .violation-nodes {
      margin-top: 12px;
      padding: 12px;
      background: #1a1a2e;
      border-radius: 4px;
      font-size: 13px;
      font-family: monospace;
      overflow-x: auto;
    }
    .violation-nodes code {
      color: #e0e0e0;
    }
    .timestamp {
      color: #666688;
      font-size: 14px;
      margin-top: 24px;
      text-align: center;
    }
    .status-pass {
      color: #2ed573;
      font-weight: bold;
    }
    .status-fail {
      color: #ff4757;
      font-weight: bold;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>🔍 Accessibility Report</h1>
    
    <div class="stats">
      <div class="stat-card total">
        <div class="value">${report.totalViolations}</div>
        <div class="label">Total Violations</div>
      </div>
      <div class="stat-card critical">
        <div class="value">${report.summary.critical}</div>
        <div class="label">Critical</div>
      </div>
      <div class="stat-card serious">
        <div class="value">${report.summary.serious}</div>
        <div class="label">Serious</div>
      </div>
      <div class="stat-card moderate">
        <div class="value">${report.summary.moderate}</div>
        <div class="label">Moderate</div>
      </div>
      <div class="stat-card minor">
        <div class="value">${report.summary.minor}</div>
        <div class="label">Minor</div>
      </div>
    </div>

    <h2>Overall Status: ${report.totalViolations === 0 ? "✅ PASS" : "❌ FAIL"}</h2>
    <p>${report.totalViolations === 0 ? "No accessibility violations detected! 🎉" : "Please fix the violations listed below."}</p>

    ${
      report.violations.length > 0
        ? `
      <h2>Violations (${report.violations.length})</h2>
      ${report.violations
        .map(
          (v) => `
        <div class="violation ${v.impact || "moderate"}">
          <div class="violation-title">${v.id}</div>
          <div class="violation-desc">${v.description}</div>
          <div class="violation-help">
            <a href="${v.helpUrl}" target="_blank" style="color: #4a6cf7;">${v.help}</a>
          </div>
          <div class="violation-nodes">
            <strong>Affected elements:</strong>
            <ul>
              ${v.nodes
                .map(
                  (n) => `
                <li>
                  <code>${n.target.join(" ")}</code>
                  <br>${n.failureSummary}
                </li>
              `,
                )
                .join("")}
            </ul>
          </div>
        </div>
      `,
        )
        .join("")}
    `
        : `
      <div class="status-pass">✅ No violations found! All accessibility checks passed.</div>
    `
    }

    <div class="timestamp">Report generated: ${report.timestamp}</div>
  </div>
</body>
</html>
    `;
  }
}
