import dearpygui.dearpygui as dpg

# (bg_rgba, text_rgba) — WoW class colors; text chosen for contrast
CLASS_COLORS: dict[str, tuple[tuple[int, int, int, int], tuple[int, int, int, int]]] = {
    "Warrior":      ((198, 155, 58,  255), (0,   0,   0,   255)),  # WoW Warrior gold
    "Cleric":       ((255, 255, 255, 255), (0,   0,   0,   255)),  # WoW Priest white
    "Paladin":      ((244, 140, 186, 255), (0,   0,   0,   255)),  # WoW Paladin pink
    "Ranger":       ((170, 211, 114, 255), (0,   0,   0,   255)),  # WoW Hunter green
    "Shadow Knight":((196, 30,  58,  255), (255, 255, 255, 255)),  # WoW Death Knight red
    "Druid":        ((255, 124, 10,  255), (0,   0,   0,   255)),  # WoW Druid orange
    "Monk":         ((0,   255, 152, 255), (0,   0,   0,   255)),  # WoW Monk jade
    "Bard":         ((51,  147, 127, 255), (255, 255, 255, 255)),  # WoW Evoker teal
    "Rogue":        ((255, 244, 104, 255), (0,   0,   0,   255)),  # WoW Rogue yellow
    "Shaman":       ((0,   112, 221, 255), (255, 255, 255, 255)),  # WoW Shaman blue
    "Necromancer":  ((135, 136, 238, 255), (0,   0,   0,   255)),  # WoW Warlock purple
    "Wizard":       ((63,  199, 235, 255), (0,   0,   0,   255)),  # WoW Mage cyan
    "Magician":     ((105, 204, 240, 255), (0,   0,   0,   255)),  # WoW Mage lighter
    "Enchanter":    ((163, 48,  201, 255), (255, 255, 255, 255)),  # WoW Demon Hunter purple
    "Beastlord":    ((255, 103, 32,  255), (0,   0,   0,   255)),  # WoW Hunter orange
    "Berserker":    ((212, 32,  32,  255), (255, 255, 255, 255)),  # WoW Warrior red variant
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
