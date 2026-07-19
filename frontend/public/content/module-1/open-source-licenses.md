## The Permission Slip: Understanding Open Source Licenses

Imagine you baked a really good cake and shared the recipe online. Someone makes your cake, sells it, and becomes famous — without ever saying it was your recipe. How would you feel?

That's why **licenses** exist. A license is like a permission slip that tells people: "Yes, you can use my code! Here are the rules..."

---

## ⚠️ The Most Important Thing to Know

> **If a GitHub repository has NO license file, you do NOT have permission to use, copy, modify, or distribute the code.**

Even though you can _see_ the code (it's public on GitHub), that doesn't mean you're allowed to _use_ it. By default, copyright law says the creator owns it. Without a license, you're just looking at someone else's work without permission.

Think of it like a book in a library. You can read it, but you can't photocopy it and sell copies unless the author says you can.

---

## 🔓 Type 1: Permissive Licenses ("Do Almost Anything")

These are the most relaxed licenses. They say:

> "Here's my code. Use it however you want — even in a paid, closed product. Just give me credit."

| License        | Key Rule                                            | Can I use it in a paid app? |
| -------------- | --------------------------------------------------- | --------------------------- |
| **MIT**        | Keep the copyright notice                           | ✅ Yes                      |
| **BSD**        | Keep the copyright notice, don't pretend it's yours | ✅ Yes                      |
| **Apache 2.0** | Same as MIT + extra patent protections              | ✅ Yes                      |

**You'll see these most often.** React, most npm packages, Python libraries — they use MIT or Apache 2.0.

**Example**: You find a cool button component on GitHub with an MIT license. You can use it in your paid app, modify it, and sell your app. You just need to keep the original credit somewhere in your code.

---

## 🔗 Type 2: Copyleft Licenses ("Share Alike")

These licenses say:

> "If you use my code and share your result, you must also share your code under the same license."

| License  | What It Requires                                                                         |
| -------- | ---------------------------------------------------------------------------------------- |
| **GPL**  | If you distribute a modified version, your changes must also be open source              |
| **LGPL** | A milder version — OK to use in paid apps as long as you don't modify the library itself |
| **AGPL** | Even if you only offer it as a web service (SaaS), you must share your changes           |

**Copyleft is designed to keep code free forever.** If someone builds on your GPL code, they can't turn it into a closed, paid product.

---

## 🧠 Analogy: Recipes

- **No license**: You found a recipe in a locked drawer. You can peek, but you can't cook it.
- **MIT license**: "Here's my recipe. Cook it, change it, sell it. Just mention it was my recipe."
- **GPL license**: "Here's my recipe. Cook it, change it, share it. But if you share your version, you must also share the recipe freely."

---

## 📋 Quick Checklist Before You Use Someone's Code

1. **Is there a LICENSE file in the repo?** → If not, assume you cannot use it.
2. **Which license?** → MIT/BSD/Apache = safe for almost anything. GPL = must stay open.
3. **Contributing your own code?** → Your contribution will be under the same license as the project you're contributing to.

---

## 💡 Friendly Advice

Don't let licenses scare you. As a beginner contributor:

- **Most projects you'll encounter use MIT or Apache 2.0** — very relaxed
- **If you see GPL**, just know your contributions must also be open (which is fine for open source!)
- **The golden rule**: When in doubt, ask the maintainers

And remember: licenses exist to **protect both creators and users**. They make open source possible by setting clear rules so everyone can collaborate safely.

---

## 📝 Quick Check

[interactive-quiz id="quiz-6"]
