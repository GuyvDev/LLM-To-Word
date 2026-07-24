//! Canonical md2docx compiler.
//!
//! Parse once with Comrak, then render the same document tree as DOCX or rich
//! HTML. Platform projects only acquire input and deliver output.

mod clipboard_html;
mod docx;
mod math;
mod profile;
mod theme;

pub use profile::{DialectProfile, profile_for_source};

use comrak::{Options, markdown_to_html};
use serde::{Deserialize, Serialize};

#[cfg(target_arch = "wasm32")]
use wasm_bindgen::prelude::*;

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct CompileOptions {
    #[serde(default)]
    pub source: String,
    #[serde(default)]
    pub profile: DialectProfile,
    #[serde(default = "default_rtl_font")]
    pub rtl_font: String,
    #[serde(default = "default_base_font")]
    pub base_font: String,
}

fn default_rtl_font() -> String {
    "Arial".into()
}
fn default_base_font() -> String {
    "Arial".into()
}

impl Default for CompileOptions {
    fn default() -> Self {
        Self {
            source: String::new(),
            profile: DialectProfile::Auto,
            rtl_font: default_rtl_font(),
            base_font: default_base_font(),
        }
    }
}

impl CompileOptions {
    pub fn effective_profile(&self) -> DialectProfile {
        if self.profile == DialectProfile::Auto {
            profile_for_source(&self.source)
        } else {
            self.profile
        }
    }
}

pub fn parser_options(profile: DialectProfile) -> Options<'static> {
    let mut options = Options::default();
    let extended = profile != DialectProfile::CommonMark;
    options.extension.strikethrough = extended;
    options.extension.tagfilter = extended;
    options.extension.table = extended;
    options.extension.autolink = extended;
    options.extension.tasklist = extended;
    options.extension.superscript = extended;
    options.extension.footnotes = extended;
    options.extension.inline_footnotes = extended;
    options.extension.description_lists = extended;
    options.extension.multiline_block_quotes = extended;
    options.extension.math_dollars = extended;
    options.extension.math_code = extended;
    options.extension.alerts = extended;
    options.extension.underline = extended;
    options.extension.subscript = extended;
    options.extension.spoiler = extended;
    options.extension.wikilinks_title_after_pipe = extended;
    options.extension.cjk_friendly_emphasis = extended;
    options.extension.subtext = extended;
    options.extension.highlight = extended;
    options.extension.insert = extended;
    options.extension.block_directive = extended;
    options.parse.smart = false;
    options.parse.relaxed_tasklist_matching = true;
    options.parse.tasklist_in_table = true;
    options.parse.relaxed_autolinks = extended;
    options.render.full_info_string = true;
    options.render.figure_with_caption = extended;
    options.render.tasklist_classes = extended;
    options.render.r#unsafe = false;
    options
}

pub fn compile_docx(markdown: &str, options: &CompileOptions) -> Result<Vec<u8>, String> {
    docx::compile(&normalize_markdown(markdown), options)
}

pub fn compile_rich_html(markdown: &str, options: &CompileOptions) -> String {
    let markdown = normalize_markdown(markdown);
    let mut parser = parser_options(options.effective_profile());
    // LLM status lines and similar single-newline content must remain separate
    // when pasted into Word instead of collapsing into one long sentence.
    parser.render.hardbreaks = true;
    let html = markdown_to_html(&markdown, &parser);
    let html = add_rtl_table_direction(&html);
    clipboard_html::render(&html)
}

fn normalize_markdown(markdown: &str) -> String {
    let characters = markdown.chars().collect::<Vec<_>>();
    let mut output = String::with_capacity(markdown.len());
    let mut index = 0;
    while index < characters.len() {
        let character = characters[index];
        if character == '—' {
            output.push('-');
            index += 1;
            continue;
        }
        if matches!(character as u32, 0x200e | 0x200f | 0x202a..=0x202e | 0x2066..=0x2069) {
            index += 1;
            continue;
        }
        if matches!(character as u32, 0x0590..=0x05ff)
            && characters.get(index + 1) == Some(&'-')
            && characters
                .get(index + 2)
                .is_some_and(|next| next.is_ascii_alphabetic())
        {
            output.push(character);
            output.push('־');
            index += 2;
            continue;
        }
        output.push(character);
        index += 1;
    }
    mirror_rtl_text_arrows(&output)
}

