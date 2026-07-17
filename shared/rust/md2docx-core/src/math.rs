#[derive(Clone, Debug, Eq, PartialEq)]
enum Token {
    Command(String),
    Char(char),
    Open,
    Close,
    Sup,
    Sub,
    Cell,
    Row,
}

pub fn to_omml(latex: &str, display: bool) -> String {
    let inner = matrix(latex.trim()).unwrap_or_else(|| Parser::new(latex).sequence(None));
    if display {
        format!(
            "<m:oMathPara><m:oMathParaPr><m:jc m:val=\"centerGroup\"/></m:oMathParaPr><m:oMath>{inner}</m:oMath></m:oMathPara>"
        )
    } else {
        format!("<m:oMath>{inner}</m:oMath>")
    }
}

pub fn to_html(latex: &str, display: bool) -> String {
    let inner =
        mathml_matrix(latex.trim()).unwrap_or_else(|| HtmlParser::new(latex).sequence(None));
    if display {
        format!(
            "<math xmlns=\"http://www.w3.org/1998/Math/MathML\" class=\"md2docx-math-display\" display=\"block\" dir=\"ltr\" style=\"display:block;text-align:center;margin:5pt auto;font-family:'Cambria Math','Times New Roman',serif;font-size:11.5pt;line-height:1.35;unicode-bidi:isolate;\"><mrow>{inner}</mrow></math>"
        )
    } else {
        format!(
            "<math xmlns=\"http://www.w3.org/1998/Math/MathML\" class=\"md2docx-math-inline\" display=\"inline\" dir=\"ltr\" style=\"font-family:'Cambria Math','Times New Roman',serif;font-size:11.5pt;unicode-bidi:isolate;white-space:nowrap;\"><mrow>{inner}</mrow></math>"
        )
    }
}

fn mathml_matrix(source: &str) -> Option<String> {
    for (environment, begin, end) in [
        ("bmatrix", "[", "]"),
        ("pmatrix", "(", ")"),
        ("matrix", "", ""),
    ] {
        let prefix = format!("\\begin{{{environment}}}");
        let suffix = format!("\\end{{{environment}}}");
        let Some(body) = source
            .strip_prefix(&prefix)
            .and_then(|value| value.strip_suffix(&suffix))
        else {
            continue;
        };
        let rows = body
            .split("\\\\")
            .map(|row| {
                let cells = row
                    .split('&')
                    .map(|cell| {
                        format!(
                            "<mtd><mrow>{}</mrow></mtd>",
                            HtmlParser::new(cell.trim()).sequence(None)
                        )
                    })
                    .collect::<String>();
                format!("<mtr>{cells}</mtr>")
            })
            .collect::<String>();
        let table = format!("<mtable>{rows}</mtable>");
        return Some(if begin.is_empty() {
            table
        } else {
            format!("<mrow><mo>{begin}</mo>{table}<mo>{end}</mo></mrow>")
        });
    }
    None
}

fn matrix(source: &str) -> Option<String> {
    for (environment, begin, end) in [
        ("bmatrix", "[", "]"),
        ("pmatrix", "(", ")"),
        ("matrix", "", ""),
    ] {
        let prefix = format!("\\begin{{{environment}}}");
        let suffix = format!("\\end{{{environment}}}");
        let Some(body) = source
            .strip_prefix(&prefix)
            .and_then(|value| value.strip_suffix(&suffix))
        else {
            continue;
        };
        let rows = body
            .split("\\\\")
            .map(|row| {
                let cells = row
                    .split('&')
                    .map(|cell| format!("<m:e>{}</m:e>", Parser::new(cell.trim()).sequence(None)))
                    .collect::<String>();
                format!("<m:mr>{cells}</m:mr>")
            })
            .collect::<String>();
        let matrix = format!("<m:m>{rows}</m:m>");
        return Some(if begin.is_empty() {
            matrix
        } else {
            format!(
                "<m:d><m:dPr><m:begChr m:val=\"{begin}\"/><m:endChr m:val=\"{end}\"/></m:dPr><m:e>{matrix}</m:e></m:d>"
            )
        });
    }
    None
}

