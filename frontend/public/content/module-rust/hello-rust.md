## 🦀 Welcome to the Rust programming language sandbox! Rust is a systems programming language focused on safety, speed, and concurrency.

<div align="center">
    <img width="300" height=auto alt="image" src="https://github.com/user-attachments/assets/99eb3058-9489-44f7-b4b7-ef2a767747b9" />
</div>

---

## 🛠️ Hand-On Task: Simple Rust Function

### In this exercise, you'll write a simple Rust function that adds two numbers.

```rust
// Main Function/The entry point where the program begins execution
fn main() {
    // Declare two immutable integer variables
    let num1 = 10;
    let num2 = 22;
    
    // Call the add function and store the returned value
    let sum = add(num1, num2);
    
    // Print the result to the console using placeholders
    println!("The sum of {} and {} is: {}", num1, num2, sum);
}

// Function to add 2 no.s: Taking two 32-bit integers and returning a 32-bit integer
fn add(a: i32, b: i32) -> i32 {
    // An expression without a semicolon is implicitly returned
    a + b
}
```

#### Here is the detailed breakdown of how each part of the code works:

* **`fn main() { ... }`**
  * This defines the `main` function, which acts as the mandatory entry point for every executable Rust program. When you run the code, execution begins here.

* **`let num1 = 10;` and `let num2 = 22;`**
  * The `let` keyword declares variables. In Rust, variables are **immutable** (cannot be changed after creation) by default. The compiler automatically figures out (infers) that these numbers are 32-bit signed integers (`i32`).

* **`let sum = add(num1, num2);`**
  * This line calls the custom `add` function, passing the values of `num1` and `num2` as input arguments. The final result returned by the function is then bound to a new variable named `sum`.

* **`println!("...", num1, num2, sum);`**
  * `println!` is a **macro** (indicated by the `!`), which prints text to the screen followed by a new line. The empty curly braces `{}` serve as sequential placeholders that are replaced by the values of `num1`, `num2`, and `sum` at runtime.

* **`fn add(a: i32, b: i32) -> i32`**
  * This defines a custom function named `add`. It accepts two inputs (`a` and `b`) and explicitly defines their data types as `i32` (32-bit signed integers). The `-> i32` syntax declares that the function's final output will also be an `i32`.

* **`a + b`**
  * This is an **expression** that calculates the sum of `a` and `b`. Because it is the final line of the function block and **lacks a trailing semicolon**, Rust automatically returns this value to the caller without requiring an explicit `return` keyword.

---

### Steps:

**1.** Visit [this site](https://javascript-code-sandbox.netlify.app/) to access a live Interactive JavaScript Sandbox tool.

<img width="1073" height="551" alt="image" src="https://github.com/user-attachments/assets/3045e128-ca1e-412b-b831-bddbde8ab48b" />

**2.** Next, you select the code that is already in the editor and delete it. Copy and paste the above code provided to add 2 numbers into the editor.

**3.** Then, you click the red **Run** button above the editor. This starts the program inside the sandbox.

**4.** After that, you look at the Output panel on the right side of the page.

**5.** For the code shown in the screenshot, the **output** should look like this:

<img width="866" height="374" alt="image" src="https://github.com/user-attachments/assets/3a8ddf2b-f91a-4bd0-898f-cb7b40ce8ad6" />

---

## 🎯 Key Concepts

- **`fn`** declares a function
- **`-> i32`** specifies the return type
- **`a: i32`** declares a parameter with type `i32` (32-bit integer)
- The last expression is returned implicitly

Try writing the `add` function that returns the sum of two numbers!
