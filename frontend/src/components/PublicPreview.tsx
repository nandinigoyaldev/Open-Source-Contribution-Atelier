import React, { useState } from "react";
import "./PublicPreview.css";

export function PublicPreview() {
  const [activeTab, setActiveTab] = useState<"preview" | "demo">("preview");
  return (
    <div className="public-preview">
      <div className="preview-header">
        <h2>🎯 Try Before You Start</h2>
        <p>
          Explore sample content and interactive features without signing up
        </p>
      </div>

      <div className="preview-tabs">
        <button
          className={`tab-btn ${activeTab === "preview" ? "active" : ""}`}
          onClick={() => setActiveTab("preview")}
        >
          📚 Sample Lesson
        </button>
        <button
          className={`tab-btn ${activeTab === "demo" ? "active" : ""}`}
          onClick={() => setActiveTab("demo")}
        >
          🧪 Interactive Demo
        </button>
      </div>

      <div className="preview-content">
        {activeTab === "preview" ? (
          <div className="sample-lesson">
            <h3>📖 Introduction to Open Source</h3>
            <div className="lesson-preview">
              <p>
                Open source software is code that is publicly accessible and can
                be modified, enhanced, and shared by anyone.
              </p>
              <ul className="preview-features">
                <li>✅ Learn what open source means</li>
                <li>✅ Understand how contributions work</li>
                <li>✅ See real-world examples</li>
              </ul>
              <div className="preview-actions">
                <button className="preview-btn">Continue Reading →</button>
                <span className="preview-note">
                  Sign up to access full lesson
                </span>
              </div>
            </div>
          </div>
        ) : (
          <div className="interactive-demo">
            <h3>🧪 Try the Sandbox</h3>
            <div className="demo-terminal">
              <div className="terminal-header">
                <span>💻 Terminal</span>
                <span className="terminal-status">⚡ Ready</span>
              </div>
              <div className="terminal-body">
                <div className="terminal-line">
                  <span className="prompt">$</span>git init
                </div>
                <div className="terminal-line output">
                  ✅ Initialized empty Git repository
                </div>
                <div className="terminal-line">
                  <span className="prompt">$</span>echo "Hello World" {">"}{" "}
                  README.md
                </div>
                <div className="terminal-line output">✅ Created README.md</div>
                <div className="terminal-line input">
                  <span className="prompt">$</span>
                  <span className="blink">_</span>
                </div>
              </div>
            </div>
            <p className="demo-note">
              💡 This is a preview. Full sandbox available after sign up
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
