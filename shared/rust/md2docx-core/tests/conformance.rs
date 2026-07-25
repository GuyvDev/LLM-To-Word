use std::io::{Cursor, Read};

use md2docx_core::{CompileOptions, DialectProfile, compile_docx, compile_rich_html};
use quick_xml::Reader;
use quick_xml::events::Event;
use serde::Deserialize;
use zip::ZipArchive;

#[derive(Debug, Deserialize)]
struct Case {
    id: String,
    source: String,
    markdown: String,
    html_contains: Vec<String>,
    html_not_contains: Vec<String>,
    docx_contains: Vec<String>,
    docx_not_contains: Vec<String>,
}

fn corpus() -> Vec<Case> {
    serde_json::from_str(include_str!(
        "../../../../tests/fixtures/markdown_conformance.json"
    ))
    .expect("valid conformance corpus")
}

fn options(source: &str) -> CompileOptions {
    CompileOptions {
        source: source.into(),
        ..Default::default()
    }
}

fn package_xml(bytes: &[u8]) -> (String, String, String) {
    let mut archive = ZipArchive::new(Cursor::new(bytes)).expect("valid DOCX ZIP");
    for required in [
        "[Content_Types].xml",
        "_rels/.rels",
        "word/document.xml",
        "word/styles.xml",
        "word/numbering.xml",
        "word/_rels/document.xml.rels",
    ] {
        assert!(
            archive.by_name(required).is_ok(),
            "missing package part {required}"
        );
    }
    let mut read = |name: &str| {
        let mut value = String::new();
        archive
            .by_name(name)
            .unwrap()
            .read_to_string(&mut value)
            .unwrap();
        value
    };
    let document = read("word/document.xml");
    let styles = read("word/styles.xml");
    let numbering = read("word/numbering.xml");
    validate_xml(&document);
    validate_xml(&styles);
    validate_xml(&numbering);
    (document, styles, numbering)
}

fn validate_xml(value: &str) {
    let mut reader = Reader::from_str(value);
    let mut buffer = Vec::new();
    loop {
        match reader.read_event_into(&mut buffer) {
            Ok(Event::Eof) => break,
            Ok(_) => {}
            Err(error) => panic!(
                "invalid generated XML at {}: {error}",
                reader.buffer_position()
            ),
        }
        buffer.clear();
    }
}

fn assert_only_balanced_compiler_bidi_controls(value: &str) {
    let mut isolate_depth = 0usize;
    for character in value.chars() {
        match character {
            '\u{2066}' => {
                assert_eq!(isolate_depth, 0, "nested LRI in generated OOXML");
                isolate_depth += 1;
            }
            '\u{2069}' => {
                assert_eq!(isolate_depth, 1, "unmatched PDI in generated OOXML");
                isolate_depth -= 1;
            }
            '\u{200e}' | '\u{200f}' | '\u{202a}' | '\u{202b}' | '\u{202c}' | '\u{202d}'
            | '\u{202e}' | '\u{2067}' | '\u{2068}' => {
                panic!(
                    "unsafe BiDi control U+{:04X} in generated OOXML",
                    character as u32
                );
            }
            _ => {}
        }
    }
    assert_eq!(isolate_depth, 0, "unclosed LRI in generated OOXML");
}

#[test]
fn hebrew_benchmark_has_independent_download_and_clipboard_contracts() {
    let markdown = include_str!("../../../../tests/fixtures/hebrew_experiment_benchmark.md");
    let options = options("chatgpt");

    let bytes = compile_docx(markdown, &options).expect("benchmark DOCX compiles");
    let (document, _, _) = package_xml(&bytes);
    assert!(document.contains("<m:oMath"));
    assert!(document.contains("<w:bidiVisual/>"));
    assert!(!document.contains(r"\theta"));

    let html = compile_rich_html(markdown, &options);
    for expected in [
        "<!--StartFragment-->",
        "font-family:Arial",
        "md2docx-math-display",
        "text-align:center;vertical-align:middle",
        "direction:rtl",
        "Status:<br />",
        "θ",
        "α",
        "∇",
    ] {
        assert!(html.contains(expected), "clipboard missing {expected:?}");
    }
    for forbidden in [r"\theta", r"\alpha", r"\nabla", r"\frac", "data-math-style"] {
        assert!(!html.contains(forbidden), "clipboard leaked {forbidden:?}");
    }
}

