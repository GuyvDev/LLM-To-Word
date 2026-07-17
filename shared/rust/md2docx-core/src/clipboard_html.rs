//! Word-friendly rich HTML for the browser clipboard.
//!
//! Clipboard HTML is a delivery format of its own.  Word does not inherit the
//! extension popup's CSS, so every important layout rule is carried inline.

use crate::{math, theme};

pub fn render(raw_html: &str) -> String {
    let mut html = render_math(raw_html);

    // Block styling is deliberately inline: Word's HTML clipboard importer is
    // more consistent with inline CSS than with extension-scoped stylesheets.
    for (from, to) in [
        (
            "<p>",
            "<p dir=\"auto\" style=\"margin:0 0 4pt 0;line-height:1.15;mso-line-height-rule:auto;\">",
        ),
        (
            "<hr />",
            "<hr style=\"border:0;border-top:0.75pt solid #d9e2f3;margin:8pt 0;\" />",
        ),
        (
            "<blockquote>",
            "<blockquote dir=\"auto\" style=\"margin:6pt 0;padding:5pt 10pt;background:#f8fafc;border-right:1.75pt solid #5b7fa3;border-left:0;color:#374151;\">",
        ),
        (
            "<ul>",
            "<ul dir=\"auto\" style=\"margin:3pt 0 5pt 0;padding-inline-start:22pt;\">",
        ),
        (
            "<ol>",
            "<ol dir=\"auto\" style=\"margin:3pt 0 5pt 0;padding-inline-start:22pt;\">",
        ),
        (
            "<li>",
            "<li dir=\"auto\" style=\"margin:0 0 2pt 0;line-height:1.15;\">",
        ),
        (
            "<pre>",
            "<pre dir=\"ltr\" style=\"font-family:'Courier New',monospace;font-size:9.5pt;line-height:1.2;background:#f3f4f6;border:1px solid #d1d5db;border-radius:3px;padding:7pt;margin:6pt 0;white-space:pre-wrap;word-break:break-word;text-align:left;\">",
        ),
        (
            "<code>",
            "<code dir=\"ltr\" style=\"font-family:'Courier New',monospace;font-size:9.5pt;background:#f3f4f6;color:#7f1d1d;padding:1pt 2pt;unicode-bidi:isolate;\">",
        ),
        (
            "<table dir=\"rtl\">",
            "<table dir=\"rtl\" style=\"border-collapse:collapse;border-spacing:0;width:100%;margin:6pt 0;table-layout:auto;direction:rtl;mso-table-lspace:0pt;mso-table-rspace:0pt;\">",
        ),
        (
            "<table>",
            "<table dir=\"ltr\" style=\"border-collapse:collapse;border-spacing:0;width:100%;margin:6pt 0;table-layout:auto;mso-table-lspace:0pt;mso-table-rspace:0pt;\">",
        ),
        (
            "<th>",
            "<th style=\"border:0.75pt solid #b7c9db;padding:4pt 5pt;text-align:center;vertical-align:middle;line-height:1.0;background:#d9eaf7;color:#17365d;font-weight:700;\">",
        ),
        (
            "<td>",
            concat!(
                "<td style=\"",
                "border:0.75pt solid #b7c9db;padding:4pt 5pt;text-align:center;vertical-align:middle;line-height:1.0;",
                "\">"
            ),
        ),
        ("<dl>", "<dl dir=\"auto\" style=\"margin:4pt 0;\">"),
        ("<dt>", "<dt style=\"font-weight:700;margin-top:3pt;\">"),
        ("<dd>", "<dd style=\"margin:0 0 3pt 18pt;\">"),
    ] {
        html = html.replace(from, to);
    }

    for heading in theme::HEADINGS {
        let level = heading.level;
        let from = format!("<h{level}>");
        let border = if level == 1 {
            format!(
                "padding:0 0 3pt 0;border-bottom:0.75pt solid #{};",
                theme::HEADING_BORDER.to_ascii_lowercase()
            )
        } else {
            String::new()
        };
        let to = format!(
            "<h{level} dir=\"auto\" style=\"font-family:{},sans-serif;font-size:{}pt;line-height:1.1;color:#{};margin:{}pt 0 {}pt 0;{border}font-weight:700;\">",
            theme::FONT,
            theme::points_from_half_points(heading.half_points),
            heading.color.to_ascii_lowercase(),
            theme::points_from_twips(heading.before_twips),
            theme::points_from_twips(heading.after_twips),
        );
        html = html.replace(&from, &to);
    }

    // Fenced code has a class attribute and therefore does not match <code>.
    html = html.replace("<code class=\"", "<code dir=\"ltr\" style=\"font-family:'Courier New',monospace;font-size:9.5pt;background:transparent;color:#111827;unicode-bidi:isolate;\" class=\"");
    html = shade_alternate_table_rows(&html);

    html = resolve_auto_directions(&html);
    html = html.replace(
        "<blockquote dir=\"ltr\" style=\"margin:6pt 0;padding:5pt 10pt;background:#f8fafc;border-right:1.75pt solid #5b7fa3;border-left:0;color:#374151;\">",
        "<blockquote dir=\"ltr\" style=\"margin:6pt 0;padding:5pt 10pt;background:#f8fafc;border-left:1.75pt solid #5b7fa3;border-right:0;color:#374151;\">",
    );
    let direction = if contains_rtl(&html) { "rtl" } else { "ltr" };
    let body_size = theme::points_from_half_points(theme::BODY_HALF_POINTS);
    format!(
        "<!--StartFragment--><div class=\"md2docx\" dir=\"{direction}\" style=\"font-family:{},sans-serif;font-size:{body_size}pt;line-height:1.15;color:#{};background:#ffffff;max-width:100%;\">{html}</div><!--EndFragment-->",
        theme::FONT,
        theme::BODY_COLOR.to_ascii_lowercase()
    )
}

