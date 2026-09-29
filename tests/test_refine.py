"""精炼系统行为测试"""
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
    def test_success_rate_matches_config(self):
        rs = make_rs(default_success_rate=0.6,
                     success_rates={5: 0.3})
        assert rs.get_success_rate(0) == 0.6
        assert rs.get_success_rate(5) == 0.3

    def test_actual_refine_uses_config_rate(self, monkeypatch):
        rs = make_rs(default_success_rate=0.5)
        monkeypatch.setattr("random.random", lambda: 0.49)
        assert rs.refine("e1") is True
        monkeypatch.setattr("random.random", lambda: 0.51)
        assert rs.refine("e1") is False

    def test_refine_attempt_logged(self, caplog):
        rs = make_rs()
        with caplog.at_level(logging.INFO, logger="src.engine"):
            rs.refine("e1")
        messages = [r.getMessage() for r in caplog.records]
        assert any("eid=e1" in m and "rate=" in m for m in messages)


class TestPool:
    def test_stat_pool_filtered_by_slot(self, monkeypatch):
        monkeypatch.setattr("random.random", lambda: 0.0)
        for slot, pool in SLOT_STAT_POOLS.items():
            rs = make_rs()
            rs.equipment["e1"].slot = slot
            for _ in range(len(pool) + 2):
                rs.refine("e1")
            assert set(rs.equipment["e1"].stats) <= set(pool)
        # 武器只出攻击类属性
        assert "defense" not in SLOT_STAT_POOLS["weapon"]
        assert "hp" not in SLOT_STAT_POOLS["weapon"]

    def test_no_duplicate_stats(self, monkeypatch):
        monkeypatch.setattr("random.random", lambda: 0.0)
        rs = make_rs()
        pool = SLOT_STAT_POOLS["weapon"]
        for _ in range(len(pool) + 3):
            rs.refine("e1")
        stats = rs.equipment["e1"].stats
        assert len(stats) == len(pool)  # 池子抽完不重复出现
        assert rs.equipment["e1"].refine_level == len(pool) + 3


class TestLevel:
    def test_max_level_from_config(self, monkeypatch):
        rs = make_rs(max_refine_level=20)
        assert rs.get_max_level() == 20
        rs.config["max_refine_level"] = 3  # 动态调整
        assert rs.get_max_level() == 3
        monkeypatch.setattr("random.random", lambda: 0.0)
        eq = rs.equipment["e1"]
        eq.refine_level = 3
        assert rs.refine("e1") is False
        assert eq.refine_level == 3

    def test_failure_drops_one_level(self, monkeypatch):
        rs = make_rs()
        rs.equipment["e1"].refine_level = 14
        monkeypatch.setattr("random.random", lambda: 0.999)
        assert rs.refine("e1") is False
        assert rs.equipment["e1"].refine_level == 13

    def test_protect_charm_prevents_level_drop(self, monkeypatch):
        rs = make_rs()
        rs.equipment["e1"].refine_level = 14
        rs.use_protect_charm("e1")
        monkeypatch.setattr("random.random", lambda: 0.999)
        assert rs.refine("e1") is False
        assert rs.equipment["e1"].refine_level == 14  # 掉星保护


class TestStats:
    def test_percent_stat_uses_base_value(self):
        rs = make_rs()
        eq = rs.equipment["e1"]
        eq.refine_level = 14
        eq.stats = {"crit": 0.1, "attack": 50}
        # 百分比只按基础值100算：100 + 100*14*0.1 + 50 + 100*0.1
        assert rs.get_stat_bonus("e1") == pytest.approx(300.0)


class TestProtectCharm:
    def test_charm_boosts_rate_not_guarantee(self, monkeypatch):
        rs = make_rs(default_success_rate=0.5, protect_charm_rate_bonus=0.2)
        rs.use_protect_charm("e1")
        assert rs.get_effective_rate("e1") == pytest.approx(0.7)
        monkeypatch.setattr("random.random", lambda: 0.75)
        assert rs.refine("e1") is False  # 不是必成

    def test_charm_rate_capped_at_100(self):
        rs = make_rs(default_success_rate=0.9, protect_charm_rate_bonus=0.2)
        rs.use_protect_charm("e1")
        assert rs.get_effective_rate("e1") == 1.0


class TestMaterial:
    def test_material_cost_scales_with_level(self):
        rs = make_rs()
        assert rs.get_material_cost(0) < rs.get_material_cost(7)
        assert rs.get_material_cost(7) < rs.get_material_cost(14)


class TestSetBonus:
    def test_set_bonus_requires_avg_refine_level(self):
        rs = make_rs()
        rs.equipment = {
            f"e{i}": Equipment(f"e{i}", "armor", level, 100, {})
            for i, level in enumerate([0, 0, 0, 0])
        }
        assert rs.get_set_bonus(list(rs.equipment)) == {}  # 白板不触发
        for i, eq in enumerate(rs.equipment.values()):
            eq.refine_level = 5
        assert rs.get_set_bonus(list(rs.equipment)) == {"atk": 50}  # 打折
        for eq in rs.equipment.values():
            eq.refine_level = 10
        assert rs.get_set_bonus(list(rs.equipment)) == {"atk": 100}  # 满效果
