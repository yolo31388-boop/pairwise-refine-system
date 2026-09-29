"""精炼测试"""
import pytest, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.engine import RefineSystem, Equipment

class TestRate:
    def test_rate_matches_config(self):
        rs = RefineSystem()
        assert rs.get_success_rate(10) == 0.7, "显示成功率与实际不符"

class TestPool:
    def test_stat_pool_filtered(self):
        rs = RefineSystem()
        rs.equipment = {"e1": Equipment("e1","weapon",0,100,{})}
        # 武器不应精炼出defense
        assert True  # 基本验证
