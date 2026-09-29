"""装备精炼附加属性系统"""
from dataclasses import dataclass, field
import logging
import random

logger = logging.getLogger(__name__)

# 各装备部位允许精炼出的属性池（按部位/类型严格过滤）
SLOT_STAT_POOLS = {
    "weapon": ["attack", "crit", "speed"],      # 武器只出攻击类属性
    "ring": ["crit", "speed", "hp"],
    "necklace": ["hp", "speed"],
    "armor": ["defense", "hp"],
    "helmet": ["defense", "hp"],
    "boots": ["defense", "speed"],
}

# 百分比属性（按基础属性计算，不含其他精炼加成）
PERCENT_STATS = {"crit", "speed"}

DEFAULT_CONFIG = {
    "max_refine_level": 15,          # 精炼等级上限（可动态调整）
    "default_success_rate": 0.7,     # 默认成功率
    "success_rates": {},             # 按等级的成功率覆盖 {level: rate}
    "protect_charm_rate_bonus": 0.2, # 保护符提高的成功率（非必成）
    "base_material_cost": 10,        # 基础材料消耗
    "material_cost_per_level": 2,    # 每级递增的材料消耗
    "refine_level_bonus": 0.1,       # 每精炼等级按基础属性的加成比例
    "set_bonus_min_count": 4,        # 套装生效件数
    "set_bonus_full_avg_level": 10,  # 套装满效果所需平均精炼等级
}


@dataclass
class Equipment:
    eid: str
    slot: str
    refine_level: int
    base_atk: float
    stats: dict = field(default_factory=dict)


class RefineSystem:
    def __init__(self, config=None):
        self.config = dict(DEFAULT_CONFIG)
        if config:
            self.config.update(config)
        self.equipment: dict[str, Equipment] = {}
        self._protect_charms: set[str] = set()

    def get_success_rate(self, level):
        # 显示成功率即实际成功率，统一从配置读取
        return self.config["success_rates"].get(
            level, self.config["default_success_rate"])

    def get_effective_rate(self, eid):
        eq = self.equipment[eid]
        rate = self.get_success_rate(eq.refine_level)
        if eid in self._protect_charms:
            # 保护符提高成功率，上限100%，而非直接必成
            rate = min(1.0, rate + self.config["protect_charm_rate_bonus"])
        return rate

    def get_max_level(self):
        # 等级上限从配置读取，可动态调整
        return self.config["max_refine_level"]

    def refine(self, eid):
        eq = self.equipment[eid]
        if eq.refine_level >= self.get_max_level():
            logger.info("refine eid=%s level=%d 已达上限，无法精炼",
                        eid, eq.refine_level)
            return False
        protected = eid in self._protect_charms
        rate = self.get_effective_rate(eid)
        roll = random.random()
        success = roll < rate
        if success:
            eq.refine_level += 1
            self._add_random_stat(eq)
        elif not protected:
            # 失败只掉1级；保护符触发掉星保护不掉级
            eq.refine_level = max(0, eq.refine_level - 1)
        if protected:
            self._protect_charms.discard(eid)
        logger.info(
            "refine eid=%s level=%d rate=%.2f roll=%.4f success=%s "
            "protected=%s new_level=%d",
            eid, eq.refine_level, rate, roll, success, protected,
            eq.refine_level)
        return success

    def _add_random_stat(self, eq):
        pool = SLOT_STAT_POOLS.get(eq.slot, [])
        # 同一条属性不重复出现
        available = [s for s in pool if s not in eq.stats]
        if not available:
            return
        stat = random.choice(available)
        if stat in PERCENT_STATS:
            eq.stats[stat] = round(random.uniform(0.01, 0.10), 4)
        else:
            eq.stats[stat] = random.randint(1, 100)

    def get_stat_bonus(self, eid):
        eq = self.equipment[eid]
        flat = sum(v for s, v in eq.stats.items() if s not in PERCENT_STATS)
        percent = sum(v for s, v in eq.stats.items() if s in PERCENT_STATS)
        # 百分比属性只按基础属性计算，不包含其他精炼加成
        refine_bonus = eq.base_atk * eq.refine_level * \
            self.config["refine_level_bonus"]
        return eq.base_atk + refine_bonus + flat + eq.base_atk * percent

    def use_protect_charm(self, eid):
        # 使用保护符：下一次精炼提高成功率且失败不掉级
        self._protect_charms.add(eid)
        logger.info("protect charm used eid=%s effective_rate=%.2f",
                    eid, self.get_effective_rate(eid))
        return True

    def get_material_cost(self, level):
        # 材料消耗随精炼等级递增
        return (self.config["base_material_cost"]
                + level * self.config["material_cost_per_level"])

    def get_set_bonus(self, eids):
        # 同时检查装备数量和平均精炼等级，等级不足效果打折
        if len(eids) < self.config["set_bonus_min_count"]:
            return {}
        levels = [self.equipment[e].refine_level for e in eids]
        avg_level = sum(levels) / len(levels)
        full_avg = self.config["set_bonus_full_avg_level"]
        scale = min(1.0, avg_level / full_avg) if full_avg > 0 else 1.0
        if scale <= 0:
            return {}
        return {"atk": int(100 * scale)}
