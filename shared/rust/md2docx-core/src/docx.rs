use std::io::{Cursor, Write};

use comrak::nodes::{AstNode, ListType, NodeValue};
use comrak::{Arena, parse_document};
use zip::{DateTime, System, ZipWriter, write::SimpleFileOptions};

use crate::{CompileOptions, parser_options, theme};

const W: &str = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";
const M: &str = "http://schemas.openxmlformats.org/officeDocument/2006/math";

#[derive(Clone, Copy, Default)]
struct BlockContext {
    quote: bool,
    list: Option<(bool, usize)>,
    center: bool,
    compact: bool,
    task: Option<bool>,
    rtl: bool,
    after_table: bool,
}

#[derive(Clone, Copy, Default)]
struct InlineStyle {
    bold: bool,
    italic: bool,
    strike: bool,
    mono: bool,
    underline: bool,
    superscript: bool,
    subscript: bool,
    highlight: bool,
}

struct InlineDirectionState {
    base_rtl: bool,
    last_strong: Option<bool>,
}

impl InlineDirectionState {
    fn new(base_rtl: bool) -> Self {
        Self {
            base_rtl,
            last_strong: None,
        }
    }
}

struct Renderer<'a> {
    options: &'a CompileOptions,
    body: String,
    document_rtl: bool,
    after_table: bool,
}

pub fn compile(markdown: &str, options: &CompileOptions) -> Result<Vec<u8>, String> {
    let arena = Arena::new();
    let root = parse_document(
        &arena,
        markdown,
        &parser_options(options.effective_profile()),
    );
    let document_rtl = dominant_rtl(markdown);
    let mut renderer = Renderer {
        options,
        body: String::new(),
        document_rtl,
        after_table: false,
    };
    renderer.render_blocks(
        root,
        BlockContext {
            rtl: document_rtl,
            ..Default::default()
        },
    );
    package(
        renderer.document_xml(),
        renderer.styles_xml(),
        numbering_xml(document_rtl),
    )
}

impl Renderer<'_> {
    fn render_blocks<'a>(&mut self, node: &'a AstNode<'a>, context: BlockContext) {
        for child in node.children() {
            self.render_block(child, context);
        }
    }

    fn render_block<'a>(&mut self, node: &'a AstNode<'a>, context: BlockContext) {
        let data = node.data.borrow();
        match &data.value {
            NodeValue::Document => { drop(data); self.render_blocks(node, context); }
            NodeValue::Paragraph => {
                drop(data);
                let context = BlockContext {
                    after_table: std::mem::take(&mut self.after_table),
                    ..context
                };
                let plain = collect_text(node);
                let rtl = context.rtl || contains_rtl(&plain);
                let mut state = InlineDirectionState::new(rtl);
                let mut content = String::new();
                if let Some(checked) = context.task {
                    content.push_str(&text_runs_with_state(
                        if checked { "☑ " } else { "☐ " },
                        InlineStyle::default(),
                        &self.options.rtl_font,
                        &mut state,
                    ));
                }
                content.push_str(&render_inline_children(
                    node,
                    InlineStyle::default(),
                    &self.options.rtl_font,
                    &mut state,
                ));
                let context = if is_display_math_paragraph(node) { BlockContext { center: true, ..context } } else { context };
                self.body.push_str(&paragraph(&content, &plain, None, context));
            }
            NodeValue::Heading(heading) => {
                let level = heading.level;
                drop(data);
                let context = BlockContext {
                    after_table: std::mem::take(&mut self.after_table),
                    ..context
                };
                let plain = collect_text(node);
                let rtl = context.rtl || contains_rtl(&plain);
                let mut state = InlineDirectionState::new(rtl);
                let content = render_inline_children(
                    node,
                    InlineStyle::default(),
                    &self.options.rtl_font,
                    &mut state,
                );
                self.body.push_str(&paragraph(&content, &plain, Some(format!("Heading{level}")), context));
            }
            NodeValue::BlockQuote | NodeValue::MultilineBlockQuote(_) => {
                drop(data);
                self.render_blocks(node, BlockContext { quote: true, ..context });
            }
            NodeValue::Alert(alert) => {
                let title = alert.title.clone().unwrap_or_else(|| format!("{:?}", alert.alert_type));
                drop(data);
                self.body.push_str(&paragraph(&text_runs(&title, InlineStyle { bold: true, ..Default::default() }, &self.options.rtl_font), &title, None, BlockContext { quote: true, ..context }));
                self.render_blocks(node, BlockContext { quote: true, ..context });
            }
            NodeValue::List(list) => {
                let ordered = list.list_type == ListType::Ordered;
                let depth = context.list.map(|(_, depth)| depth + 1).unwrap_or(0);
                drop(data);
                self.render_blocks(node, BlockContext { list: Some((ordered, depth)), ..context });
            }
            NodeValue::Item(_) | NodeValue::DescriptionItem(_) | NodeValue::DescriptionTerm | NodeValue::DescriptionDetails => {
                drop(data);
                self.render_blocks(node, context);
            }
            NodeValue::TaskItem(item) => {
                let checked = item.symbol.is_some();
                drop(data);
                self.render_blocks(node, BlockContext { task: Some(checked), ..context });
            }
            NodeValue::CodeBlock(code) => {
                let literal = code.literal.clone();
                let language = code.info.split_whitespace().next().unwrap_or("").to_string();
                drop(data);
                self.body.push_str(&code_block(&literal, &language));
            }
            NodeValue::FrontMatter(literal) => {
                let literal = literal.clone();
                drop(data);
                self.body.push_str(&code_block(&literal, "front-matter"));
            }
            NodeValue::Subtext => {
                drop(data);
                let plain = collect_text(node);
                let rtl = context.rtl || contains_rtl(&plain);
                let mut state = InlineDirectionState::new(rtl);
                let content = render_inline_children(
                    node,
                    InlineStyle {
                        italic: true,
                        ..Default::default()
                    },
                    &self.options.rtl_font,
                    &mut state,
                );
                self.body.push_str(&paragraph(&content, &plain, None, context));
            }
            NodeValue::ThematicBreak => self.body.push_str("<w:p><w:pPr><w:pBdr><w:bottom w:val=\"single\" w:sz=\"6\" w:space=\"1\" w:color=\"auto\"/></w:pBdr></w:pPr></w:p>"),
            NodeValue::Table(_) => {
                drop(data);
                self.body.push_str(&render_table(node, &self.options.rtl_font, context.rtl));
                self.after_table = true;
            }
            NodeValue::HtmlBlock(html) => {
                let literal = html.literal.clone();
                drop(data);
                self.body.push_str(&paragraph(&text_runs(&literal, InlineStyle { mono: true, ..Default::default() }, &self.options.rtl_font), &literal, None, context));
            }
            NodeValue::FootnoteDefinition(definition) => {
                let label = format!("[{}]", definition.name);
                drop(data);
                self.body.push_str(&paragraph(&text_runs(&label, InlineStyle { bold: true, ..Default::default() }, &self.options.rtl_font), &label, None, context));
                self.render_blocks(node, context);
            }
            _ => { drop(data); self.render_blocks(node, context); }
        }
    }

    fn document_xml(&self) -> String {
        let bidi = if self.document_rtl { "<w:bidi/>" } else { "" };
        format!(
            "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><w:document xmlns:w=\"{W}\" xmlns:m=\"{M}\"><w:body>{}<w:sectPr>{bidi}<w:pgSz w:w=\"11906\" w:h=\"16838\"/><w:pgMar w:top=\"1134\" w:right=\"1134\" w:bottom=\"1134\" w:left=\"1134\"/></w:sectPr></w:body></w:document>",
            self.body
        )
    }

    fn styles_xml(&self) -> String {
        let heading_xml = theme::HEADINGS.iter().map(|heading| {
            let (level, size, color, before, after) = (heading.level, heading.half_points, heading.color, heading.before_twips, heading.after_twips);
            let border = if level == 1 { format!("<w:pBdr><w:bottom w:val=\"single\" w:sz=\"6\" w:space=\"4\" w:color=\"{}\"/></w:pBdr>", theme::HEADING_BORDER) } else { String::new() };
            format!("<w:style w:type=\"paragraph\" w:styleId=\"Heading{level}\"><w:name w:val=\"heading {level}\"/><w:basedOn w:val=\"Normal\"/><w:next w:val=\"Normal\"/><w:qFormat/><w:pPr><w:keepNext/><w:keepLines/><w:spacing w:before=\"{before}\" w:after=\"{after}\"/>{border}</w:pPr><w:rPr><w:rFonts w:ascii=\"{}\" w:hAnsi=\"{}\" w:cs=\"{}\"/><w:b/><w:color w:val=\"{color}\"/><w:sz w:val=\"{size}\"/><w:szCs w:val=\"{size}\"/></w:rPr></w:style>", theme::FONT, theme::FONT, theme::FONT)
        }).collect::<String>();
        format!(
            "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><w:styles xmlns:w=\"{W}\"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii=\"{}\" w:hAnsi=\"{}\" w:cs=\"{}\"/><w:sz w:val=\"{}\"/><w:szCs w:val=\"{}\"/><w:color w:val=\"{}\"/><w:lang w:val=\"en-US\" w:bidi=\"he-IL\"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after=\"{}\" w:line=\"{}\" w:lineRule=\"auto\"/><w:widowControl/></w:pPr></w:pPrDefault></w:docDefaults><w:style w:type=\"paragraph\" w:default=\"1\" w:styleId=\"Normal\"><w:name w:val=\"Normal\"/><w:qFormat/></w:style>{heading_xml}<w:style w:type=\"table\" w:styleId=\"TableGrid\"><w:name w:val=\"Table Grid\"/></w:style></w:styles>",
            xml(&self.options.base_font),
            xml(&self.options.base_font),
            xml(&self.options.rtl_font),
            theme::BODY_HALF_POINTS,
            theme::BODY_HALF_POINTS,
            theme::BODY_COLOR,
            theme::BODY_AFTER_TWIPS,
            theme::BODY_LINE_TWIPS
        )
    }
}

