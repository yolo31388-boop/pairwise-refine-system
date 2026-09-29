"""装备精炼附加属性 - 带9个bug"""
from dataclasses import dataclass, field
import random

@dataclass
class Equipment:
    eid: str
    slot: str
    refine_level: int
    base_atk: float
    stats: dict

class RefineSystem:
    def __init__(self):
        self.equipment: dict[str, Equipment] = {}
        self.stat_pool = ["attack", "defense", "hp", "crit", "speed"]  # bug2: 全局池
        self.pity = {}

    def get_success_rate(self, level):
        # bug1: 显示70%实际15%
        return 0.7

    def refine(self, eid):
        eq = self.equipment[eid]
        actual_rate = 0.15  # bug1
        if random.random() < actual_rate:
            eq.refine_level += 1
            # bug2: 不按部位过滤
            stat = random.choice(self.stat_pool)
            # bug5: 可重复
            eq.stats[stat] = random.randint(1, 100)
            return True
        else:
            # bug4: 直接掉0
            eq.refine_level = 0
            return False

    def get_max_level(self):
        # bug3: 硬编码
        return 15

    def get_stat_bonus(self, eid):
        eq = self.equipment[eid]
        # bug6: 按最终值
        return eq.base_atk * (1 + eq.refine_level * 0.1)

    def use_protect_charm(self, eid):
        # bug7: 直接必成
        self.equipment[eid].refine_level += 1
        return True

    def get_material_cost(self, level):
        # bug8: 固定
        return 10

    def get_set_bonus(self, eids):
        # bug9: 只看数量
        if len(eids) >= 4:
            return {"atk": 100}
        return {}