struct Parser {
    tokens: Vec<Token>,
    position: usize,
}

struct HtmlParser {
    tokens: Vec<Token>,
    position: usize,
}

impl HtmlParser {
    fn new(source: &str) -> Self {
        Self {
            tokens: tokenize(source),
            position: 0,
        }
    }

    fn group(&mut self) -> String {
        if self.tokens.get(self.position) == Some(&Token::Open) {
            self.position += 1;
            let value = self.sequence(Some(Token::Close));
            if self.tokens.get(self.position) == Some(&Token::Close) {
                self.position += 1;
            }
            value
        } else {
            self.scripted_atom()
        }
    }

    fn atom(&mut self) -> String {
        let Some(token) = self.tokens.get(self.position).cloned() else {
            return String::new();
        };
        self.position += 1;
        match token {
            Token::Open => {
                let value = self.sequence(Some(Token::Close));
                if self.tokens.get(self.position) == Some(&Token::Close) {
                    self.position += 1;
                }
                value
            }
            Token::Command(command) if matches!(command.as_str(), "frac" | "dfrac" | "tfrac") => {
                let numerator = self.group();
                let denominator = self.group();
                format!("<mfrac><mrow>{numerator}</mrow><mrow>{denominator}</mrow></mfrac>")
            }
            Token::Command(command) if command == "sqrt" => {
                let value = self.group();
                format!("<msqrt><mrow>{value}</mrow></msqrt>")
            }
            Token::Command(command)
                if matches!(command.as_str(), "text" | "mathrm" | "operatorname") =>
            {
                self.group()
            }
            Token::Command(command)
                if matches!(command.as_str(), "left" | "right" | "displaystyle") =>
            {
                String::new()
            }
            Token::Command(command) => {
                mathml_token(&symbol(&command).unwrap_or_else(|| format!("\\{command}")))
            }
            Token::Char(value) => mathml_token(&value.to_string()),
            Token::Close | Token::Sup | Token::Sub | Token::Cell | Token::Row => String::new(),
        }
    }

    fn scripted_atom(&mut self) -> String {
        let base = self.atom();
        let mut subscript = String::new();
        let mut superscript = String::new();
        loop {
            match self.tokens.get(self.position) {
                Some(Token::Sub) => {
                    self.position += 1;
                    subscript = self.group();
                }
                Some(Token::Sup) => {
                    self.position += 1;
                    superscript = self.group();
                }
                _ => break,
            }
        }
        match (subscript.is_empty(), superscript.is_empty()) {
            (false, false) => format!(
                "<msubsup><mrow>{base}</mrow><mrow>{subscript}</mrow><mrow>{superscript}</mrow></msubsup>"
            ),
            (false, true) => format!("<msub><mrow>{base}</mrow><mrow>{subscript}</mrow></msub>"),
            (true, false) => format!("<msup><mrow>{base}</mrow><mrow>{superscript}</mrow></msup>"),
            (true, true) => base,
        }
    }

    fn sequence(&mut self, until: Option<Token>) -> String {
        let mut output = String::new();
        while self.position < self.tokens.len() {
            if until
                .as_ref()
                .is_some_and(|token| self.tokens.get(self.position) == Some(token))
            {
                break;
            }
            if matches!(
                self.tokens.get(self.position),
                Some(Token::Close | Token::Cell | Token::Row)
            ) {
                break;
            }
            output.push_str(&self.scripted_atom());
        }
        output
    }
}

impl Parser {
    fn new(source: &str) -> Self {
        Self {
            tokens: tokenize(source),
            position: 0,
        }
    }