fn paragraph(content: &str, plain: &str, style: Option<String>, context: BlockContext) -> String {
    let rtl = context.rtl || contains_rtl(plain);
    let mut properties = String::new();
    if let Some(style) = style {
        properties.push_str(&format!("<w:pStyle w:val=\"{}\"/>", xml(&style)));
    }
    if rtl {
        properties.push_str("<w:bidi/>");
    }
    if context.center {
        properties.push_str("<w:jc w:val=\"center\"/>");
    } else if rtl {
        properties.push_str("<w:jc w:val=\"start\"/>");
    }
    if context.compact {
        properties.push_str(
            "<w:spacing w:before=\"0\" w:after=\"0\" w:line=\"240\" w:lineRule=\"auto\"/>",
        );
    } else if context.center {
        properties.push_str("<w:spacing w:before=\"60\" w:after=\"60\"/>");
    } else if context.after_table {
        properties.push_str("<w:spacing w:before=\"160\"/>");
    }
    if context.quote {
        let (side, indent) = if rtl {
            ("right", "right")
        } else {
            ("left", "left")
        };
        properties.push_str(&format!("<w:ind w:{indent}=\"360\"/><w:shd w:val=\"clear\" w:fill=\"{}\"/><w:pBdr><w:{side} w:val=\"single\" w:sz=\"14\" w:space=\"5\" w:color=\"{}\"/></w:pBdr>", theme::QUOTE_FILL, theme::QUOTE_BORDER));
    }
    if let Some((ordered, depth)) = context.list {
        properties.push_str(&format!(
            "<w:numPr><w:ilvl w:val=\"{}\"/><w:numId w:val=\"{}\"/></w:numPr>",
            depth.min(8),
            if ordered { 2 } else { 1 }
        ));
    }
    format!(
        "<w:p>{}<w:pPr></w:pPr>{content}</w:p>",
        if properties.is_empty() {
            String::new()
        } else {
            format!("<w:pPr>{properties}</w:pPr>")
        }
    )
    .replace("<w:pPr></w:pPr>", "")
}

fn code_block(literal: &str, language: &str) -> String {
    let language_run = if language.is_empty() {
        String::new()
    } else {
        format!(
            "{}<w:r><w:br/></w:r>",
            text_runs(
                language,
                InlineStyle {
                    bold: true,
                    mono: true,
                    ..Default::default()
                },
                "Arial"
            )
        )
    };
    format!(
        "<w:p><w:pPr><w:ind w:left=\"360\"/><w:shd w:val=\"clear\" w:fill=\"F3F4F6\"/><w:pBdr><w:left w:val=\"single\" w:sz=\"8\" w:color=\"94A3B8\"/></w:pBdr></w:pPr>{language_run}{}</w:p>",
        text_runs(
            literal.trim_end_matches('\n'),
            InlineStyle {
                mono: true,
                ..Default::default()
            },
            "Arial"
        )
    )
}