fn shade_alternate_table_rows(input: &str) -> String {
    let mut output = String::with_capacity(input.len() + 64);
    let mut remaining = input;
    while let Some(body_start) = remaining.find("<tbody>") {
        output.push_str(&remaining[..body_start + "<tbody>".len()]);
        let after_start = &remaining[body_start + "<tbody>".len()..];
        let Some(body_end) = after_start.find("</tbody>") else {
            output.push_str(after_start);
            return output;
        };
        let mut body = &after_start[..body_end];
        let mut row = 0;
        while let Some(row_start) = body.find("<tr>") {
            output.push_str(&body[..row_start]);
            if row % 2 == 1 {
                output.push_str("<tr style=\"background:#f8fafc;\">");
            } else {
                output.push_str("<tr>");
            }
            body = &body[row_start + "<tr>".len()..];
            row += 1;
        }
        output.push_str(body);
        output.push_str("</tbody>");
        remaining = &after_start[body_end + "</tbody>".len()..];
    }
    output.push_str(remaining);
    output
}

fn resolve_auto_directions(input: &str) -> String {
    let mut output = input.to_string();
    let mut search_from = 0;
    const AUTO: &str = "dir=\"auto\"";
    while let Some(relative) = output[search_from..].find(AUTO) {
        let attribute = search_from + relative;
        let Some(open_start) = output[..attribute].rfind('<') else {
            break;
        };
        let Some(open_end_relative) = output[attribute..].find('>') else {
            break;
        };
        let open_end = attribute + open_end_relative;
        let tag_end = output[open_start + 1..]
            .find(|value: char| value.is_whitespace() || value == '>')
            .map(|value| open_start + 1 + value)
            .unwrap_or(open_end);
        let tag = &output[open_start + 1..tag_end];
        let closing = format!("</{tag}>");
        let content_end = output[open_end + 1..]
            .find(&closing)
            .map(|value| open_end + 1 + value)
            .unwrap_or(open_end + 1);
        let direction = if contains_rtl(&output[open_end + 1..content_end]) {
            "rtl"
        } else {
            "ltr"
        };
        output.replace_range(
            attribute..attribute + AUTO.len(),
            &format!("dir=\"{direction}\""),
        );
        search_from = attribute + AUTO.len();
    }
    output
}

fn contains_rtl(value: &str) -> bool {
    value
        .chars()
        .any(|character| matches!(character as u32, 0x0590..=0x08ff))
}

fn render_math(input: &str) -> String {
    let mut output = String::with_capacity(input.len() + 128);
    let mut remaining = input;
    const OPEN: &str = "<span data-math-style=\"";
    const CLOSE: &str = "</span>";
    while let Some(start) = remaining.find(OPEN) {
        output.push_str(&remaining[..start]);
        let after_open = &remaining[start + OPEN.len()..];
        let Some(quote) = after_open.find("\">") else {
            output.push_str(&remaining[start..]);
            return output;
        };
        let kind = &after_open[..quote];
        let content = &after_open[quote + 2..];
        let Some(end) = content.find(CLOSE) else {
            output.push_str(&remaining[start..]);
            return output;
        };
        output.push_str(&math::to_html(
            &unescape(content[..end].trim()),
            kind == "display",
        ));
        remaining = &content[end + CLOSE.len()..];
    }
    output.push_str(remaining);
    output
}

fn unescape(value: &str) -> String {
    value
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", "\"")
        .replace("&#39;", "'")
        .replace("&amp;", "&")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn word_clipboard_theme_is_inline_and_math_is_rendered() {
        let html = render(
            "<h1>כותרת</h1>\n<p><span data-math-style=\"display\">\\frac{\\theta_1}{2}</span></p>\n<table dir=\"rtl\"><tr><th>א</th></tr><tr><td>1</td></tr></table>\n",
        );
        assert!(html.starts_with("<!--StartFragment-->"));
        assert!(html.contains("font-family:Arial"));
        assert!(html.contains("text-align:center;vertical-align:middle"));
        assert!(html.contains("md2docx-math-display"));
        assert!(html.contains("θ"));
        assert!(html.contains("<msub"));
        assert!(html.contains("<mfrac>"));
        assert!(!html.contains(r"\frac"));
        assert!(!html.contains(r"\theta"));
    }

    #[test]
    fn clipboard_resolves_direction_and_matches_alternate_table_banding() {
        let html = render(
            "<blockquote><p>English quote</p></blockquote><table dir=\"rtl\"><tbody><tr><td>א</td></tr><tr><td>ב</td></tr></tbody></table>",
        );
        assert!(html.contains("<blockquote dir=\"ltr\""));
        assert!(html.contains("border-left:1.75pt"));
        assert!(html.contains("<p dir=\"ltr\""));
        assert!(html.contains("<tr style=\"background:#f8fafc;\">"));
    }
}
