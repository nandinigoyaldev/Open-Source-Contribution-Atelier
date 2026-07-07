import * as acorn from "acorn";
import * as walk from "acorn-walk";
import { generate } from "astring";

export function instrumentJS(code: string): string {
  try {
    const ast = acorn.parse(code, {
      ecmaVersion: "latest",
      sourceType: "module",
      locations: true,
    });

    const allVariables = new Set<string>();

    function extractIdentifiers(pattern: acorn.Node | any) {
      if (!pattern) return;
      if (pattern.type === "Identifier") {
        allVariables.add(pattern.name);
      } else if (pattern.type === "ObjectPattern") {
        pattern.properties.forEach((prop: any) => {
          extractIdentifiers(prop.value || prop.argument);
        });
      } else if (pattern.type === "ArrayPattern") {
        pattern.elements.forEach((elem: any) => {
          extractIdentifiers(elem);
        });
      } else if (pattern.type === "RestElement") {
        extractIdentifiers(pattern.argument);
      } else if (pattern.type === "AssignmentPattern") {
        extractIdentifiers(pattern.left);
      }
    }

    walk.simple(ast, {
      VariableDeclarator(node: acorn.Node | any) {
        extractIdentifiers(node.id);
      },
      FunctionDeclaration(node: acorn.Node | any) {
        if (node.id?.name) {
          allVariables.add(node.id.name);
        }
        node.params?.forEach(extractIdentifiers);
      },
    });

    const varsObject = Array.from(allVariables)
      .map((v) => `"${v}": (typeof ${v} !== "undefined" ? ${v} : undefined)`)
      .join(", ");

    const buildLocals = `{ ${varsObject} }`;

    // Recursive function to instrument the AST
    function instrumentNode(node: acorn.Node | any) {
      if (!node || typeof node !== "object") return;

      // Wrap single-statement bodies of control structures into BlockStatements
      const controlStructures = ["IfStatement", "ForStatement", "ForInStatement", "ForOfStatement", "WhileStatement", "DoWhileStatement"];
      if (controlStructures.includes(node.type)) {
        if (node.consequent && node.consequent.type !== "BlockStatement") {
          node.consequent = { type: "BlockStatement", body: [node.consequent] };
        }
        if (node.alternate && node.alternate.type !== "BlockStatement" && node.alternate.type !== "IfStatement") {
          node.alternate = { type: "BlockStatement", body: [node.alternate] };
        }
        if (node.body && node.body.type !== "BlockStatement") {
          node.body = { type: "BlockStatement", body: [node.body] };
        }
      }

      // If it's a BlockStatement or Program, inject traces before every statement
      if (node.type === "BlockStatement" || node.type === "Program") {
        const newBody: acorn.Node[] | any[] = [];
        for (const child of node.body) {
          // Don't trace function declarations or already injected traces
          if (
            child.type === "FunctionDeclaration" ||
            (child.type === "ExpressionStatement" &&
              child.expression.type === "CallExpression" &&
              child.expression.callee.name === "__trace")
          ) {
            newBody.push(child);
            continue;
          }

          const line = child.loc?.start.line || 1;
          const traceNode = {
            type: "ExpressionStatement",
            expression: {
              type: "CallExpression",
              callee: { type: "Identifier", name: "__trace" },
              arguments: [
                { type: "Literal", value: line },
                {
                  type: "CallExpression",
                  callee: { type: "Identifier", name: "eval" },
                  arguments: [{ type: "Literal", value: `(${buildLocals})` }],
                },
              ],
            },
          };

          newBody.push(traceNode as any);
          newBody.push(child);
        }
        node.body = newBody;
      }

      // Recursively process children
      for (const key in node) {
        if (key === "loc" || key === "range") continue;
        const child = node[key];
        if (Array.isArray(child)) {
          child.forEach(instrumentNode);
        } else if (child && typeof child === "object") {
          instrumentNode(child);
        }
      }
    }

    instrumentNode(ast);

    return generate(ast);
  } catch (err) {
    console.error("Failed to instrument JS:", err);
    return code;
  }
}