fn render_table<'a>(node: &'a AstNode<'a>, rtl_font: &str, document_rtl: bool) -> String {
    let rtl = document_rtl || contains_rtl(&collect_text(node));
    let table_rows = node.children().collect::<Vec<_>>();
    let columns = table_rows
        .iter()
        .map(|row| row.children().count())
        .max()
        .unwrap_or(1);
    let column_width = 9000 / columns.max(1);
    let mut rows_xml = String::new();
    for (row_index, row) in table_rows.into_iter().enumerate() {
        let is_header = matches!(row.data.borrow().value, NodeValue::TableRow(true));
        let cells = row.children().collect::<Vec<_>>();
        let mut cells_xml = String::new();
        for cell in cells {
            let plain = collect_text(cell);
            let mut state = InlineDirectionState::new(rtl);
            let content = render_inline_children(
                cell,
                InlineStyle {
                    bold: is_header,
                    ..Default::default()
                },
                rtl_font,
                &mut state,
            );
            let para = paragraph(
                &content,
                &plain,
                None,
                BlockContext {
                    center: true,
                    compact: true,
                    rtl,
                    ..Default::default()
                },
            );
            let shade = if is_header {
                format!(
                    "<w:shd w:val=\"clear\" w:fill=\"{}\"/>",
                    theme::TABLE_HEADER_FILL
                )
            } else if row_index % 2 == 0 {
                format!("<w:shd w:val=\"clear\" w:fill=\"{}\"/>", theme::QUOTE_FILL)
            } else {
                String::new()
            };
            cells_xml.push_str(&format!("<w:tc><w:tcPr><w:tcW w:w=\"{column_width}\" w:type=\"dxa\"/><w:vAlign w:val=\"center\"/>{shade}</w:tcPr>{para}</w:tc>"));
        }
        rows_xml.push_str(&format!("<w:tr>{cells_xml}</w:tr>"));
    }
    let grid = (0..columns)
        .map(|_| format!("<w:gridCol w:w=\"{column_width}\"/>"))
        .collect::<String>();
    let bidi = if rtl { "<w:bidiVisual/>" } else { "" };
    format!(
        "<w:tbl><w:tblPr><w:tblStyle w:val=\"TableGrid\"/><w:tblW w:w=\"9000\" w:type=\"dxa\"/><w:tblLayout w:type=\"fixed\"/><w:jc w:val=\"center\"/>{bidi}<w:tblCellMar><w:top w:w=\"80\" w:type=\"dxa\"/><w:left w:w=\"100\" w:type=\"dxa\"/><w:bottom w:w=\"80\" w:type=\"dxa\"/><w:right w:w=\"100\" w:type=\"dxa\"/></w:tblCellMar><w:tblBorders><w:top w:val=\"single\" w:sz=\"6\" w:color=\"{border}\"/><w:left w:val=\"single\" w:sz=\"6\" w:color=\"{border}\"/><w:bottom w:val=\"single\" w:sz=\"6\" w:color=\"{border}\"/><w:right w:val=\"single\" w:sz=\"6\" w:color=\"{border}\"/><w:insideH w:val=\"single\" w:sz=\"4\" w:color=\"{inner}\"/><w:insideV w:val=\"single\" w:sz=\"4\" w:color=\"{inner}\"/></w:tblBorders></w:tblPr><w:tblGrid>{grid}</w:tblGrid>{rows_xml}</w:tbl>",
        border = theme::TABLE_BORDER,
        inner = theme::TABLE_INNER_BORDER
    )
}

fn render_inline_children<'a>(
    node: &'a AstNode<'a>,
    style: InlineStyle,
    rtl_font: &str,
    state: &mut InlineDirectionState,
) -> String {
    let mut output = String::new();
    for child in node.children() {
        output.push_str(&render_inline(child, style, rtl_font, state));
    }
    output
}

fn render_inline<'a>(
    node: &'a AstNode<'a>,
    mut style: InlineStyle,
    rtl_font: &str,
    state: &mut InlineDirectionState,
) -> String {
    let data = node.data.borrow();
    match &data.value {
        NodeValue::Text(value) => text_runs_with_state(value, style, rtl_font, state),
        NodeValue::Code(code) => {
            state.last_strong = Some(false);
            word_run(
                &code.literal,
                InlineStyle {
                    mono: true,
                    ..style
                },
                rtl_font,
                false,
            )
        }
        NodeValue::SoftBreak => text_runs_with_state(" ", style, rtl_font, state),
        NodeValue::LineBreak => "<w:r><w:br/></w:r>".into(),
        NodeValue::Strong => {
            style.bold = true;
            drop(data);
            render_inline_children(node, style, rtl_font, state)
        }
        NodeValue::Emph => {
            style.italic = true;
            drop(data);
            render_inline_children(node, style, rtl_font, state)
        }
        NodeValue::Strikethrough => {
            style.strike = true;
            drop(data);
            render_inline_children(node, style, rtl_font, state)
        }
        NodeValue::Underline | NodeValue::Insert => {
            style.underline = true;
            drop(data);
            render_inline_children(node, style, rtl_font, state)
        }
        NodeValue::Superscript => {
            style.superscript = true;
            drop(data);
            render_inline_children(node, style, rtl_font, state)
        }
        NodeValue::Subscript => {
            style.subscript = true;
            drop(data);
            render_inline_children(node, style, rtl_font, state)
        }
        NodeValue::Highlight => {
            style.highlight = true;
            drop(data);
            render_inline_children(node, style, rtl_font, state)
        }
        NodeValue::SpoileredText => {
            style.highlight = true;
            drop(data);
            render_inline_children(node, style, rtl_font, state)
        }
        NodeValue::Link(link) => {
            let url = link.url.clone();
            drop(data);
            let label = render_inline_children(
                node,
                InlineStyle {
                    underline: true,
                    ..style
                },
                rtl_font,
                state,
            );
            format!(
                "{label}{}",
                text_runs_with_state(&format!(" ({url})"), style, rtl_font, state)
            )
        }
        NodeValue::Image(link) => {
            let url = link.url.clone();
            drop(data);
            let alt = collect_text(node);
            text_runs_with_state(
                &format!("[Image: {alt}] ({url})"),
                InlineStyle {
                    italic: true,
                    ..style
                },
                rtl_font,
                state,
            )
        }
        NodeValue::Math(math) => {
            state.last_strong = Some(false);
            math_xml(&math.literal, math.display_math)
        }
        NodeValue::TaskItem(item) => text_runs_with_state(
            if item.symbol.is_some() {
                "☑ "
            } else {
                "☐ "
            },
            style,
            rtl_font,
            state,
        ),
        NodeValue::FootnoteReference(reference) => text_runs_with_state(
            &format!("[{}]", reference.name),
            InlineStyle {
                superscript: true,
                ..style
            },
            rtl_font,
            state,
        ),
        NodeValue::HtmlInline(value) => {
            state.last_strong = Some(false);
            word_run(
                value,
                InlineStyle {
                    mono: true,
                    ..style
                },
                rtl_font,
                false,
            )
        }
        NodeValue::Raw(value) => text_runs_with_state(value, style, rtl_font, state),
        NodeValue::EscapedTag(value) => text_runs_with_state(value, style, rtl_font, state),
        NodeValue::WikiLink(link) => {
            let url = link.url.clone();
            drop(data);
            let label = render_inline_children(
                node,
                InlineStyle {
                    underline: true,
                    ..style
                },
                rtl_font,
                state,
            );
            format!(
                "{label}{}",
                text_runs_with_state(&format!(" ({url})"), style, rtl_font, state)
            )
        }
        _ => {
            drop(data);
            render_inline_children(node, style, rtl_font, state)
        }
    }
}

