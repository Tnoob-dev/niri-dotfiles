# ~/.config/kitty/scripts/tab_bar.py
from kitty.fast_data_types import Screen
from kitty.tab_bar import DrawData, ExtraData, TabBarData, draw_tab_with_powerline

def draw_tab(draw_data: DrawData, screen: Screen, tab: TabBarData,
             before: int, max_tab_length: int, index: int,
             is_last: bool, extra_data: ExtraData) -> int:
    draw_tab_with_powerline(
        draw_data, screen, tab, before, max_tab_length,
        index, is_last, extra_data
    )
    return screen.cursor.x