document.addEventListener('DOMContentLoaded', function() {
  const codeInput = document.getElementById('codeInput');
  const output = document.getElementById('output');
  const runBtn = document.getElementById('runBtn');
  const clearBtn = document.getElementById('clearBtn');
  const exampleBtn = document.getElementById('exampleBtn');
  const status = document.getElementById('status');

  const examples = {
    basic: `# Basic Julia
println("Hello, World!")
x = 10
y = 20
println("Sum: ", x + y)`,

    function: `# Function example
function greet(name)
    println("Hello, \$name!")
end
greet("Julia")`,

    math: `# Math operations
a = [1, 2, 3, 4, 5]
println("Sum: ", sum(a))
println("Mean: ", mean(a))
println("Squares: ", a .^ 2)`,

    plot: `# Plot example (using Plots.jl)
using Plots
x = 1:10
y = x .^ 2
plot(x, y, title="Squares", xlabel="x", ylabel="x^2")`
  };

  // Load example
  exampleBtn.addEventListener('click', function() {
    const keys = Object.keys(examples);
    const random = keys[Math.floor(Math.random() * keys.length)];
    codeInput.value = examples[random];
  });

  // Clear
  clearBtn.addEventListener('click', function() {
    codeInput.value = '';
    output.textContent = '';
  });

  // Run code (simulated execution)
  runBtn.addEventListener('click', function() {
    const code = codeInput.value.trim();
    if (!code) {
      output.textContent = '⚠️ Please enter some code';
      return;
    }

    status.textContent = '⏳ Running...';
    output.textContent = '';

    // Simulate Julia execution
    setTimeout(() => {
      const lines = code.split('\n');
      let result = '📤 Output:\n\n';
      
      lines.forEach(line => {
        if (line.trim().startsWith('#')) {
          result += line + '\n';
        } else if (line.trim().includes('println')) {
          const match = line.match(/println\("(.+)"\)/);
          if (match) result += match[1] + '\n';
        } else if (line.trim().includes('+') || line.trim().includes('*')) {
          try {
            // Simple evaluation
            const parts = line.split('=');
            if (parts.length > 1) {
              const expr = parts[1].trim();
              const value = eval(expr);
              result += parts[0].trim() + ' = ' + value + '\n';
            }
          } catch (e) {
            result += '⚠️ ' + e.message + '\n';
          }
        } else if (line.trim()) {
          result += '> ' + line + '\n';
        }
      });
      
      result += '\n✅ Execution complete';
      output.textContent = result;
      status.textContent = '✅ Done';
    }, 500);
  });

  // Load initial example
  codeInput.value = examples.basic;
});