#[test]
fn spotwize_mixed_bidi_regression_uses_directional_runs_and_mirrored_arrows() {
    let markdown = include_str!("../../../../tests/fixtures/spotwize_bidi_regression.md");
    let options = options("llm");
    let bytes = compile_docx(markdown, &options).expect("Spotwize regression DOCX compiles");
    let (document, _, _) = package_xml(&bytes);

    for expected in [
        "Spotwize",
        "תקציר מנהלים",
        "Roadmap",
        "עקרונות",
        "Density before geography",
    ] {
        assert!(document.contains(expected), "DOCX missing {expected:?}");
    }
    assert!(document.contains("<w:bidi/>"));
    assert!(document.contains("<w:rtl/>"));
    assert!(document.contains("<w:rtl w:val=\"0\"/>"));
    assert!(document.contains("תל אביב ← גוש דן ← ערים נבחרות בישראל"));
    assert!(!document.contains('→'));
    assert_only_balanced_compiler_bidi_controls(&document);

    let html = compile_rich_html(markdown, &options);
    assert!(html.contains("<h2 dir=\"rtl\""));
    assert!(html.contains("תל אביב ← גוש דן ← ערים נבחרות בישראל"));
    assert!(!html.contains('→'));
}

#[test]
fn nested_ltr_brackets_use_a_visual_ltr_run_in_rtl_paragraphs() {
    let markdown = "המסקנה: השילוב בין עברית, English, מספרים 12.5%, וסוגריים {A[0]} נשאר קריא.";
    let docx = compile_docx(markdown, &options("llm")).expect("nested brackets compile");
    let (document, _, _) = package_xml(&docx);
    assert!(document.contains("<w:bdo w:val=\"ltr\">"));
    assert!(document.contains(">{</w:t>"));
    assert!(document.contains(">A</w:t>"));
    assert!(document.contains(">[</w:t>"));
    assert!(document.contains(">0</w:t>"));
    assert!(document.contains(">]</w:t>"));
    assert!(document.contains(">}</w:t>"));
    assert!(!document.contains("\u{2066}{A[0]}\u{2069}"));
    assert!(document.contains("<w:rtl w:val=\"0\"/>"));
    assert!(!document.contains("<w:dir"));
    assert_only_balanced_compiler_bidi_controls(&document);
}

#[test]
fn exact_rtl_status_and_punctuation_regression_uses_simple_visual_brackets() {
    let markdown =
        "# סטטוס: [פעיל] (Beta).\n\n# {A[0]} נשאר קריא.\n\n# השילוב בין עברית, English, מספרים.";
    let docx = compile_docx(markdown, &options("llm")).expect("exact regression compiles");
    let (document, _, _) = package_xml(&docx);

    assert!(document.contains("<w:bdo w:val=\"ltr\">"));
    assert!(document.contains("[פעיל]"));
    assert!(document.contains("\u{2066}(Beta)\u{2069}"));
    assert!(document.contains(">.</w:t>"));
    assert!(document.contains(">{</w:t>"));
    assert!(document.contains(">[</w:t>"));
    assert!(document.contains(">]</w:t>"));
    assert!(document.contains(">}</w:t>"));
    assert!(!document.contains("\u{2066}{A[0]}\u{2069}"));
    assert!(!document.contains("<w:dir"));
    assert!(document.contains("\u{2066}English\u{2069}"));
    assert!(document.contains(">,</w:t>"));
    assert!(!document.contains("English,,"));
    assert!(document.find("[פעיל]").unwrap() < document.find("(Beta)").unwrap());
    assert_only_balanced_compiler_bidi_controls(&document);
}

