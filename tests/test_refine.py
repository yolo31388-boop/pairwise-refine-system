"""精炼系统修复验证：10 项需求"""
import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.engine import RefineSystem, Equipment, SLOT_STAT_POOLS


def make_rs(**config):
    rs = RefineSystem(config or None)
    rs.equipment = {"e1": Equipment("e1", "weapon", 0, 100, {})}
    return rs


class TestRate:
    def test_rate_matches_config_and_is_used(self, monkeypatch):
        rs = make_rs()
        assert rs.get_success_rate(10) == 0.7
        # 实际精炼用的就是配置里的 0.7，而不是暗改的固定值
        monkeypatch.setattr("src.engine.random.random", lambda: 0.69)
        assert rs.refine("e1") is True
        monkeypatch.setattr("src.engine.random.random", lambda: 0.71)
        assert rs.refine("e1") is False

    def test_refine_has_log(self, caplog):
        rs = make_rs()
        with caplog.at_level(logging.INFO, logger="src.engine"):
            rs.refine("e1")
        assert rs.refine_log and rs.refine_log[-1]["rate"] == 0.7
        assert any("rate=0.70" in r.getMessage() for r in caplog.records)


class TestPool:
    def test_stat_pool_filtered_by_slot(self, monkeypatch):
        rs = make_rs()
        monkeypatch.setattr("src.engine.random.random", lambda: 0.0)  # 必成
        for _ in range(10):
            rs.refine("e1")
        stats = rs.equipment["e1"].stats
        assert stats, "精炼成功应附加属性"
        assert set(stats) <= set(SLOT_STAT_POOLS["weapon"])
        assert "defense" not in stats and "hp" not in stats


class TestMaxLevel:
    def test_max_level_from_config_dynamic(self, monkeypatch):
        rs = make_rs()
        assert rs.get_max_level() == 15
        rs.config["max_level"] = 20  # 配置改了，代码里跟着变
        assert rs.get_max_level() == 20
        rs.config["max_level"] = 3
        rs.equipment["e1"].refine_level = 3
        monkeypatch.setattr("src.engine.random.random", lambda: 0.0)
        assert rs.refine("e1") is False  # 到顶后拒绝继续精炼
        assert rs.equipment["e1"].refine_level == 3


class TestFailure:
    def test_failure_drops_one_level_only(self, monkeypatch):
        rs = make_rs()
        rs.equipment["e1"].refine_level = 14
        monkeypatch.setattr("src.engine.random.random", lambda: 0.99)  # 必败
        assert rs.refine("e1") is False
        assert rs.equipment["e1"].refine_level == 13  # 只掉 1 级，不回 0

    def test_protect_charm_prevents_drop(self, monkeypatch):
        rs = make_rs()
        rs.equipment["e1"].refine_level = 14
        rs.use_protect_charm("e1")
        monkeypatch.setattr("src.engine.random.random", lambda: 0.99)  # 必败
        assert rs.refine("e1") is False
        assert rs.equipment["e1"].refine_level == 14  # 掉星保护


class TestNoDuplicate:
    def test_stats_never_repeat(self, monkeypatch):
        rs = make_rs()
        monkeypatch.setattr("src.engine.random.random", lambda: 0.0)  # 必成
        for _ in range(10):
            rs.refine("e1")
        stats = rs.equipment["e1"].stats
        # 不会重复出现同一属性：数量不超过部位池大小
        assert len(stats) <= len(SLOT_STAT_POOLS["weapon"])
        assert len(stats) == len(set(stats))


class TestPercentOnBase:
    def test_percentage_bonus_uses_base_only(self):
        rs = make_rs()
        eq = rs.equipment["e1"]
        eq.refine_level = 10
        eq.stats = {"attack": 500}  # 其他精炼加成不参与百分比计算
        assert rs.get_stat_bonus("e1") == 100 * (1 + 10 * 0.1)


class TestProtectCharm:
    def test_charm_boosts_rate_not_guarantee(self, monkeypatch):
        rs = make_rs()
        boosted = rs.use_protect_charm("e1")
        assert rs.equipment["e1"].refine_level == 0  # 不是直接必成
        assert 0.7 < boosted <= 1.0
        # 0.8 介于原成功率 0.7 与加成后 0.9 之间：有符才成功
        monkeypatch.setattr("src.engine.random.random", lambda: 0.8)
        assert rs.refine("e1") is True

    def test_charm_capped_at_100_percent(self):
        rs = make_rs(success_rate=0.95, protect_charm_bonus=0.2)
        assert rs.use_protect_charm("e1") == 1.0


class TestMaterialCost:
    def test_cost_scales_with_level(self):
        rs = make_rs()
        costs = [rs.get_material_cost(lvl) for lvl in range(15)]
        assert all(b > a for a, b in zip(costs, costs[1:]))
        assert rs.get_material_cost(14) > rs.get_material_cost(1)


class TestSetBonus:
    def test_set_bonus_checks_count_and_avg_level(self):
        rs = RefineSystem()
        rs.equipment = {
            f"e{i}": Equipment(f"e{i}", "armor", 0, 100, {}) for i in range(4)
        }
        eids = list(rs.equipment)
        assert rs.get_set_bonus(eids[:3]) == {}  # 数量不足
        assert rs.get_set_bonus(eids) == {}  # 白板不触发满额套装
        for eq in rs.equipment.values():
            eq.refine_level = 5  # 平均等级不足：效果打折
        half = rs.get_set_bonus(eids)
        assert 0 < half["atk"] < 100
        for eq in rs.equipment.values():
            eq.refine_level = 10
        assert rs.get_set_bonus(eids) == {"atk": 100}  # 等级达标：满额