fn mirror_rtl_text_arrows(markdown: &str) -> String {
    let mut output = String::with_capacity(markdown.len());
    let mut fenced = false;
    for line in markdown.split_inclusive('\n') {
        let trimmed = line.trim_start();
        let fence_line = trimmed.starts_with("```") || trimmed.starts_with("~~~");
        if fence_line {
            fenced = !fenced;
            output.push_str(line);
            continue;
        }
        if fenced || !line.chars().any(|c| matches!(c as u32, 0x0590..=0x08ff)) {
            output.push_str(line);
            continue;
        }
        let mut inline_code = false;
        let mut inline_math = false;
        let mut escaped = false;
        for character in line.chars() {
            if escaped {
                output.push(character);
                escaped = false;
                continue;
            }
            if character == '\\' {
                output.push(character);
                escaped = true;
                continue;
            }
            if character == '`' && !inline_math {
                inline_code = !inline_code;
                output.push(character);
                continue;
            }
            if character == '$' && !inline_code {
                inline_math = !inline_math;
                output.push(character);
                continue;
            }
            output.push(match character {
                '→' if !inline_code && !inline_math => '←',
                '←' if !inline_code && !inline_math => '→',
                _ => character,
            });
        }
    }
    output
}

fn add_rtl_table_direction(html: &str) -> String {
    let mut output = String::with_capacity(html.len() + 32);
    let mut remaining = html;
    while let Some(start) = remaining.find("<table>") {
        let before = &remaining[..start];
        output.push_str(before);
        let table_and_after = &remaining[start..];
        let Some(end) = table_and_after.find("</table>") else {
            output.push_str(table_and_after);
            return output;
        };
        let end = end + "</table>".len();
        let table = &table_and_after[..end];
        if table.chars().any(|ch| matches!(ch as u32, 0x0590..=0x08ff)) {
            output.push_str(&table.replacen("<table>", "<table dir=\"rtl\">", 1));
        } else {
            output.push_str(table);
        }
        remaining = &table_and_after[end..];
    }
    output.push_str(remaining);
    output
}

#[cfg_attr(target_arch = "wasm32", wasm_bindgen)]
pub fn convert_docx(markdown: &str, source: &str) -> Result<Vec<u8>, String> {
    compile_docx(
        markdown,
        &CompileOptions {
            source: source.into(),
            ..Default::default()
        },
    )
}

#[cfg_attr(target_arch = "wasm32", wasm_bindgen)]
pub fn convert_html(markdown: &str, source: &str) -> String {
    compile_rich_html(
        markdown,
        &CompileOptions {
            source: source.into(),
            ..Default::default()
        },
    )
}

#[cfg_attr(target_arch = "wasm32", wasm_bindgen)]
pub fn detected_profile(source: &str) -> String {
    profile_for_source(source).as_str().into()
}

#[cfg_attr(target_arch = "wasm32", wasm_bindgen)]
pub fn capabilities_json() -> String {
    serde_json::json!({
        "engine": "md2docx-core",
        "version": env!("CARGO_PKG_VERSION"),
        "profiles": DialectProfile::all().iter().map(|p| p.as_str()).collect::<Vec<_>>(),
        "outputs": ["docx", "rich-html"],
        "markdown": "CommonMark 0.31.2 + GFM + md2docx extensions"
    })
    .to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn source_selects_a_profile() {
        assert_eq!(profile_for_source("chatgpt"), DialectProfile::Llm);
        assert_eq!(profile_for_source("github.com"), DialectProfile::Github);
        assert_eq!(profile_for_source("unknown"), DialectProfile::Gfm);
    }

    #[test]
    fn extended_html_supports_fenced_bash_and_tables() {
        let source = "| א | ב |\n|---|---|\n| 1 | 2 |\n\n```bash\necho ok\n```";
        let html = compile_rich_html(source, &CompileOptions::default());
        assert!(html.contains("<table dir=\"rtl\" style="));
        assert!(html.contains("language-bash"));
    }

    #[test]
    fn shared_normalization_stabilizes_word_punctuation() {
        assert_eq!(
            normalize_markdown("ה-Roadmap — ו-Compliance \u{2066}safe\u{2069}"),
            "ה־Roadmap - ו־Compliance safe"
        );
    }

    #[test]
    fn rtl_prose_arrows_are_mirrored_but_code_and_math_are_not() {
        let source =
            "רצף: תל אביב → גוש דן\n\nעברית $a → b$ ו־`x → y`\n\n```text\nעברית → code\n```";
        let normalized = normalize_markdown(source);
        assert!(normalized.contains("תל אביב ← גוש דן"));
        assert!(normalized.contains("$a → b$"));
        assert!(normalized.contains("`x → y`"));
        assert!(normalized.contains("עברית → code"));
        let html = compile_rich_html(source, &CompileOptions::default());
        assert!(html.contains("תל אביב ← גוש דן"));
    }
}