fn text_runs(text: &str, style: InlineStyle, rtl_font: &str) -> String {
    let mut state = InlineDirectionState::new(dominant_rtl(text));
    text_runs_with_state(text, style, rtl_font, &mut state)
}

fn text_runs_with_state(
    text: &str,
    style: InlineStyle,
    rtl_font: &str,
    state: &mut InlineDirectionState,
) -> String {
    let neutral_fallback_rtl = state.last_strong.unwrap_or(state.base_rtl);
    let segments = split_directional(text, state.base_rtl, neutral_fallback_rtl);
    let mut output = String::new();
    for (value, rtl) in segments {
        if rtl {
            output.push_str(&rtl_word_runs(&value, style, rtl_font));
        } else if state.base_rtl {
            output.push_str(&rtl_paragraph_ltr_runs(&value, style, rtl_font));
        } else {
            output.push_str(&word_run(&value, style, rtl_font, false));
        }
    }
    if let Some(direction) = text.chars().rev().find_map(strong_character_direction) {
        state.last_strong = Some(direction);
    }
    output
}

fn word_run(text: &str, style: InlineStyle, rtl_font: &str, rtl: bool) -> String {
    let isolated = if rtl {
        text.to_string()
    } else {
        format!("\u{2066}{text}\u{2069}")
    };
    unwrapped_word_run(&isolated, style, rtl_font, rtl)
}

fn unwrapped_word_run(text: &str, style: InlineStyle, rtl_font: &str, rtl: bool) -> String {
    let mut props = style_properties(style);
    if rtl {
        props.push_str(&format!(
            "<w:rFonts w:cs=\"{}\"/><w:rtl/><w:lang w:bidi=\"he-IL\"/>",
            xml(rtl_font)
        ));
    } else {
        props.push_str("<w:rtl w:val=\"0\"/><w:lang w:val=\"en-US\"/>");
    }
    run_xml(text, &props)
}

fn ltr_syntax_run(text: &str, style: InlineStyle, rtl_font: &str) -> String {
    let mut output = String::from("<w:bdo w:val=\"ltr\">");
    for character in text.chars() {
        output.push_str(&unwrapped_word_run(
            &character.to_string(),
            style,
            rtl_font,
            false,
        ));
    }
    output.push_str("</w:bdo>");
    output
}

fn rtl_word_runs(text: &str, style: InlineStyle, rtl_font: &str) -> String {
    word_run(text, style, rtl_font, true)
}

fn rtl_paragraph_ltr_runs(text: &str, style: InlineStyle, rtl_font: &str) -> String {
    let punctuation_start = text
        .char_indices()
        .rev()
        .take_while(|(_, character)| matches!(character, '.' | ',' | ';' | ':' | '!' | '?'))
        .last()
        .map(|(index, _)| index)
        .unwrap_or(text.len());
    if punctuation_start == text.len() {
        return if is_balanced_ascii_syntax_atom(text) {
            ltr_syntax_run(text, style, rtl_font)
        } else {
            word_run(text, style, rtl_font, false)
        };
    }
    let mut output = String::new();
    if punctuation_start > 0 {
        let atom = &text[..punctuation_start];
        if is_balanced_ascii_syntax_atom(atom) {
            output.push_str(&ltr_syntax_run(atom, style, rtl_font));
        } else {
            output.push_str(&word_run(atom, style, rtl_font, false));
        }
    }
    output.push_str(&word_run(&text[punctuation_start..], style, rtl_font, true));
    output
}

fn is_balanced_ascii_syntax_atom(text: &str) -> bool {
    if !text.is_ascii()
        || text.chars().any(char::is_whitespace)
        || !text.chars().any(|character| character.is_ascii_alphanumeric())
        || !text.contains('[')
    {
        return false;
    }

    let mut stack = Vec::new();
    let mut nested = false;
    for character in text.chars() {
        match character {
            '(' | '[' | '{' => {
                stack.push(character);
                nested |= stack.len() > 1;
            }
            ')' | ']' | '}' => {
                let expected = match character {
                    ')' => '(',
                    ']' => '[',
                    '}' => '{',
                    _ => unreachable!(),
                };
                if stack.pop() != Some(expected) {
                    return false;
                }
            }
            _ => {}
        }
    }
    nested && stack.is_empty()
}

fn style_properties(style: InlineStyle) -> String {
    let mut props = String::new();
    if style.bold {
        props.push_str("<w:b/>");
    }
    if style.italic {
        props.push_str("<w:i/>");
    }
    if style.strike {
        props.push_str("<w:strike/>");
    }
    if style.underline {
        props.push_str("<w:u w:val=\"single\"/>");
    }
    if style.superscript {
        props.push_str("<w:vertAlign w:val=\"superscript\"/>");
    }
    if style.subscript {
        props.push_str("<w:vertAlign w:val=\"subscript\"/>");
    }
    if style.highlight {
        props.push_str("<w:highlight w:val=\"yellow\"/>");
    }
    if style.mono {
        props.push_str(
            "<w:rFonts w:ascii=\"Courier New\" w:hAnsi=\"Courier New\"/><w:sz w:val=\"20\"/>",
        );
    }
    props
}

fn run_xml(text: &str, props: &str) -> String {
    format!(
        "<w:r>{}<w:t xml:space=\"preserve\">{}</w:t></w:r>",
        if props.is_empty() {
            String::new()
        } else {
            format!("<w:rPr>{props}</w:rPr>")
        },
        xml(text)
    )
}

fn strong_character_direction(character: char) -> Option<bool> {
    if matches!(character as u32, 0x0590..=0x08ff) {
        Some(true)
    } else if character.is_alphabetic() {
        Some(false)
    } else {
        None
    }
}

fn math_xml(latex: &str, display: bool) -> String {
    crate::math::to_omml(latex, display)
}

fn is_display_math_paragraph<'a>(node: &'a AstNode<'a>) -> bool {
    let mut children = node.children();
    let Some(child) = children.next() else {
        return false;
    };
    if children.next().is_some() {
        return false;
    }
    matches!(&child.data.borrow().value, NodeValue::Math(math) if math.display_math)
}

