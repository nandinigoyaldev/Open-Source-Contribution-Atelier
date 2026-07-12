import { describe, it, expect } from "vitest";
import { instrumentJS } from "../lib/jsTracer";

describe("jsTracer", () => {
  it("should instrument a simple variable declaration", () => {
    const code = `let x = 10;`;
    const result = instrumentJS(code);
    expect(result).toContain("__trace(");
    expect(result).toContain("typeof x");
  });

  it("should handle shadowing and functions", () => {
    const code = `
      let x = 10;
      function foo(y) {
        let x = 20;
        return x + y;
      }
      foo(5);
    `;
    const result = instrumentJS(code);
    expect(result).toContain("typeof x");
    expect(result).toContain("typeof y");
    expect(result).toContain("typeof foo");
  });

  it("should handle object destructuring", () => {
    const code = `
      const obj = { a: 1, b: { c: 2 } };
      const { a, b: { c } } = obj;
    `;
    const result = instrumentJS(code);
    expect(result).toContain("typeof a");
    expect(result).toContain("typeof c");
  });

  it("should handle array destructuring", () => {
    const code = `
      const arr = [1, 2, 3];
      const [first, , third] = arr;
    `;
    const result = instrumentJS(code);
    expect(result).toContain("typeof first");
    expect(result).toContain("typeof third");
  });

  it("should gracefully handle syntax errors by returning original code", () => {
    const code = `const x = ;`;
    const result = instrumentJS(code);
    expect(result).toEqual(code);
  });
});
