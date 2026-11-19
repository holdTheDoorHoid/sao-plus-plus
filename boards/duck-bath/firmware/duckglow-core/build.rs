//! Writes the fading curve (a raised cosine, 1024 steps from 0 up to 65535 and
//! back, then a rest of 128 zeros at the bottom) into OUT_DIR/curve.rs.
//! The maker's firmware uses the same curve shape; this table is computed
//! here from the formula, not copied.
use std::{env, fs, path::Path};

fn main() {
    let steps = 1024usize;
    let rest = 128usize;
    let mut out = String::from("/// Fading curve: see build.rs.\npub const CURVE: [u16; ");
    out += &format!("{}] = [", steps + rest);
    for n in 0..steps {
        let a = 2.0 * std::f64::consts::PI * n as f64 / steps as f64 + 1.5 * std::f64::consts::PI;
        let v = ((a.sin() + 1.0) * 32768.0) as i64;
        out += &format!("{},", v.clamp(0, 65535));
    }
    for _ in 0..rest {
        out += "0,";
    }
    out += "];\n";
    let dst = Path::new(&env::var("OUT_DIR").unwrap()).join("curve.rs");
    fs::write(dst, out).unwrap();
    println!("cargo:rerun-if-changed=build.rs");
}
