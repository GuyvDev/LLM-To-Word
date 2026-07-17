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
    docx::compile(markdown, options)
}

pub fn compile_rich_html(markdown: &str, options: &CompileOptions) -> String {
    let mut parser = parser_options(options.effective_profile());
    // LLM status lines and similar single-newline content must remain separate
    // when pasted into Word instead of collapsing into one long sentence.
    parser.render.hardbreaks = true;
    let html = markdown_to_html(markdown, &parser);
    let html = add_rtl_table_direction(&html);
    clipboard_html::render(&html)
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
}
