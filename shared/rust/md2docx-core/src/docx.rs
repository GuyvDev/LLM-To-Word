use std::io::{Cursor, Write};

use comrak::nodes::{AstNode, ListType, NodeValue};
use comrak::{Arena, parse_document};
use zip::{ZipWriter, write::SimpleFileOptions};

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

struct Renderer<'a> {
    options: &'a CompileOptions,
    body: String,
}

pub fn compile(markdown: &str, options: &CompileOptions) -> Result<Vec<u8>, String> {
    let arena = Arena::new();
    let root = parse_document(
        &arena,
        markdown,
        &parser_options(options.effective_profile()),
    );
    let mut renderer = Renderer {
        options,
        body: String::new(),
    };
    renderer.render_blocks(root, BlockContext::default());
    package(
        renderer.document_xml(),
        renderer.styles_xml(),
        numbering_xml(),
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
                let plain = collect_text(node);
                let mut content = render_inline_children(node, InlineStyle::default(), &self.options.rtl_font);
                if let Some(checked) = context.task {
                    content = format!("{}{content}", text_runs(if checked { "☑ " } else { "☐ " }, InlineStyle::default(), &self.options.rtl_font));
                }
                let context = if is_display_math_paragraph(node) { BlockContext { center: true, ..context } } else { context };
                self.body.push_str(&paragraph(&content, &plain, None, context));
            }
            NodeValue::Heading(heading) => {
                let level = heading.level;
                drop(data);
                let plain = collect_text(node);
                let content = render_inline_children(node, InlineStyle::default(), &self.options.rtl_font);
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
                let content = render_inline_children(node, InlineStyle { italic: true, ..Default::default() }, &self.options.rtl_font);
                self.body.push_str(&paragraph(&content, &plain, None, context));
            }
            NodeValue::ThematicBreak => self.body.push_str("<w:p><w:pPr><w:pBdr><w:bottom w:val=\"single\" w:sz=\"6\" w:space=\"1\" w:color=\"auto\"/></w:pBdr></w:pPr></w:p>"),
            NodeValue::Table(_) => { drop(data); self.body.push_str(&render_table(node, &self.options.rtl_font)); }
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
        format!(
            "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><w:document xmlns:w=\"{W}\" xmlns:m=\"{M}\"><w:body>{}<w:sectPr><w:pgSz w:w=\"11906\" w:h=\"16838\"/><w:pgMar w:top=\"1134\" w:right=\"1134\" w:bottom=\"1134\" w:left=\"1134\"/></w:sectPr></w:body></w:document>",
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
    let rtl = contains_rtl(plain);
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

fn render_table<'a>(node: &'a AstNode<'a>, rtl_font: &str) -> String {
    let rtl = contains_rtl(&collect_text(node));
    let mut rows_xml = String::new();
    let mut columns = 0usize;
    for (row_index, row) in node.children().enumerate() {
        let is_header = matches!(row.data.borrow().value, NodeValue::TableRow(true));
        let cells = row.children().collect::<Vec<_>>();
        columns = columns.max(cells.len());
        let mut cells_xml = String::new();
        for cell in cells {
            let plain = collect_text(cell);
            let content = render_inline_children(
                cell,
                InlineStyle {
                    bold: is_header,
                    ..Default::default()
                },
                rtl_font,
            );
            let para = paragraph(
                &content,
                &plain,
                None,
                BlockContext {
                    center: true,
                    compact: true,
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
            cells_xml.push_str(&format!("<w:tc><w:tcPr><w:tcW w:w=\"2400\" w:type=\"dxa\"/><w:vAlign w:val=\"center\"/>{shade}</w:tcPr>{para}</w:tc>"));
        }
        rows_xml.push_str(&format!("<w:tr>{cells_xml}</w:tr>"));
    }
    let grid = (0..columns)
        .map(|_| "<w:gridCol w:w=\"2400\"/>".to_string())
        .collect::<String>();
    let bidi = if rtl { "<w:bidiVisual/>" } else { "" };
    format!(
        "<w:tbl><w:tblPr><w:tblStyle w:val=\"TableGrid\"/><w:tblW w:w=\"0\" w:type=\"auto\"/><w:jc w:val=\"center\"/>{bidi}<w:tblCellMar><w:top w:w=\"80\" w:type=\"dxa\"/><w:left w:w=\"100\" w:type=\"dxa\"/><w:bottom w:w=\"80\" w:type=\"dxa\"/><w:right w:w=\"100\" w:type=\"dxa\"/></w:tblCellMar><w:tblBorders><w:top w:val=\"single\" w:sz=\"6\" w:color=\"{border}\"/><w:left w:val=\"single\" w:sz=\"6\" w:color=\"{border}\"/><w:bottom w:val=\"single\" w:sz=\"6\" w:color=\"{border}\"/><w:right w:val=\"single\" w:sz=\"6\" w:color=\"{border}\"/><w:insideH w:val=\"single\" w:sz=\"4\" w:color=\"{inner}\"/><w:insideV w:val=\"single\" w:sz=\"4\" w:color=\"{inner}\"/></w:tblBorders></w:tblPr><w:tblGrid>{grid}</w:tblGrid>{rows_xml}</w:tbl>",
        border = theme::TABLE_BORDER,
        inner = theme::TABLE_INNER_BORDER
    )
}

fn render_inline_children<'a>(node: &'a AstNode<'a>, style: InlineStyle, rtl_font: &str) -> String {
    node.children()
        .map(|child| render_inline(child, style, rtl_font))
        .collect()
}

fn render_inline<'a>(node: &'a AstNode<'a>, mut style: InlineStyle, rtl_font: &str) -> String {
    let data = node.data.borrow();
    match &data.value {
        NodeValue::Text(value) => text_runs(value, style, rtl_font),
        NodeValue::Code(code) => text_runs(
            &code.literal,
            InlineStyle {
                mono: true,
                ..style
            },
            rtl_font,
        ),
        NodeValue::SoftBreak => text_runs(" ", style, rtl_font),
        NodeValue::LineBreak => "<w:r><w:br/></w:r>".into(),
        NodeValue::Strong => {
            style.bold = true;
            drop(data);
            render_inline_children(node, style, rtl_font)
        }
        NodeValue::Emph => {
            style.italic = true;
            drop(data);
            render_inline_children(node, style, rtl_font)
        }
        NodeValue::Strikethrough => {
            style.strike = true;
            drop(data);
            render_inline_children(node, style, rtl_font)
        }
        NodeValue::Underline | NodeValue::Insert => {
            style.underline = true;
            drop(data);
            render_inline_children(node, style, rtl_font)
        }
        NodeValue::Superscript => {
            style.superscript = true;
            drop(data);
            render_inline_children(node, style, rtl_font)
        }
        NodeValue::Subscript => {
            style.subscript = true;
            drop(data);
            render_inline_children(node, style, rtl_font)
        }
        NodeValue::Highlight => {
            style.highlight = true;
            drop(data);
            render_inline_children(node, style, rtl_font)
        }
        NodeValue::SpoileredText => {
            style.highlight = true;
            drop(data);
            render_inline_children(node, style, rtl_font)
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
            );
            format!(
                "{label}{}",
                text_runs(&format!(" ({url})"), style, rtl_font)
            )
        }
        NodeValue::Image(link) => {
            let url = link.url.clone();
            drop(data);
            let alt = collect_text(node);
            text_runs(
                &format!("[Image: {alt}] ({url})"),
                InlineStyle {
                    italic: true,
                    ..style
                },
                rtl_font,
            )
        }
        NodeValue::Math(math) => math_xml(&math.literal, math.display_math),
        NodeValue::TaskItem(item) => text_runs(
            if item.symbol.is_some() {
                "☑ "
            } else {
                "☐ "
            },
            style,
            rtl_font,
        ),
        NodeValue::FootnoteReference(reference) => text_runs(
            &format!("[{}]", reference.name),
            InlineStyle {
                superscript: true,
                ..style
            },
            rtl_font,
        ),
        NodeValue::HtmlInline(value) => text_runs(
            value,
            InlineStyle {
                mono: true,
                ..style
            },
            rtl_font,
        ),
        NodeValue::Raw(value) => text_runs(value, style, rtl_font),
        NodeValue::EscapedTag(value) => text_runs(value, style, rtl_font),
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
            );
            format!(
                "{label}{}",
                text_runs(&format!(" ({url})"), style, rtl_font)
            )
        }
        _ => {
            drop(data);
            render_inline_children(node, style, rtl_font)
        }
    }
}