    fn group(&mut self) -> String {
        if self.tokens.get(self.position) == Some(&Token::Open) {
            self.position += 1;
            let value = self.sequence(Some(Token::Close));
            if self.tokens.get(self.position) == Some(&Token::Close) {
                self.position += 1;
            }
            value
        } else {
            self.scripted_atom()
        }
    }

    fn atom(&mut self) -> String {
        let Some(token) = self.tokens.get(self.position).cloned() else {
            return String::new();
        };
        self.position += 1;
        match token {
            Token::Open => {
                let value = self.sequence(Some(Token::Close));
                if self.tokens.get(self.position) == Some(&Token::Close) {
                    self.position += 1;
                }
                value
            }
            Token::Command(command) if matches!(command.as_str(), "frac" | "dfrac" | "tfrac") => {
                let numerator = self.group();
                let denominator = self.group();
                format!("<m:f><m:num>{numerator}</m:num><m:den>{denominator}</m:den></m:f>")
            }
            Token::Command(command) if command == "sqrt" => {
                let value = self.group();
                format!(
                    "<m:rad><m:radPr><m:degHide m:val=\"1\"/></m:radPr><m:deg/><m:e>{value}</m:e></m:rad>"
                )
            }
            Token::Command(command)
                if matches!(command.as_str(), "text" | "mathrm" | "operatorname") =>
            {
                self.group()
            }
            Token::Command(command)
                if matches!(command.as_str(), "left" | "right" | "displaystyle") =>
            {
                String::new()
            }
            Token::Command(command) => {
                math_run(symbol(&command).unwrap_or_else(|| format!("\\{command}")))
            }
            Token::Char(value) => math_run(value.to_string()),
            Token::Close | Token::Sup | Token::Sub | Token::Cell | Token::Row => String::new(),
        }
    }

    fn scripted_atom(&mut self) -> String {
        let base = self.atom();
        let mut subscript = String::new();
        let mut superscript = String::new();
        loop {
            match self.tokens.get(self.position) {
                Some(Token::Sub) => {
                    self.position += 1;
                    subscript = self.group();
                }
                Some(Token::Sup) => {
                    self.position += 1;
                    superscript = self.group();
                }
                _ => break,
            }
        }
        match (subscript.is_empty(), superscript.is_empty()) {
            (false, false) => format!(
                "<m:sSubSup><m:e>{base}</m:e><m:sub>{subscript}</m:sub><m:sup>{superscript}</m:sup></m:sSubSup>"
            ),
            (false, true) => {
                format!("<m:sSub><m:e>{base}</m:e><m:sub>{subscript}</m:sub></m:sSub>")
            }
            (true, false) => {
                format!("<m:sSup><m:e>{base}</m:e><m:sup>{superscript}</m:sup></m:sSup>")
            }
            (true, true) => base,
        }
    }

    fn sequence(&mut self, until: Option<Token>) -> String {
        let mut output = String::new();
        while self.position < self.tokens.len() {
            if until
                .as_ref()
                .is_some_and(|token| self.tokens.get(self.position) == Some(token))
            {
                break;
            }
            if matches!(
                self.tokens.get(self.position),
                Some(Token::Close | Token::Cell | Token::Row)
            ) {
                break;
            }
            output.push_str(&self.scripted_atom());
        }
        output
    }
}

fn tokenize(source: &str) -> Vec<Token> {
    let chars = source.chars().collect::<Vec<_>>();
    let mut tokens = Vec::new();
    let mut index = 0;
    while index < chars.len() {
        let value = chars[index];
        if value.is_whitespace() {
            index += 1;
            continue;
        }
        if value == '\\' {
            if chars.get(index + 1) == Some(&'\\') {
                tokens.push(Token::Row);
                index += 2;
                continue;
            }
            let mut end = index + 1;
            while chars.get(end).is_some_and(|ch| ch.is_ascii_alphabetic()) {
                end += 1;
            }
            if end > index + 1 {
                tokens.push(Token::Command(chars[index + 1..end].iter().collect()));
                index = end;
                continue;
            }
            if let Some(next) = chars.get(index + 1) {
                tokens.push(Token::Char(*next));
                index += 2;
                continue;
            }
        }
        tokens.push(match value {
            '{' => Token::Open,
            '}' => Token::Close,
            '^' => Token::Sup,
            '_' => Token::Sub,
            '&' => Token::Cell,
            _ => Token::Char(value),
        });
        index += 1;
    }
    tokens
}

