use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum DialectProfile {
    #[default]
    Auto,
    CommonMark,
    Gfm,
    Github,
    Hackmd,
    Llm,
}

impl DialectProfile {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Auto => "auto",
            Self::CommonMark => "commonmark",
            Self::Gfm => "gfm",
            Self::Github => "github",
            Self::Hackmd => "hackmd",
            Self::Llm => "llm",
        }
    }

    pub const fn all() -> &'static [Self] {
        &[
            Self::Auto,
            Self::CommonMark,
            Self::Gfm,
            Self::Github,
            Self::Hackmd,
            Self::Llm,
        ]
    }
}

pub fn profile_for_source(source: &str) -> DialectProfile {
    let value = source.trim().to_ascii_lowercase();
    if value == "commonmark" {
        DialectProfile::CommonMark
    } else if value == "gfm" {
        DialectProfile::Gfm
    } else if value == "github" || value.contains("github.com") {
        DialectProfile::Github
    } else if value == "hackmd" || value.contains("hackmd.io") {
        DialectProfile::Hackmd
    } else if value == "llm" {
        DialectProfile::Llm
    } else if value.contains("github") {
        DialectProfile::Github
    } else if value.contains("hackmd") {
        DialectProfile::Hackmd
    } else if [
        "chatgpt",
        "openai",
        "claude",
        "gemini",
        "copilot",
        "grok",
        "perplexity",
        "deepseek",
        "llm",
    ]
    .iter()
    .any(|name| value.contains(name))
    {
        DialectProfile::Llm
    } else {
        DialectProfile::Gfm
    }
}
