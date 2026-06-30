# Hello, Rust!

Welcome to the Rust programming language sandbox! Rust is a systems programming language focused on safety, speed, and concurrency.

## Your First Rust Function

In this exercise, you'll write a simple Rust function that adds two numbers.

```rust
fn add(a: i32, b: i32) -> i32 {
    a + b
}
```

Rust uses `fn` to declare functions, and the last expression in a function is its return value (no `return` keyword needed for simple expressions).

## Key Concepts

- **`fn`** declares a function
- **`-> i32`** specifies the return type
- **`a: i32`** declares a parameter with type `i32` (32-bit integer)
- The last expression is returned implicitly

Try writing the `add` function that returns the sum of two numbers!