fn math_run(value: impl AsRef<str>) -> String {
    format!("<m:r><m:t>{}</m:t></m:r>", xml(value.as_ref()))
}

fn symbol(command: &str) -> Option<String> {
    let value = match command {
        "alpha" => "α",
        "beta" => "β",
        "gamma" => "γ",
        "delta" => "δ",
        "epsilon" => "ε",
        "theta" => "θ",
        "lambda" => "λ",
        "mu" => "μ",
        "pi" => "π",
        "rho" => "ρ",
        "sigma" => "σ",
        "tau" => "τ",
        "phi" => "φ",
        "chi" => "χ",
        "psi" => "ψ",
        "omega" => "ω",
        "Gamma" => "Γ",
        "Delta" => "Δ",
        "Theta" => "Θ",
        "Lambda" => "Λ",
        "Pi" => "Π",
        "Sigma" => "Σ",
        "Phi" => "Φ",
        "Psi" => "Ψ",
        "Omega" => "Ω",
        "pm" => "±",
        "mp" => "∓",
        "times" => "×",
        "cdot" => "·",
        "div" => "÷",
        "le" | "leq" => "≤",
        "ge" | "geq" => "≥",
        "neq" => "≠",
        "approx" => "≈",
        "infty" => "∞",
        "partial" => "∂",
        "nabla" => "∇",
        "sum" => "∑",
        "prod" => "∏",
        "int" => "∫",
        "oint" => "∮",
        "to" | "rightarrow" => "→",
        "leftarrow" => "←",
        "leftrightarrow" => "↔",
        "in" => "∈",
        "notin" => "∉",
        "subset" => "⊂",
        "supset" => "⊃",
        "subseteq" => "⊆",
        "supseteq" => "⊇",
        "cup" => "∪",
        "cap" => "∩",
        "forall" => "∀",
        "exists" => "∃",
        "neg" => "¬",
        "land" => "∧",
        "lor" => "∨",
        "ldots" => "…",
        "cdots" => "⋯",
        "degree" => "°",
        "quad" => "  ",
        "qquad" => "    ",
        "sin" | "cos" | "tan" | "log" | "ln" | "lim" | "max" | "min" | "det" => command,
        _ => return None,
    };
    Some(value.into())
}

fn xml(value: &str) -> String {
    let mut output = String::with_capacity(value.len());
    for character in value.chars().filter(|character| matches!(*character as u32, 0x9 | 0xa | 0xd | 0x20..=0xd7ff | 0xe000..=0xfffd | 0x10000..=0x10ffff)) {
        match character {
            '&' => output.push_str("&amp;"), '<' => output.push_str("&lt;"), '>' => output.push_str("&gt;"),
            '"' => output.push_str("&quot;"), '\'' => output.push_str("&apos;"), _ => output.push(character),
        }
    }
    output
}

fn html(value: impl AsRef<str>) -> String {
    value
        .as_ref()
        .chars()
        .filter(|character| !character.is_control() || matches!(*character, '\t' | '\n' | '\r'))
        .fold(String::new(), |mut output, character| {
            match character {
                '&' => output.push_str("&amp;"),
                '<' => output.push_str("&lt;"),
                '>' => output.push_str("&gt;"),
                '"' => output.push_str("&quot;"),
                '\'' => output.push_str("&#39;"),
                _ => output.push(character),
            }
            output
        })
}

