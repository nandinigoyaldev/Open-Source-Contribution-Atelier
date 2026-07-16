## 🇯‌🇸‌ JavaScript is the programming language of the web. In this lesson, we will learn how to write basic JavaScript functions and see the output directly in the browser, and delve into the topic of Web Workers.

<img width="1492" height="312" alt="image" src="https://github.com/user-attachments/assets/e247359d-fbc6-436d-8c2a-0d53db6e85b7" />

---

## 🛠️ Hands-On Task: Simple JavaScript Program

### Steps

**1.** Visit [this site](https://javascript-code-sandbox.netlify.app/) to access a live Interactive JavaScript Sandbox tool.

<img width="1402" height="908" alt="image" src="https://github.com/user-attachments/assets/2f87bb6e-d846-432d-9dc5-6072a0239ac7" />

**2.** First, you look at the editor panel on the left side of the page. This is where the JavaScript code is written.

**3.** Next, you can use the code that is already in the editor, or you can type your own code into that editor.

**4.** Then, you click the teal **Run** button above the editor. This starts the program inside the sandbox.

**5.** After that, you look at the Console Output panel on the right side of the page. This is where the sandbox shows messages from console.log(), console.info(), console.warn(), console.error(), and any value returned by the code.

**6.** For the code shown in the screenshot, the **output** should look like this:

```
Items: keyboard, notebook, adapter

Total: 116.20

116.2

Program finished.
```

- The code creates a cart array with three products: a keyboard, a notebook, and an adapter. Each product has a name and a price.
- The code then uses reduce() to add the three prices together. The total is 84.95 + 12.5 + 18.75, which equals 116.2.
- The first console.log() prints the product names as one line: keyboard, notebook, adapter.
- The second console.log() prints the total with two decimal places, so 116.2 becomes 116.20.
- Finally, return total sends the raw number back to the sandbox. That is why the console also shows 116.2 after the logged messages.

---

- **If the code runs too long, you can click Stop.** The sandbox also stops code automatically after 5 seconds.
- **If you want to try different code, you can click one of the example cards** such as Array tools, Async test, or Loop output, then click Run again.

---

## 🌐 👨‍🔧 What is a Web Worker?

A Web Worker allows you to run JavaScript code in the background, completely separate from the main browser thread.

This means even if your code takes a long time to run (or accidentally enters an infinite loop), it WON'T freeze the webpage!

---

## 👨‍🔧 How Web Workers Play a Role in JavaScript Programs

### Here is a breakdown of how web workers play a role in the JavaScript program you just executed in the interactive sandbox.

1. First, you type JavaScript into the editor on the left side of the page, or you use the starter code that is already there.

2. Next, you click the teal **Run** button. The site does not run that code directly inside the main React page. Instead, it creates a separate browser Web Worker.

3. A Web Worker is a background browser thread. It lets the site run JavaScript away from the main page so the interface can stay responsive while the user code is executing.

4. When you click Run, the site takes the code from the editor and passes it into a helper that builds a small worker script. That worker script includes console-handling code, error handling, and the user’s JavaScript.

5. The site turns that worker script into a Blob, creates a temporary URL for it with URL.createObjectURL(), and starts it with new Worker(workerUrl).

6. Inside the worker, the user’s code is wrapped in an async function. That is why the editor can run normal JavaScript and also supports await.

7. The worker receives a custom console object. When the user code calls console.log(), console.info(), console.warn(), or console.error(), those methods do not write directly to the page. They send a message back to the React app with self.postMessage().

8. The React app listens for worker messages with worker.onmessage. When it receives an output message, it adds a new line to the Console Output panel on the right side of the page.

- If the user code returns a value, the worker formats that value and sends it back as a result message. That is why the sample code logs Total: 116.20 and then also shows the returned number 116.2.
- If the code throws an error or an async promise fails, the worker catches it and sends an error message back to the console panel. The page can show the error without crashing the whole React interface.

9. The site also starts a 5 second timeout when the worker begins. If the code runs too long, the timeout calls the stop logic and terminates the worker.

10. When the program finishes normally, the worker sends a complete message. The React app clears the timeout, terminates the worker, revokes the temporary worker URL, changes the button back from Stop to Run, and prints Program finished.

11. If the user clicks Stop, the site terminates the active worker immediately. This is possible because the user code is running in the worker instead of blocking the main page.

For the screenshot’s starter code, the worker runs the cart calculation, sends the two console.log() messages back to the page, sends the returned total back as a result, and then tells the page the program is complete.