fn text_runs(text: &str, style: InlineStyle, rtl_font: &str) -> String {
    split_directional(text).into_iter().map(|(part, rtl)| {
        let mut props = String::new();
        if style.bold { props.push_str("<w:b/>"); }
        if style.italic { props.push_str("<w:i/>"); }
        if style.strike { props.push_str("<w:strike/>"); }
        if style.underline { props.push_str("<w:u w:val=\"single\"/>"); }
        if style.superscript { props.push_str("<w:vertAlign w:val=\"superscript\"/>"); }
        if style.subscript { props.push_str("<w:vertAlign w:val=\"subscript\"/>"); }
        if style.highlight { props.push_str("<w:highlight w:val=\"yellow\"/>"); }
        if style.mono { props.push_str("<w:rFonts w:ascii=\"Courier New\" w:hAnsi=\"Courier New\"/><w:sz w:val=\"20\"/>"); }
        if rtl { props.push_str(&format!("<w:rFonts w:cs=\"{}\"/><w:rtl/><w:lang w:bidi=\"he-IL\"/>", xml(rtl_font))); }
        format!("<w:r>{}<w:t xml:space=\"preserve\">{}</w:t></w:r>", if props.is_empty() { String::new() } else { format!("<w:rPr>{props}</w:rPr>") }, xml(&part))
    }).collect()
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

fn split_directional(text: &str) -> Vec<(String, bool)> {
    let mut result = Vec::new();
    let mut buffer = String::new();
    let mut neutrals = String::new();
    let mut direction: Option<bool> = None;
    for ch in text.chars() {
        let char_direction = if matches!(ch as u32, 0x0590..=0x08ff) {
            Some(true)
        } else if ch.is_alphanumeric() {
            Some(false)
        } else {
            None
        };
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
                let pivot = boundary_pivot(&neutrals);
                buffer.push_str(&word_stable_boundary(&neutrals[..pivot]));
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
    buffer.push_str(&neutrals);
    if !buffer.is_empty() {
        result.push((buffer, direction.unwrap_or(false)));
    }
    result
}

fn boundary_pivot(neutrals: &str) -> usize {
    // Opening punctuation belongs with the following directional run. Other
    // neutral characters, including closing punctuation, stay with the prior.
    neutrals
        .char_indices()
        .find(|(_, value)| is_opening_punctuation(*value))
        .map(|(index, _)| index)
        .unwrap_or(neutrals.len())
}

fn word_stable_boundary(value: &str) -> String {
    // Word may suppress or visually move an ordinary trailing space when the
    // next run changes direction. NBSP remains a visible-width separator and
    // stays attached to the preceding run during Word's BiDi reordering.
    value.replace(' ', "\u{00a0}")
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
    let options = SimpleFileOptions::default().compression_method(zip::CompressionMethod::Stored);
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

fn numbering_xml() -> String {
    let levels = (0..9).map(|level| format!("<w:lvl w:ilvl=\"{level}\"><w:start w:val=\"1\"/><w:numFmt w:val=\"bullet\"/><w:lvlText w:val=\"{}\"/><w:pPr><w:ind w:left=\"{}\" w:hanging=\"360\"/></w:pPr></w:lvl>", if level % 3 == 0 { "•" } else if level % 3 == 1 { "◦" } else { "▪" }, 720 * (level + 1))).collect::<String>();
    let ordered = (0..9).map(|level| format!("<w:lvl w:ilvl=\"{level}\"><w:start w:val=\"1\"/><w:numFmt w:val=\"decimal\"/><w:lvlText w:val=\"%{}.\"/><w:pPr><w:ind w:left=\"{}\" w:hanging=\"360\"/></w:pPr></w:lvl>", level + 1, 720 * (level + 1))).collect::<String>();
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
        let segments = split_directional("עברית [English] ואז العربية (ABC) וגם 【Latin】");
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
    }

    #[test]
    fn spaces_at_mixed_bidi_boundaries_are_word_stable() {
        for source in [
            "של 2026 החברה",
            "היה Customer Acquisition Cost (CAC), שירד",
            "ב־API החדש (v2/users/create) כדי",
            "ב־18% לעומת Q4 2025",
            "מ־$42 ל־$31",
        ] {
            let segments = split_directional(source);
            let reconstructed = segments
                .iter()
                .map(|(value, _)| value.replace('\u{00a0}', " "))
                .collect::<String>();
            assert_eq!(reconstructed, source);
            assert!(
                segments
                    .iter()
                    .any(|(value, _)| value.ends_with('\u{00a0}')),
                "no Word-stable boundary in {source:?}: {segments:?}"
            );
            assert!(
                !segments
                    .iter()
                    .skip(1)
                    .any(|(value, _)| value.starts_with(' ')),
                "ordinary space starts a directional run in {source:?}: {segments:?}"
            );
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
            let segments = split_directional(source);
            let stable_spaces = segments
                .iter()
                .map(|(value, _)| value.matches('\u{00a0}').count())
                .sum::<usize>();
            assert!(
                stable_spaces > 0,
                "missing stable symbol/language spacing for {source:?}: {segments:?}"
            );
            assert_eq!(
                segments
                    .iter()
                    .map(|(value, _)| value.replace('\u{00a0}', " "))
                    .collect::<String>(),
                source
            );
        }
        let currency = split_directional("מחיר מ־$42 ל־€31 וגם ₪100");
        for value in ["$42", "€31", "₪100"] {
            assert!(
                currency
                    .iter()
                    .any(|(part, rtl)| !rtl && part.contains(value)),
                "currency prefix did not stay with its LTR number: {currency:?}"
            );
        }
    }
}
