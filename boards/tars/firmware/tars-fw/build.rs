fn main() {
    // Exactly one chip feature must be chosen.
    let chips = ["esp32c3", "esp32c6"]
        .iter()
        .filter(|c| std::env::var(format!("CARGO_FEATURE_{}", c.to_uppercase())).is_ok())
        .count();
    if chips != 1 {
        panic!("\n\nChoose exactly one chip: use `cargo c3` or `cargo c6` (see README.md), not plain `cargo build`.\n");
    }
}
