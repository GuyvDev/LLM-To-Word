//! One visual theme shared by native DOCX and formatted clipboard output.

pub const FONT: &str = "Arial";
pub const BODY_COLOR: &str = "1F2937";
pub const BODY_HALF_POINTS: u16 = 23;
pub const BODY_AFTER_TWIPS: u16 = 80;
pub const BODY_LINE_TWIPS: u16 = 276;

pub const HEADING_BORDER: &str = "D9E2F3";
pub const TABLE_BORDER: &str = "B7C9DB";
pub const TABLE_INNER_BORDER: &str = "D9E2EC";
pub const TABLE_HEADER_FILL: &str = "D9EAF7";
pub const QUOTE_FILL: &str = "F8FAFC";
pub const QUOTE_BORDER: &str = "5B7FA3";

#[derive(Clone, Copy)]
pub struct Heading {
    pub level: u8,
    pub half_points: u16,
    pub color: &'static str,
    pub before_twips: u16,
    pub after_twips: u16,
}

pub const HEADINGS: [Heading; 6] = [
    Heading {
        level: 1,
        half_points: 42,
        color: "17365D",
        before_twips: 0,
        after_twips: 100,
    },
    Heading {
        level: 2,
        half_points: 32,
        color: "1F4E79",
        before_twips: 180,
        after_twips: 60,
    },
    Heading {
        level: 3,
        half_points: 27,
        color: "334155",
        before_twips: 140,
        after_twips: 40,
    },
    Heading {
        level: 4,
        half_points: 24,
        color: "334155",
        before_twips: 120,
        after_twips: 40,
    },
    Heading {
        level: 5,
        half_points: 22,
        color: "475569",
        before_twips: 100,
        after_twips: 30,
    },
    Heading {
        level: 6,
        half_points: 21,
        color: "475569",
        before_twips: 80,
        after_twips: 30,
    },
];

pub fn points_from_twips(value: u16) -> String {
    compact_decimal(value as f32 / 20.0)
}

pub fn points_from_half_points(value: u16) -> String {
    compact_decimal(value as f32 / 2.0)
}

fn compact_decimal(value: f32) -> String {
    if value.fract() == 0.0 {
        format!("{value:.0}")
    } else {
        format!("{value:.1}")
    }
}