#[test]
fn shared_corpus_matches_html_and_docx_contracts() {
    for case in corpus() {
        let options = options(&case.source);
        let html = compile_rich_html(&case.markdown, &options);
        for expected in &case.html_contains {
            assert!(
                html.contains(expected),
                "{} HTML missing {expected:?}\n{html}",
                case.id
            );
        }
        for forbidden in &case.html_not_contains {
            assert!(
                !html.contains(forbidden),
                "{} HTML unexpectedly contains {forbidden:?}\n{html}",
                case.id
            );
        }

        let bytes = compile_docx(&case.markdown, &options)
            .unwrap_or_else(|error| panic!("{} DOCX failed: {error}", case.id));
        assert_eq!(&bytes[..4], b"PK\x03\x04", "{} ZIP signature", case.id);
        let (document, styles, numbering) = package_xml(&bytes);
        let searchable = format!("{document}{styles}{numbering}");
        for expected in &case.docx_contains {
            assert!(
                searchable.contains(expected),
                "{} DOCX missing {expected:?}",
                case.id
            );
        }
        for forbidden in &case.docx_not_contains {
            assert!(
                !searchable.contains(forbidden),
                "{} DOCX unexpectedly contains {forbidden:?}",
                case.id
            );
        }
    }
}

#[test]
fn explicit_profile_names_select_every_dialect() {
    for (source, expected) in [
        ("commonmark", DialectProfile::CommonMark),
        ("gfm", DialectProfile::Gfm),
        ("github", DialectProfile::Github),
        ("hackmd", DialectProfile::Hackmd),
        ("llm", DialectProfile::Llm),
    ] {
        assert_eq!(
            options(source).effective_profile(),
            expected,
            "source {source}"
        );
    }
}

#[test]
fn generated_punctuation_combinations_are_deterministic_and_valid() {
    let punctuation = r##"!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~"##;
    let atoms = [
        "Latin",
        "עברית ״׳־׃",
        "العربية ،؛؟",
        "é",
        "😀",
        punctuation,
        "()[]{}（）【】「」",
        "<>&\"'",
    ];
    let wrappers = [
        ("**", "**"),
        ("*", "*"),
        ("`", "`"),
        ("~~", "~~"),
        ("[", "](https://example.com/?q=%5Bx%5D)"),
    ];
    for profile in ["commonmark", "gfm", "github", "hackmd", "llm"] {
        for index in 0..64 {
            let atom = atoms[index % atoms.len()];
            let (open, close) = wrappers[(index / atoms.len()) % wrappers.len()];
            let markdown = format!(
                "### Case {index}: [{atom}] ({punctuation})\n\n{open}{atom}{close}\n\n| A[{index}] | B({atom}) |\n|---|---|\n| `{punctuation}` | {atom} |"
            );
            let first =
                compile_docx(&markdown, &options(profile)).expect("generated case compiles");
            let second =
                compile_docx(&markdown, &options(profile)).expect("generated case recompiles");
            assert_eq!(first, second, "non-deterministic {profile} case {index}");
            package_xml(&first);
        }
    }
}

#[test]
fn empty_long_deep_and_control_character_inputs_stay_valid() {
    let deep_lists = (0..32)
        .map(|depth| {
            format!(
                "{}- level {depth}: [{}] ({})",
                "  ".repeat(depth),
                depth,
                "{}[]()"
            )
        })
        .collect::<Vec<_>>()
        .join("\n");
    let long_text = format!("# Long\n\n{} end.", "אבג ABC ([]) {{}} !? ".repeat(2_000));
    let controls = "legal\tline\ncarriage\r illegal:\u{0}\u{1}\u{8}\u{b}\u{c}\u{1f} end";
    for (name, markdown) in [
        ("empty", ""),
        ("whitespace", "\u{feff} \n\t"),
        ("deep", deep_lists.as_str()),
        ("long", long_text.as_str()),
        ("controls", controls),
    ] {
        let bytes = compile_docx(markdown, &options("llm"))
            .unwrap_or_else(|error| panic!("{name}: {error}"));
        let (document, _, _) = package_xml(&bytes);
        assert!(
            !document
                .chars()
                .any(|ch| matches!(ch as u32, 0x0 | 0x1..=0x8 | 0xb..=0xc | 0xe..=0x1f)),
            "{name} retained illegal XML controls"
        );
    }
}
