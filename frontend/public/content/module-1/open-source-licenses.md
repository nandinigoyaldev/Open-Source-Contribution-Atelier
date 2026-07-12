# ⚖️ Choosing and Understanding Open Source Licenses

### Before you fork, use, or contribute to a project, one question matters more than any line of code: **what does its license actually let you do?**

---

## 1️⃣ A License Is Not Optional Legal Fine Print

A license is the document that grants you permission to use, copy, modify, or distribute someone else's code. Copyright law gives the original author exclusive rights by default — a license is how they _waive_ some of those rights for everyone else.

> [!IMPORTANT]
> If a public repository has **no license file**, it is not "free to use." By default, the author retains all rights, and you have no legal permission to use, copy, modify, or distribute the code, even though you can see it on GitHub.

This is one of the most common misunderstandings in open source: **visible is not the same as usable.**

---

## 2️⃣ Permissive Licenses: Minimal Restrictions

Permissive licenses let you do almost anything with the code, including using it in closed-source commercial products, as long as you keep the required attribution.

| License              | Key requirement                                                                            | Commercial/closed-source use? |
| -------------------- | ------------------------------------------------------------------------------------------ | ----------------------------- |
| **MIT**              | Keep the copyright notice and license text                                                 | ✅ Yes                        |
| **BSD (2/3-clause)** | Keep the copyright notice; 3-clause also restricts using the author's name for endorsement | ✅ Yes                        |
| **Apache 2.0**       | Keep notice + an explicit patent grant clause                                              | ✅ Yes                        |

These are the licenses you'll see most often on libraries meant to be widely reused — React, most npm packages, and many Python libraries use MIT or Apache 2.0.

---

## 3️⃣ Copyleft Licenses: "Share Alike" Requirements

Copyleft licenses require that derivative works, and in some cases even software that merely _links_ to the code, be released under the same or a compatible open source license. This is sometimes informally called being "viral."

- **GPL (GNU General Public License)**: If you distribute a modified version, you must release your changes under the GPL too.
- **LGPL (Lesser GPL)**: A softer version — you can link to LGPL code from proprietary software without open-sourcing your own code, but modifications to the LGPL library itself must stay open.
- **AGPL (Affero GPL)**: Like the GPL, but also triggers the sharing requirement when the software is used to provide a network service (e.g. a SaaS product), not just when it's distributed.

> [!WARNING]
> Copyleft licenses are a common blocker for companies. Before adding a GPL/AGPL-licensed dependency to a commercial closed-source product, check with a legal or licensing expert — it can force you to open source parts of your own codebase.

---

## 4️⃣ Quick Checklist Before You Contribute or Depend on a Repo

1. **Look for a `LICENSE` or `LICENSE.md` file** in the repo root.
2. **No license file at all?** Assume you have no legal right to reuse the code — open an issue asking the maintainer to add one instead of assuming it's fine.
3. **Permissive (MIT/BSD/Apache)?** Safe for almost any use case, including commercial and closed-source.
4. **Copyleft (GPL/LGPL/AGPL)?** Fine for personal projects and other open source projects, but get informed before shipping it inside proprietary software.
5. **Contributing code yourself?** Your contribution is typically licensed under the _same_ license as the project you're contributing to, unless a Contributor License Agreement (CLA) says otherwise.

---

> [!TIP]
> Choosealicense.com is a great quick reference if you're ever unsure what a specific license permits — but for anything commercially sensitive, a real license comparison from a lawyer beats a website summary.
