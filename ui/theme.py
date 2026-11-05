# -*- coding: utf-8 -*-
"""统一主题：颜色 / 字体 / 尺寸"""

# 浅色主题
BG          = "#F2F4F7"
CARD        = "#FFFFFF"
CARD_HOVER  = "#FAFBFC"
BORDER      = "#E4E7EC"
BORDER_SOFT = "#EFF1F4"

PRIMARY     = "#2F6BFF"
PRIMARY_DK  = "#1E54E0"
PRIMARY_LT  = "#EBF1FF"

DANGER      = "#E5484D"
DANGER_LT   = "#FEECEC"
WARN        = "#F5A524"
WARN_LT     = "#FEF6E7"
OK          = "#12A150"
OK_LT       = "#E9F9EF"
INFO        = "#0E7C9B"

TEXT        = "#1B2434"
TEXT_SUB    = "#5B6472"
TEXT_MUTED  = "#98A2B3"

SIDEBAR     = "#FFFFFF"
SIDEBAR_SEL = "#EBF1FF"

FONT_FAMILY = "Microsoft YaHei UI"
FONT_MONO   = "Consolas"

F_TITLE     = (FONT_FAMILY, 19, "bold")
F_H1        = (FONT_FAMILY, 15, "bold")
F_H2        = (FONT_FAMILY, 12, "bold")
F_BODY      = (FONT_FAMILY, 10)
F_SMALL     = (FONT_FAMILY, 9)
F_TINY      = (FONT_FAMILY, 8)
F_BIG_NUM   = (FONT_FAMILY, 22, "bold")

LEVEL_COLOR = {
    "high": DANGER,
    "mid":  WARN,
    "low":  TEXT_MUTED,
    "trusted": OK,
}
LEVEL_TEXT = {
    "high": "高风险",
    "mid":  "中风险",
    "low":  "低风险",
    "trusted": "可信",
}