fn collect_text<'a>(node: &'a AstNode<'a>) -> String {
    let data = node.data.borrow();
    let own = match &data.value {
        NodeValue::Text(value) => value.to_string(),
        NodeValue::Code(code) => code.literal.clone(),
        NodeValue::CodeBlock(code) => code.literal.clone(),
        NodeValue::Math(math) => math.literal.clone(),
        NodeValue::SoftBreak | NodeValue::LineBreak => "\n".into(),
        _ => String::new(),
    };
    drop(data);
    own + &node.children().map(collect_text).collect::<String>()
}

fn contains_rtl(text: &str) -> bool {
    text.chars().any(|c| matches!(c as u32, 0x0590..=0x08ff))
}

fn dominant_rtl(text: &str) -> bool {
    let rtl = text
        .chars()
        .filter(|character| matches!(*character as u32, 0x0590..=0x08ff))
        .count();
    let ltr = text
        .chars()
        .filter(|character| {
            character.is_alphabetic() && !matches!(*character as u32, 0x0590..=0x08ff)
        })
        .count();
    rtl > ltr
}

fn split_directional(
    text: &str,
    base_rtl: bool,
    neutral_fallback_rtl: bool,
) -> Vec<(String, bool)> {
    let mut result = Vec::new();
    let mut buffer = String::new();
    let mut neutrals = String::new();
    let mut direction: Option<bool> = None;
    for ch in text.chars() {
        let char_direction = strong_character_direction(ch);
        let Some(next) = char_direction else {
            neutrals.push(ch);
            continue;
        };
        match direction {
            None => {
                buffer.push_str(&neutrals);
                neutrals.clear();
                direction = Some(next);
            }
            Some(current) if current == next => {
                buffer.push_str(&neutrals);
                neutrals.clear();
            }
            Some(current) => {
                let pivot = boundary_pivot(&neutrals, current, next, base_rtl);
                buffer.push_str(&neutrals[..pivot]);
                if !buffer.is_empty() {
                    result.push((std::mem::take(&mut buffer), current));
                }
                buffer.push_str(&neutrals[pivot..]);
                neutrals.clear();
                direction = Some(next);
            }
        }
        buffer.push(ch);
    }
    let final_direction = direction.unwrap_or(neutral_fallback_rtl);
    buffer.push_str(&neutrals);
    if !buffer.is_empty() {
        result.push((buffer, final_direction));
    }
    result
}

fn boundary_pivot(neutrals: &str, current: bool, next: bool, base_rtl: bool) -> usize {
    // Boundary whitespace belongs to the paragraph's base-direction side.
    // Closing punctuation stays with the preceding run; unmatched opening
    // punctuation belongs with the following strong text.
    if current != base_rtl && next == base_rtl {
        if let Some((opening_index, _)) = neutrals.char_indices().find(|(index, value)| {
            is_opening_punctuation(*value)
                && matching_closer(*value)
                    .is_none_or(|closer| !neutrals[index + value.len_utf8()..].contains(closer))
        }) {
            return trailing_whitespace_start(&neutrals[..opening_index]).unwrap_or(opening_index);
        }
        return trailing_whitespace_start(neutrals).unwrap_or(neutrals.len());
    }
    neutrals
        .char_indices()
        .find(|(index, value)| {
            is_opening_punctuation(*value)
                && matching_closer(*value)
                    .is_none_or(|closer| !neutrals[index + value.len_utf8()..].contains(closer))
        })
        .map(|(index, _)| index)
        .unwrap_or(neutrals.len())
}

fn trailing_whitespace_start(value: &str) -> Option<usize> {
    value
        .char_indices()
        .rev()
        .take_while(|(_, character)| character.is_whitespace())
        .last()
        .map(|(index, _)| index)
}

fn matching_closer(character: char) -> Option<char> {
    match character {
        '(' => Some(')'),
        '[' => Some(']'),
        '{' => Some('}'),
        '<' => Some('>'),
        '（' => Some('）'),
        '［' => Some('］'),
        '｛' => Some('｝'),
        '【' => Some('】'),
        '「' => Some('」'),
        '『' => Some('』'),
        '〈' => Some('〉'),
        '《' => Some('》'),
        _ => None,
    }
}

fn is_opening_punctuation(character: char) -> bool {
    matches!(
        character,
        '(' | '['
            | '{'
            | '<'
            | '"'
            | '\''
            | '“'
            | '‘'
            | '«'
            | '‹'
            | '（'
            | '［'
            | '｛'
            | '【'
            | '「'
            | '『'
            | '〈'
            | '《'
            | '$'
            | '€'
            | '£'
            | '¥'
            | '₪'
            | '₹'
            | '₩'
    )
}

fn package(document: String, styles: String, numbering: String) -> Result<Vec<u8>, String> {
    let cursor = Cursor::new(Vec::new());
    let mut zip = ZipWriter::new(cursor);
    let timestamp = DateTime::from_date_and_time(2000, 1, 1, 0, 0, 0).map_err(|e| e.to_string())?;
    let options = SimpleFileOptions::default()
        .compression_method(zip::CompressionMethod::Stored)
        .last_modified_time(timestamp)
        .system(System::Dos);
    let files = [
        ("[Content_Types].xml", content_types()),
        ("_rels/.rels", root_relationships()),
        ("word/document.xml", document),
        ("word/styles.xml", styles),
        ("word/numbering.xml", numbering),
        ("word/_rels/document.xml.rels", document_relationships()),
        ("docProps/core.xml", core_properties()),
        ("docProps/app.xml", app_properties()),
    ];
    for (name, content) in files {
        zip.start_file(name, options).map_err(|e| e.to_string())?;
        zip.write_all(content.as_bytes())
            .map_err(|e| e.to_string())?;
    }
    zip.finish()
        .map(|cursor| cursor.into_inner())
        .map_err(|e| e.to_string())
}

fn content_types() -> String {
    "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"><Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/><Default Extension=\"xml\" ContentType=\"application/xml\"/><Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/><Override PartName=\"/word/styles.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml\"/><Override PartName=\"/word/numbering.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml\"/><Override PartName=\"/docProps/core.xml\" ContentType=\"application/vnd.openxmlformats-package.core-properties+xml\"/><Override PartName=\"/docProps/app.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.extended-properties+xml\"/></Types>".into()
}
fn root_relationships() -> String {
    "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/><Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties\" Target=\"docProps/core.xml\"/><Relationship Id=\"rId3\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties\" Target=\"docProps/app.xml\"/></Relationships>".into()
}
fn document_relationships() -> String {
    "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles\" Target=\"styles.xml\"/><Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering\" Target=\"numbering.xml\"/></Relationships>".into()
}
fn core_properties() -> String {
    "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><cp:coreProperties xmlns:cp=\"http://schemas.openxmlformats.org/package/2006/metadata/core-properties\" xmlns:dc=\"http://purl.org/dc/elements/1.1/\"><dc:title>md2docx document</dc:title><dc:creator>md2docx canonical compiler</dc:creator></cp:coreProperties>".into()
}
fn app_properties() -> String {
    "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Properties xmlns=\"http://schemas.openxmlformats.org/officeDocument/2006/extended-properties\"><Application>md2docx</Application></Properties>".into()
}

