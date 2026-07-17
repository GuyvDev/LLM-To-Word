use std::{env, fs, process};

use md2docx_core::{CompileOptions, compile_docx};

fn main() {
    if let Err(error) = run() {
        eprintln!("md2docx-core: {error}");
        process::exit(1);
    }
}

fn run() -> Result<(), String> {
    let mut args = env::args().skip(1);
    let input = args
        .next()
        .ok_or("usage: md2docx-core <input.md> <output.docx> [source]")?;
    let output = args
        .next()
        .ok_or("usage: md2docx-core <input.md> <output.docx> [source]")?;
    let source = args.next().unwrap_or_else(|| "auto".into());
    let markdown = fs::read_to_string(&input).map_err(|e| format!("cannot read {input}: {e}"))?;
    let bytes = compile_docx(
        &markdown,
        &CompileOptions {
            source,
            ..Default::default()
        },
    )?;
    fs::write(&output, bytes).map_err(|e| format!("cannot write {output}: {e}"))
}
