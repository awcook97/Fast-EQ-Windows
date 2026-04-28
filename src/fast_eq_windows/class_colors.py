import dearpygui.dearpygui as dpg

# (bg_rgba, text_rgba) — text chosen by luminance rule: 0.299R+0.587G+0.114B > 128 → black, else white
CLASS_COLORS: dict[str, tuple[tuple[int, int, int, int], tuple[int, int, int, int]]] = {
    "Warrior":      ((160, 82,  45,  255), (255, 255, 255, 255)),
    "Cleric":       ((192, 192, 192, 255), (0,   0,   0,   255)),
    "Paladin":      ((218, 165, 32,  255), (0,   0,   0,   255)),
    "Ranger":       ((34,  139, 34,  255), (255, 255, 255, 255)),
    "Shadow Knight":((100, 0,   0,   255), (255, 255, 255, 255)),
    "Druid":        ((107, 142, 35,  255), (255, 255, 255, 255)),
    "Monk":         ((205, 92,  0,   255), (255, 255, 255, 255)),
    "Bard":         ((148, 0,   211, 255), (255, 255, 255, 255)),
    "Rogue":        ((47,  79,  79,  255), (255, 255, 255, 255)),
    "Shaman":       ((0,   128, 128, 255), (255, 255, 255, 255)),
    "Necromancer":  ((88,  0,   0,   255), (255, 255, 255, 255)),
    "Wizard":       ((65,  105, 225, 255), (255, 255, 255, 255)),
    "Magician":     ((0,   150, 210, 255), (255, 255, 255, 255)),
    "Enchanter":    ((75,  0,   130, 255), (255, 255, 255, 255)),
    "Beastlord":    ((188, 100, 0,   255), (255, 255, 255, 255)),
    "Berserker":    ((178, 34,  34,  255), (255, 255, 255, 255)),
}

_DEFAULT_BG: tuple[int, int, int, int] = (80, 80, 80, 255)
_DEFAULT_FG: tuple[int, int, int, int] = (255, 255, 255, 255)


def get_class_colors(eq_class: str) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    return CLASS_COLORS.get(eq_class, (_DEFAULT_BG, _DEFAULT_FG))


def build_class_theme(eq_class: str) -> int:
    bg, fg = get_class_colors(eq_class)
    bg_hover = (min(bg[0] + 30, 255), min(bg[1] + 30, 255), min(bg[2] + 30, 255), 255)
    bg_active = (max(bg[0] - 30, 0), max(bg[1] - 30, 0), max(bg[2] - 30, 0), 255)

    with dpg.theme() as theme_id:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button,        bg,        category=dpg.mvThemeCat_Core)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, bg_hover,  category=dpg.mvThemeCat_Core)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive,  bg_active, category=dpg.mvThemeCat_Core)
            dpg.add_theme_color(dpg.mvThemeCol_Text,          fg,        category=dpg.mvThemeCat_Core)

    return theme_id
