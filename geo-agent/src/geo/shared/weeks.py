from __future__ import annotations

TEST_WEEK_MIN = 900
TEST_WEEK_MAX = 999
TEST_WEEK = 901   # 无法注入 repo 的测试(snapshot 等)统一用此带,与生产周空间隔离

def validate_production_week(week: int) -> int:
    """生产入口周号校验:正数且不落在测试保留带。库函数不加(测试带 tmp repo 直调合法)。"""
    if not isinstance(week, int) or isinstance(week, bool) or week < 1:
        raise ValueError(f"week 必须为正整数: {week!r}")
    if TEST_WEEK_MIN <= week <= TEST_WEEK_MAX:
        raise ValueError(f"week {week} 落在测试保留带 [{TEST_WEEK_MIN},{TEST_WEEK_MAX}];"
                         f"生产周请用 1–{TEST_WEEK_MIN-1},测试请 from geo.shared.weeks import TEST_WEEK")
    return week
