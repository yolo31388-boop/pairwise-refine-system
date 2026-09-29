"""装备精炼附加属性系统"""
from dataclasses import dataclass, field
import logging
import random

logger = logging.getLogger(__name__)


DEFAULT_CONFIG = {
    # 精炼成功率，与展示给玩家的数值严格一致
    "success_rate": 0.7,
    # 可选：按等级覆盖成功率，{等级: 成功率}
    "success_rates": {},
    # 精炼等级上限，从配置读取，可动态调整
    "max_level": 15,
    # 每级精炼按基础属性提升的百分比
    "refine_pct_per_level": 0.1,
    # 保护符提高的成功率（加成后上限不超过 100%）
    "protect_charm_bonus": 0.2,
    # 材料消耗基数，实际消耗随精炼等级递增
    "material_cost_base": 10,
    # 套装：需要的件数与平均精炼等级，等级不足效果打折
    "set_required_count": 4,
    "set_required_avg_level": 10,
    "set_bonus": {"atk": 100},
}

# 各装备部位的精炼属性池，严格按部位过滤
SLOT_STAT_POOLS = {
    "weapon": ["attack", "crit", "speed"],
    "ring": ["attack", "crit"],
    "necklace": ["crit", "speed"],
    "armor": ["defense", "hp"],
    "helmet": ["defense", "hp"],
    "boots": ["defense", "speed"],
}
DEFAULT_STAT_POOL = ["attack", "defense", "hp", "crit", "speed"]


@dataclass
class Equipment:
    eid: str
    slot: str
    refine_level: int
    base_atk: float
    stats: dict


class RefineSystem:
    def __init__(self, config=None):
        self.equipment: dict[str, Equipment] = {}
        self.config = dict(DEFAULT_CONFIG)
        if config:
            self.config.update(config)
        self.stat_pool = DEFAULT_STAT_POOL  # 兼容旧接口
        self._protect_charms: dict[str, int] = {}  # eid -> 剩余保护符次数
        self.refine_log: list[dict] = []  # 精炼日志，可查

    def get_success_rate(self, level):
        """成功率与配置严格一致。"""
        rates = self.config.get("success_rates") or {}
        return rates.get(level, self.config["success_rate"])

    def get_max_level(self):
        """等级上限从配置读取，可动态调整。"""
        return self.config["max_level"]

    def refine(self, eid):
        eq = self.equipment[eid]
        max_level = self.get_max_level()
        if eq.refine_level >= max_level:
            logger.info("refine eid=%s 已达等级上限 %d，拒绝精炼", eid, max_level)
            return False

        rate = self.get_success_rate(eq.refine_level)
        protected = self._protect_charms.get(eid, 0) > 0
        if protected:
            self._protect_charms[eid] -= 1
            rate = min(1.0, rate + self.config["protect_charm_bonus"])

        roll = random.random()
        success = roll < rate
        entry = {
            "eid": eid,
            "level": eq.refine_level,
            "rate": rate,
            "roll": roll,
            "protected": protected,
            "success": success,
        }
        self.refine_log.append(entry)
        logger.info(
            "refine eid=%s level=%d rate=%.2f roll=%.4f protected=%s -> %s",
            eid, eq.refine_level, rate, roll, protected,
            "success" if success else "fail",
        )

        if success:
            eq.refine_level += 1
            self._add_stat(eq)
            return True

        # 失败只掉 1 级；保护符生效时不掉级（掉星保护）
        if protected:
            logger.info("refine eid=%s 保护符生效，等级保持 %d", eid, eq.refine_level)
        elif eq.refine_level > 0:
            eq.refine_level -= 1
        return False

    def _add_stat(self, eq):
        """按部位过滤属性池，且已有的属性不重复出现。"""
        pool = SLOT_STAT_POOLS.get(eq.slot, DEFAULT_STAT_POOL)
        available = [s for s in pool if s not in eq.stats]
        if not available:
            logger.info("refine eid=%s 部位 %s 属性池已满，不再附加", eq.eid, eq.slot)
            return
        stat = random.choice(available)
        eq.stats[stat] = random.randint(1, 100)

    def get_stat_bonus(self, eid):
        """百分比精炼加成只按基础属性计算，不包含其他精炼加成。"""
        eq = self.equipment[eid]
        pct = self.config["refine_pct_per_level"]
        return eq.base_atk * (1 + eq.refine_level * pct)

    def use_protect_charm(self, eid):
        """保护符：提高下一次精炼的成功率（上限 100%），并防止失败掉级。"""
        self._protect_charms[eid] = self._protect_charms.get(eid, 0) + 1
        eq = self.equipment[eid]
        rate = min(1.0, self.get_success_rate(eq.refine_level)
                   + self.config["protect_charm_bonus"])
        logger.info("protect charm eid=%s 下次精炼成功率提升至 %.2f", eid, rate)
        return rate

    def get_material_cost(self, level):
        """材料消耗随精炼等级递增，高等级消耗更多。"""
        return self.config["material_cost_base"] * (level + 1)

    def get_set_bonus(self, eids):
        """套装效果：同时检查装备数量和平均精炼等级，等级不足效果打折。"""
        eqs = [self.equipment[e] for e in eids if e in self.equipment]
        required_count = self.config["set_required_count"]
        if len(eqs) < required_count:
            return {}
        avg = sum(eq.refine_level for eq in eqs) / len(eqs)
        required_avg = self.config["set_required_avg_level"]
        factor = min(1.0, avg / required_avg) if required_avg > 0 else 1.0
        if factor <= 0:
            logger.info("set bonus 平均精炼等级 %.1f 不足，无套装效果", avg)
            return {}
        bonus = {k: v * factor for k, v in self.config["set_bonus"].items()}
        logger.info(
            "set bonus count=%d avg_level=%.1f factor=%.2f -> %s",
            len(eqs), avg, factor, bonus,
        )
        return bonus