fn numbering_xml(rtl: bool) -> String {
    let indent_side = if rtl { "right" } else { "left" };
    let level_alignment = if rtl { "right" } else { "left" };
    let run_properties = if rtl {
        "<w:rPr><w:rtl/><w:lang w:bidi=\"he-IL\"/></w:rPr>"
    } else {
        ""
    };
    let levels = (0..9).map(|level| format!("<w:lvl w:ilvl=\"{level}\"><w:start w:val=\"1\"/><w:numFmt w:val=\"bullet\"/><w:lvlText w:val=\"{}\"/><w:lvlJc w:val=\"{level_alignment}\"/><w:pPr><w:ind w:{indent_side}=\"{}\" w:hanging=\"360\"/></w:pPr>{run_properties}</w:lvl>", if level % 3 == 0 { "•" } else if level % 3 == 1 { "◦" } else { "▪" }, 720 * (level + 1))).collect::<String>();
    let ordered = (0..9).map(|level| format!("<w:lvl w:ilvl=\"{level}\"><w:start w:val=\"1\"/><w:numFmt w:val=\"decimal\"/><w:lvlText w:val=\"%{}.\"/><w:lvlJc w:val=\"{level_alignment}\"/><w:pPr><w:ind w:{indent_side}=\"{}\" w:hanging=\"360\"/></w:pPr>{run_properties}</w:lvl>", level + 1, 720 * (level + 1))).collect::<String>();
    format!(
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><w:numbering xmlns:w=\"{W}\"><w:abstractNum w:abstractNumId=\"0\"><w:multiLevelType w:val=\"multilevel\"/>{levels}</w:abstractNum><w:abstractNum w:abstractNumId=\"1\"><w:multiLevelType w:val=\"multilevel\"/>{ordered}</w:abstractNum><w:num w:numId=\"1\"><w:abstractNumId w:val=\"0\"/></w:num><w:num w:numId=\"2\"><w:abstractNumId w:val=\"1\"/></w:num></w:numbering>"
    )
}

fn xml(value: &str) -> String {
    let mut output = String::with_capacity(value.len());
    for character in value
        .chars()
        .filter(|character| valid_xml_character(*character))
    {
        match character {
            '&' => output.push_str("&amp;"),
            '<' => output.push_str("&lt;"),
            '>' => output.push_str("&gt;"),
            '"' => output.push_str("&quot;"),
            '\'' => output.push_str("&apos;"),
            _ => output.push(character),
        }
    }
    output
}

