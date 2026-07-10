import { describe, it, expect } from "vitest";
import { TextTokenizer } from "./renderMentions";

describe("TextTokenizer", () => {
  it("parses plain text correctly", () => {
    const tokenizer = new TextTokenizer("Hello world");
    const tokens = tokenizer.tokenize();
    expect(tokens).toEqual([
      { type: "text", content: "Hello world", raw: "Hello world" },
    ]);
  });

  it("parses a single mention", () => {
    const tokenizer = new TextTokenizer("@johndoe");
    const tokens = tokenizer.tokenize();
    expect(tokens).toEqual([
      { type: "mention", content: "johndoe", raw: "@johndoe" },
    ]);
  });

  it("parses a mention inside text", () => {
    const tokenizer = new TextTokenizer("Hello @johndoe how are you?");
    const tokens = tokenizer.tokenize();
    expect(tokens).toEqual([
      { type: "text", content: "Hello ", raw: "Hello " },
      { type: "mention", content: "johndoe", raw: "@johndoe" },
      { type: "text", content: " how are you?", raw: " how are you?" },
    ]);
  });

  it("parses multiple mentions", () => {
    const tokenizer = new TextTokenizer("@alice and @bob");
    const tokens = tokenizer.tokenize();
    expect(tokens).toEqual([
      { type: "mention", content: "alice", raw: "@alice" },
      { type: "text", content: " and ", raw: " and " },
      { type: "mention", content: "bob", raw: "@bob" },
    ]);
  });

  it("parses issue references", () => {
    const tokenizer = new TextTokenizer("Fixes #123");
    const tokens = tokenizer.tokenize();
    expect(tokens).toEqual([
      { type: "text", content: "Fixes ", raw: "Fixes " },
      { type: "issue", content: "123", raw: "#123" },
    ]);
  });

  it("parses links", () => {
    const tokenizer = new TextTokenizer("Check https://example.com/foo");
    const tokens = tokenizer.tokenize();
    expect(tokens).toEqual([
      { type: "text", content: "Check ", raw: "Check " },
      {
        type: "link",
        content: "https://example.com/foo",
        raw: "https://example.com/foo",
      },
    ]);
  });

  it("parses bold and italic", () => {
    const tokenizer = new TextTokenizer("This is **bold** and *italic*");
    const tokens = tokenizer.tokenize();
    expect(tokens).toEqual([
      { type: "text", content: "This is ", raw: "This is " },
      { type: "bold", content: "bold", raw: "**bold**" },
      { type: "text", content: " and ", raw: " and " },
      { type: "italic", content: "italic", raw: "*italic*" },
    ]);
  });

  it("parses inline code", () => {
    const tokenizer = new TextTokenizer("Use `const x = 1;`");
    const tokens = tokenizer.tokenize();
    expect(tokens).toEqual([
      { type: "text", content: "Use ", raw: "Use " },
      { type: "code", content: "const x = 1;", raw: "`const x = 1;`" },
    ]);
  });

  it("parses code blocks", () => {
    const text = '```js\nconsole.log("hello");\n```';
    const tokenizer = new TextTokenizer(text);
    const tokens = tokenizer.tokenize();
    expect(tokens).toEqual([
      {
        type: "codeblock",
        content: 'console.log("hello");\n',
        raw: text,
        metadata: { language: "js" },
      },
    ]);
  });

  it("handles mentions directly after text like user@name", () => {
    const tokenizer = new TextTokenizer("user@name");
    const tokens = tokenizer.tokenize();
    expect(tokens).toEqual([
      { type: "text", content: "user", raw: "user" },
      { type: "mention", content: "name", raw: "@name" },
    ]);
  });

  it("handles quotes", () => {
    const tokenizer = new TextTokenizer("> quote text\nnext line");
    const tokens = tokenizer.tokenize();
    expect(tokens).toEqual([
      { type: "quote", content: "quote text", raw: "> quote text\n" },
      { type: "text", content: "next line", raw: "next line" },
    ]);
  });

  it("handles mixed edge cases", () => {
    const text =
      "Hey @alice, check out #42 and `rm -rf /`. See https://google.com for more **info**!";
    const tokenizer = new TextTokenizer(text);
    const tokens = tokenizer.tokenize();

    expect(tokens.map((t) => t.type)).toEqual([
      "text",
      "mention",
      "text",
      "issue",
      "text",
      "code",
      "text",
      "link",
      "text",
      "bold",
      "text",
    ]);
  });
});
