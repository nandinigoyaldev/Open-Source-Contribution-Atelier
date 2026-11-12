#!/usr/bin/env python3
"""
Unit tests for audit_security_headers_and_cors.py
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.audit_security_headers_and_cors import (
    analyze_file_content,
    scan_directory,
)


class TestAuditSecurityHeadersAndCors(unittest.TestCase):
    def test_detects_insecure_wildcard_cors_with_credentials(self):
        insecure_snippet = """
        const cors = require('cors');
        app.use(cors({
            origin: '*',
            credentials: true
        }));
        """
        findings = analyze_file_content(insecure_snippet, "server.js")
        self.assertTrue(any(f.severity == "HIGH" and f.category == "CORS" for f in findings))

    def test_detects_permissive_cors_without_credentials(self):
        permissive_snippet = """
        app.use(cors({ origin: '*' }));
        """
        findings = analyze_file_content(permissive_snippet, "server.js")
        self.assertTrue(any(f.severity == "MEDIUM" and f.category == "CORS" for f in findings))

    def test_secure_helmet_server_has_no_missing_header_findings(self):
        secure_snippet = """
        import express from 'express';
        import helmet from 'helmet';
        import cors from 'cors';

        const app = express();
        app.use(helmet());
        app.use(cors({ origin: 'https://trusted.domain.com', credentials: true }));
        """
        findings = analyze_file_content(secure_snippet, "server.js")
        self.assertEqual(len(findings), 0)

    def test_flags_missing_headers_on_raw_server_without_helmet(self):
        bare_server = """
        import express from 'express';
        const app = express();
        app.get('/api', (req, res) => res.json({ ok: true }));
        """
        findings = analyze_file_content(bare_server, "app.js")
        self.assertTrue(any(f.category == "Headers" and "Helmet" in f.message for f in findings))

    def test_scan_directory_finds_vulnerable_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            vuln_file = tmppath / "api_server.js"
            vuln_file.write_text("app.use(cors({ origin: '*', credentials: true }));", encoding="utf-8")

            findings = scan_directory(tmppath)
            self.assertTrue(len(findings) >= 1)
            self.assertTrue(any(f.severity == "HIGH" and f.category == "CORS" for f in findings))


if __name__ == "__main__":
    unittest.main()