fn valid_xml_character(character: char) -> bool {
    matches!(character as u32, 0x9 | 0xa | 0xd | 0x20..=0xd7ff | 0xe000..=0xfffd | 0x10000..=0x10ffff)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Read;
    use zip::ZipArchive;

    fn document_xml(markdown: &str) -> String {
        let bytes = compile(markdown, &CompileOptions::default()).unwrap();
        let mut archive = ZipArchive::new(Cursor::new(bytes)).unwrap();
        let mut value = String::new();
        archive
            .by_name("word/document.xml")
            .unwrap()
            .read_to_string(&mut value)
            .unwrap();
        value
    }

    fn assert_only_balanced_compiler_bidi_controls(xml: &str) {
        let mut isolate_depth = 0usize;
        for character in xml.chars() {
            match character {
                '\u{2066}' => {
                    assert_eq!(isolate_depth, 0, "nested LRI in generated XML: {xml}");
                    isolate_depth += 1;
                }
                '\u{2069}' => {
                    assert_eq!(isolate_depth, 1, "unmatched PDI in generated XML: {xml}");
                    isolate_depth -= 1;
                }
                '\u{200e}'
                | '\u{200f}'
                | '\u{202a}'
                | '\u{202b}'
                | '\u{202c}'
                | '\u{202d}'
                | '\u{202e}'
                | '\u{2067}'
                | '\u{2068}' => {
                    panic!(
                        "unsafe BiDi control U+{:04X} in generated XML",
                        character as u32
                    );
                }
                _ => {}
            }
        }
        assert_eq!(isolate_depth, 0, "unclosed LRI in generated XML: {xml}");
    }

    #[test]
    fn hebrew_table_uses_word_visual_rtl_without_destroying_logical_order() {
        let xml = document_xml("| שם | ערך |\n|---|---|\n| אלף | 1 |");
        assert!(xml.contains("<w:bidiVisual/>"));
        assert!(xml.find("שם").unwrap() < xml.find("ערך").unwrap());
    }

    #[test]
    fn headings_nested_styles_and_any_fence_language_are_compiled() {
        let xml = document_xml("Title\n=====\n\n**bold and *nested***\n\n```bash\necho ok\n```");
        assert!(xml.contains("Heading1"));
        assert!(xml.contains("bash"));
        assert!(xml.contains("Courier New"));
        assert!(xml.contains("echo ok"));
    }

    #[test]
    fn canonical_fixture_keeps_extended_markdown_content() {
        let xml = document_xml(include_str!(
            "../../../../tests/fixtures/canonical_markdown.md"
        ));
        for expected in [
            "Primary heading",
            "Setext heading",
            "external link",
            "Completed task",
            "Note",
            "Footnote",
            "content",
        ] {
            assert!(xml.contains(expected), "missing {expected}");
        }
        assert!(xml.contains("<w:bidiVisual/>"));
    }

    #[test]
    fn hebrew_benchmark_has_native_math_and_centered_table_cells() {
        let xml = document_xml(include_str!(
            "../../../../tests/fixtures/hebrew_experiment_benchmark.md"
        ));
        assert!(!xml.contains(">$$</w:t>"));
        assert!(xml.contains("<m:sSub>"));
        assert!(xml.contains("θ"));
        assert!(xml.contains("α"));
        assert!(xml.contains("∇"));
        assert!(xml.contains("<w:bidiVisual/>"));
        for cell in xml.split("<w:tc>").skip(1) {
            let cell = cell.split("</w:tc>").next().unwrap();
            assert!(cell.contains("<w:jc w:val=\"center\"/>"));
            assert!(cell.contains("<w:vAlign w:val=\"center\"/>"));
        }
    }

    #[test]
    fn opening_brackets_follow_their_directional_text() {
        let segments = split_directional(
            "עברית [English] ואז العربية (ABC) וגם 【Latin】",
            true,
            true,
        );
        assert!(
            segments
                .iter()
                .any(|(value, rtl)| !rtl && value.contains("[English]")),
            "{segments:?}"
        );
        assert!(
            segments
                .iter()
                .any(|(value, rtl)| !rtl && value.contains("(ABC)")),
            "{segments:?}"
        );
        assert!(
            segments
                .iter()
                .any(|(value, rtl)| !rtl && value.contains("【Latin】")),
            "{segments:?}"
        );
        let arabic = split_directional("Arabic «نص» ، ؛ ؟.", false, false);
        assert!(
            arabic
                .iter()
                .any(|(value, rtl)| *rtl && value.starts_with('«')),
            "{arabic:?}"
        );
    }

    #[test]
    fn nested_ltr_brackets_use_a_native_ltr_override_in_rtl_paragraphs() {
        let source = "המסקנה: השילוב בין עברית, English, מספרים 12.5%, וסוגריים {A[0]} נשאר קריא.";
        let segments = split_directional(source, true, true);
        assert!(
            segments
                .iter()
                .any(|(value, rtl)| !rtl && value.contains("{A[0]}")),
            "{segments:?}"
        );
        let xml = text_runs(source, InlineStyle::default(), "Arial");
        assert!(!xml.contains("<w:dir"), "{xml}");
        assert!(xml.contains("<w:bdo w:val=\"ltr\">"), "{xml}");
        assert!(xml.contains(">{</w:t>"), "{xml}");
        assert!(xml.contains(">A</w:t>"), "{xml}");
        assert!(xml.contains(">[</w:t>"), "{xml}");
        assert!(xml.contains(">0</w:t>"), "{xml}");
        assert!(xml.contains(">]</w:t>"), "{xml}");
        assert!(xml.contains(">}</w:t>"), "{xml}");
        assert!(xml.contains("</w:bdo>"), "{xml}");
        assert!(!xml.contains(">\u{2066}{A[0]}\u{2069}</w:t>"), "{xml}");
        assert!(xml.contains("> נשאר קריא.</w:t>"), "{xml}");
        assert_only_balanced_compiler_bidi_controls(&xml);
        assert!(!xml.contains('\u{00a0}'), "{xml}");
    }

    #[test]
    fn rtl_brackets_remain_in_natural_logical_order() {
        let xml = text_runs("סטטוס: [פעיל] [מומלץ]", InlineStyle::default(), "Arial");
        assert!(xml.contains(">סטטוס: [פעיל] [מומלץ]</w:t>"), "{xml}");
        assert!(!xml.contains("]פעיל["), "{xml}");
    }

    #[test]
    fn only_balanced_ascii_nested_syntax_uses_the_literal_ltr_run() {
        assert!(is_balanced_ascii_syntax_atom("{A[0]}"));
        assert!(is_balanced_ascii_syntax_atom("array[index[0]]"));
        for value in [
            "[פעיל]",
            "{A[0]",
            "{A]0[}",
            "{A[0]} extra",
            "English",
            "[0]",
        ] {
            assert!(!is_balanced_ascii_syntax_atom(value), "{value}");
        }
    }

    #[test]
    fn spaces_at_mixed_bidi_boundaries_remain_breakable_and_lossless() {
        for source in [
            "היה Customer Acquisition Cost (CAC), שירד",
            "ב־API החדש (v2/users/create) כדי",
            "ב־18% לעומת Q4 2025",
        ] {
            let segments = split_directional(source, true, true);
            let reconstructed = segments
                .iter()
                .map(|(value, _)| value.as_str())
                .collect::<String>();
            assert_eq!(reconstructed, source);
            assert!(
                segments.windows(2).any(|boundary| {
                    boundary[0].0.ends_with(' ') || boundary[1].0.starts_with(' ')
                }),
                "no directional boundary space in {source:?}: {segments:?}"
            );
        }
        for source in ["של 2026 החברה", "מ־$42 ל־$31"] {
            let segments = split_directional(source, true, true);
            assert_eq!(segments, vec![(source.to_string(), true)], "{segments:?}");
        }
    }

    #[test]
    fn symbols_and_heading_punctuation_keep_visible_bidi_spacing() {
        for source in [
            "דוגמה 1 — עברית + English + 18%",
            "ניתוח אלגוריתם Gradient Descent",
            "טבלה מורכבת עם Markdown",
            "השוואת פתרונות AI",
            "Customer Acquisition Cost (CAC), שירד מ־$42 ל־$31.",
        ] {
            let segments = split_directional(source, true, true);
            let boundary_spaces = segments
                .windows(2)
                .filter(|boundary| {
                    boundary[0].0.ends_with(' ')
                        || boundary[1].0.starts_with(' ')
                        || [", ", "; ", ": ", ". ", "! ", "? "]
                            .iter()
                            .any(|prefix| boundary[1].0.starts_with(prefix))
                })
                .count();
            assert!(
                boundary_spaces > 0,
                "missing breakable symbol/language spacing for {source:?}: {segments:?}"
            );
            assert_eq!(
                segments
                    .iter()
                    .map(|(value, _)| value.as_str())
                    .collect::<String>(),
                source
            );
        }
        let currency = split_directional("מחיר מ־$42 ל־€31 וגם ₪100", true, true);
        for value in ["$42", "€31", "₪100"] {
            assert!(
                currency
                    .iter()
                    .any(|(part, rtl)| *rtl && part.contains(value)),
                "currency did not inherit the surrounding Hebrew run: {currency:?}"
            );
        }
    }

    #[test]
    fn mixed_text_uses_directional_runs_and_styled_boundaries_keep_spaces() {
        let xml = document_xml(
            "# 2. Phase 0 - תשתית ותכנון Validation\n\n**גרסה:** 1.0\n\n**מטרה:** יצירת בסיס",
        );
        for text in ["2. Phase 0", "תשתית ותכנון", "Validation"] {
            assert!(xml.contains(text), "missing {text}: {xml}");
        }
        assert!(xml.contains("0 -\u{2069}</w:t>"), "{xml}");
        assert!(xml.contains("> תשתית ותכנון </w:t>"), "{xml}");
        assert!(xml.contains("<w:rtl/>"));
        assert!(xml.contains("<w:rtl w:val=\"0\"/>"));
        assert!(!xml.contains('\u{00a0}'), "{xml}");
        assert!(xml.contains("> 1.0</w:t>"));
        assert!(xml.contains("> יצירת בסיס</w:t>"));
        assert_only_balanced_compiler_bidi_controls(&xml);
    }

    #[test]
    fn punctuation_only_nodes_are_neutral_and_structural_boundaries_are_embedded() {
        let mut mixed_state = InlineDirectionState::new(true);
        let mixed = text_runs_with_state(
            "המדד Customer Acquisition Cost (CAC) ירד.",
            InlineStyle::default(),
            "Arial",
            &mut mixed_state,
        );
        assert!(mixed.contains(">המדד </w:t>"), "{mixed}");
        assert!(mixed.contains("(CAC)\u{2069}</w:t>"), "{mixed}");
        assert!(mixed.contains("> ירד.</w:t>"), "{mixed}");
        assert!(!mixed.contains('\u{00a0}'), "{mixed}");
        assert!(mixed.contains("Customer Acquisition Cost (CAC)"), "{mixed}");

        let punctuation = text_runs(".", InlineStyle::default(), "Arial");
        assert!(
            punctuation.contains("<w:rtl w:val=\"0\"/>"),
            "{punctuation}"
        );
        assert!(
            punctuation.contains(">\u{2066}.\u{2069}</w:t>"),
            "{punctuation}"
        );

        let status = text_runs("סטטוס: [פעיל]", InlineStyle::default(), "Arial");
        assert!(!status.contains("<w:dir"), "{status}");
        assert!(status.contains("<w:rtl/>"), "{status}");
        assert!(!status.contains("<w:bdo"), "{status}");
        assert!(status.contains(">סטטוס: [פעיל]</w:t>"), "{status}");

        let mut state = InlineDirectionState::new(true);
        let heading = text_runs_with_state(
            "השוואת פתרונות AI",
            InlineStyle::default(),
            "Arial",
            &mut state,
        );
        assert!(!heading.contains("<w:dir"), "{heading}");
        assert!(heading.contains(">השוואת פתרונות </w:t>"), "{heading}");
        assert!(heading.contains(">\u{2066}AI\u{2069}</w:t>"), "{heading}");
    }

    #[test]
    fn numbers_weak_symbols_and_cross_node_punctuation_follow_word_bidi_runs() {
        let mixed = text_runs(
            "ברבעון הראשון של 2026 החברה הגדילה את ההכנסות ב-18% לעומת Q4 2025.",
            InlineStyle::default(),
            "Arial",
        );
        assert!(
            mixed.contains(">ברבעון הראשון של 2026 החברה הגדילה את ההכנסות ב-18% לעומת </w:t>"),
            "{mixed}"
        );
        assert!(mixed.contains(">\u{2066}Q4 2025\u{2069}</w:t>"), "{mixed}");
        assert!(mixed.contains(">.</w:t>"), "{mixed}");
        assert!(!mixed.contains('\u{00a0}'), "{mixed}");

        let xml = document_xml("אחריות: צוות Platform מטפל ב-`release_check()`.");
        assert!(
            xml.contains(">\u{2066}release_check()\u{2069}</w:t>"),
            "{xml}"
        );
        assert!(xml.contains(">.</w:t>"), "{xml}");
        assert!(!xml.contains(">\u{2066}release_check().\u{2069}</w:t>"), "{xml}");
    }

    #[test]
    fn rtl_sentence_punctuation_stays_with_its_logical_text() {
        let mut state = InlineDirectionState::new(true);
        let workflow = text_runs_with_state(
            "המעבר המרכזי: הרשמה ← אימות ← Dashboard; סטטוס: [פעיל] (Beta).",
            InlineStyle::default(),
            "Arial",
            &mut state,
        );
        assert!(
            workflow.contains(">\u{2066}Dashboard\u{2069}</w:t>"),
            "{workflow}"
        );
        assert!(workflow.contains(">;</w:t>"), "{workflow}");
        assert!(
            workflow.contains(">\u{2066}(Beta)\u{2069}</w:t>"),
            "{workflow}"
        );
        assert!(workflow.contains(">.</w:t>"), "{workflow}");
        assert!(!workflow.contains("<w:dir"), "{workflow}");
        assert!(!workflow.contains("<w:bdo"), "{workflow}");
        assert!(workflow.contains("> סטטוס: [פעיל] </w:t>"), "{workflow}");
        let beta = workflow.find("(Beta)").unwrap();
        let bracket_token = workflow.find("[פעיל]").unwrap();
        assert!(bracket_token < beta, "{workflow}");
        assert_only_balanced_compiler_bidi_controls(&workflow);

        let mut state = InlineDirectionState::new(true);
        let mixed = text_runs_with_state(
            "המסקנה: השילוב בין עברית, English, מספרים 12.5%, וסוגריים {A[0]} נשאר קריא.",
            InlineStyle::default(),
            "Arial",
            &mut state,
        );
        assert!(mixed.contains(">\u{2066}English\u{2069}</w:t>"), "{mixed}");
        assert!(mixed.contains(">,</w:t>"), "{mixed}");
        assert!(mixed.contains("> מספרים 12.5%, וסוגריים </w:t>"), "{mixed}");
        assert!(
            mixed.contains("<w:bdo w:val=\"ltr\">"),
            "{mixed}"
        );
        assert!(!mixed.contains(">\u{2066}{A[0]}\u{2069}</w:t>"), "{mixed}");
        assert!(!mixed.contains("English,,"), "{mixed}");
        assert!(mixed.ends_with("נשאר קריא.</w:t></w:r>"), "{mixed}");
        assert_only_balanced_compiler_bidi_controls(&mixed);
    }

    #[test]
    fn paragraph_after_rtl_table_has_compiler_owned_spacing() {
        let xml = document_xml(
            "| פתרון | Accuracy |\n|---|---:|\n| Baseline | 88.2% |\n\nכל התאים מיושרים למרכז.",
        );
        let after_table = xml.split("</w:tbl>").nth(1).unwrap();
        assert!(
            after_table.contains("<w:spacing w:before=\"160\"/>"),
            "{after_table}"
        );
    }

    #[test]
    fn hebrew_dominant_document_keeps_english_list_items_rtl() {
        let xml = document_xml(
            "# כותרת עברית ארוכה\n\nפסקה עברית שמבהירה כי המסמך כולו כתוב בעיקר בעברית.\n\n- English only\n- פריט בעברית\n- Another English item",
        );
        assert!(xml.contains("<w:sectPr><w:bidi/>"));
        for item in ["English only", "Another English item"] {
            let before = xml.split(&format!(">{item}</w:t>")).next().unwrap();
            let paragraph = before.rsplit("<w:p>").next().unwrap();
            assert!(
                paragraph.contains("<w:bidi/>"),
                "missing RTL paragraph for {item}"
            );
        }
    }

    #[test]
    fn rtl_numbering_places_markers_on_the_right() {
        let rtl = numbering_xml(true);
        assert!(rtl.contains("<w:lvlJc w:val=\"right\"/>"), "{rtl}");
        assert!(rtl.contains("<w:ind w:right=\"720\""), "{rtl}");
        assert!(!rtl.contains("<w:lvlJc w:val=\"start\"/>"), "{rtl}");

        let ltr = numbering_xml(false);
        assert!(ltr.contains("<w:lvlJc w:val=\"left\"/>"), "{ltr}");
        assert!(ltr.contains("<w:ind w:left=\"720\""), "{ltr}");
    }
}