fn mathml_token(value: &str) -> String {
    let tag = if value
        .chars()
        .all(|character| character.is_ascii_digit() || character == '.')
    {
        "mn"
    } else if value.chars().all(|character| character.is_alphabetic()) {
        "mi"
    } else {
        "mo"
    };
    format!("<{tag}>{}</{tag}>", html(value))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn benchmark_equation_becomes_native_omml() {
        let result = to_omml(
            r"\theta_{t+1} = \theta_t - \alpha \nabla_\theta L(\theta_t)",
            true,
        );
        assert!(result.contains("<m:sSub>"));
        assert!(result.contains("θ"));
        assert!(result.contains("α"));
        assert!(result.contains("∇"));
        assert!(!result.contains(r"\theta"));
        assert!(result.contains("centerGroup"));
    }

    #[test]
    fn nested_brackets_fractions_roots_and_scripts_are_structured() {
        let result = to_omml(
            r"\left[\frac{(a+b)}{\sqrt{x_1}}\right]_{n=1}^{\infty}",
            false,
        );
        for expected in ["<m:f>", "<m:rad>", "<m:sSub>", "<m:sSubSup>", "[", "]", "∞"] {
            assert!(result.contains(expected), "missing {expected}: {result}");
        }
        for forbidden in [r"\left", r"\right", r"\frac", r"\sqrt", r"\infty"] {
            assert!(!result.contains(forbidden), "raw {forbidden}: {result}");
        }
    }

    #[test]
    fn greek_operators_relations_and_arrows_are_converted() {
        let source = r"\alpha \beta \gamma \delta \epsilon \theta \lambda \mu \pi \rho \sigma \tau \phi \chi \psi \omega \Gamma \Delta \Theta \Lambda \Pi \Sigma \Phi \Psi \Omega \pm \mp \times \cdot \div \leq \geq \neq \approx \infty \partial \nabla \sum \prod \int \oint \rightarrow \leftarrow \leftrightarrow \in \notin \subset \supset \subseteq \supseteq \cup \cap \forall \exists \neg \land \lor \ldots \cdots \degree";
        let result = to_omml(source, false);
        for expected in [
            "α", "β", "θ", "Ω", "±", "×", "≤", "≥", "≠", "∞", "∂", "∇", "∑", "∫", "→", "←", "↔",
            "∈", "⊆", "∀", "∃", "∧", "∨", "…", "⋯", "°",
        ] {
            assert!(result.contains(expected), "missing {expected}");
        }
        assert!(!result.contains('\\'), "known command leaked: {result}");
    }

    #[test]
    fn matrices_and_malformed_math_degrade_without_panicking() {
        let matrix = to_omml(r"\begin{pmatrix}a&b\\c&d\end{pmatrix}", true);
        assert!(matrix.contains("<m:m>"));
        assert_eq!(matrix.matches("<m:mr>").count(), 2);
        assert!(matrix.contains("m:begChr m:val=\"(\""));
        assert!(matrix.contains("m:endChr m:val=\")\""));

        for malformed in ["", "{", "}", "x_{", r"\frac{a", r"\sqrt", r"\unknown_{x}"] {
            let result = to_omml(malformed, false);
            assert!(result.starts_with("<m:oMath>"));
            assert!(result.ends_with("</m:oMath>"));
        }
    }

    #[test]
    fn clipboard_math_is_native_importable_mathml_without_raw_known_latex() {
        let result = to_html(
            r"J(\theta)=\frac{1}{m}\sum_{i=1}^{m}(h_\theta(x_i)-y_i)^2",
            true,
        );
        assert!(result.contains("md2docx-math-display"));
        assert!(result.contains("θ"));
        assert!(result.contains("∑"));
        assert!(result.contains("<msub"));
        assert!(result.contains("<msup"));
        assert!(result.contains("<mfrac>"));
        assert!(result.contains("xmlns=\"http://www.w3.org/1998/Math/MathML\""));
        assert!(!result.contains(r"\theta"));
        assert!(!result.contains(r"\frac"));
    }
}
