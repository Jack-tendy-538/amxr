"""
新田县生鲜配送路径优化模型 - 完整实现代码
模型逻辑：
1. AHP 加权计算路段综合成本 G_ij（使用距离、理论时间、路况系数 R）
2. 实际行驶时间由距离和拥堵等级（硬编码）决定
3. 节约算法构造路径，同时考虑载重约束和时间窗惩罚
4. 最终总成本 = 所有路段 G_ij 之和 + 时间窗惩罚之和
"""

import numpy as np
from typing import List, Tuple, Dict

class XintianDeliveryOptimizer:
    """新田县生鲜配送路径优化器"""

    def __init__(self):
        """AHP 权重（可根据实际调整）"""
        self.psi_distance = 0.1047    # 距离权重
        self.psi_time = 0.2583        # 时间权重（使用理论时间）
        self.psi_road = 0.6370        # 路况系数权重（独立于拥堵）

        # 时间窗惩罚系数
        self.alpha = 10.0   # 早到惩罚 (元/小时)
        self.beta = 50.0    # 晚到惩罚 (元/小时)

        # 服务时间 (小时)
        self.service_time = 0.25   # 15分钟

        # 基准速度 (km/h) 用于计算理论时间
        self.base_speed = 40.0

    def normalize_matrix(self, matrix: np.ndarray) -> np.ndarray:
        """Min-Max 归一化（越小越好）"""
        min_val = np.min(matrix)
        max_val = np.max(matrix)
        if max_val == min_val:
            return np.zeros_like(matrix)
        return (matrix - min_val) / (max_val - min_val)

    def calculate_comprehensive_cost(self, d_matrix: np.ndarray,
                                     t_theoretical: np.ndarray,
                                     r_matrix: np.ndarray) -> np.ndarray:
        """
        计算 AHP 综合成本矩阵 G_ij
        G_ij = ψ1*D_norm + ψ2*T_norm + ψ3*R_norm
        """
        D_norm = self.normalize_matrix(d_matrix)
        T_norm = self.normalize_matrix(t_theoretical)
        R_norm = self.normalize_matrix(r_matrix)

        G_matrix = (self.psi_distance * D_norm +
                    self.psi_time * T_norm +
                    self.psi_road * R_norm)
        return G_matrix

    def calculate_time_window_penalty(self, arrival_time: float,
                                      time_window: Tuple[float, float]) -> float:
        """计算单个客户的时间窗惩罚"""
        et, lt = time_window
        early_penalty = max(et - arrival_time, 0) * self.alpha
        late_penalty = max(arrival_time - lt, 0) * self.beta
        return early_penalty + late_penalty

    def simulate_route_timing(self, route: List[int],
                              start_time: float,
                              t_actual: np.ndarray,
                              time_windows: List[Tuple[float, float]]) -> Dict:
        """
        模拟路线的时间安排，返回到达时间、惩罚等
        t_actual: 实际行驶时间矩阵（由距离和拥堵速度决定）
        """
        current_time = start_time
        arrival_times = []
        penalties = []
        total_penalty = 0.0

        for i in range(1, len(route)):
            prev = route[i-1]
            curr = route[i]
            travel = t_actual[prev, curr]
            current_time += travel

            if curr != 0:  # 不是配送中心
                arrival_times.append((curr, current_time))
                penalty = self.calculate_time_window_penalty(current_time, time_windows[curr])
                penalties.append((curr, penalty))
                total_penalty += penalty
                current_time += self.service_time

        return {
            'arrival_times': arrival_times,
            'penalties': penalties,
            'total_penalty': total_penalty,
            'finish_time': current_time
        }

    def savings_algorithm_with_time_windows(self,
                                            G_matrix: np.ndarray,
                                            demands: List[float],
                                            time_windows: List[Tuple[float, float]],
                                            t_actual: np.ndarray,
                                            vehicle_capacity: float = 1500,
                                            start_time: float = 6.0) -> Dict:
        """
        带时间窗约束的节约里程法
        - G_matrix: 路段综合成本（AHP）
        - t_actual: 实际行驶时间（用于惩罚）
        """
        n = len(demands)
        # 初始路线：每个客户单独往返
        routes = [[0, i, 0] for i in range(1, n)]
        route_demands = [demands[i] for i in range(1, n)]

        # 计算节约值 S_ij = G[0,i] + G[0,j] - G[i,j]
        savings = []
        for i in range(1, n):
            for j in range(i+1, n):
                saving = G_matrix[0, i] + G_matrix[0, j] - G_matrix[i, j]
                savings.append((saving, i, j))
        savings.sort(reverse=True, key=lambda x: x[0])

        # 尝试合并
        for saving, i, j in savings:
            # 找到 i 和 j 所在的路线索引
            idx_i = idx_j = -1
            route_i = route_j = None
            for idx, route in enumerate(routes):
                if i in route and route[0]==0 and route[-1]==0:
                    idx_i, route_i = idx, route
                if j in route and route[0]==0 and route[-1]==0:
                    idx_j, route_j = idx, route
            if idx_i == idx_j or route_i is None or route_j is None:
                continue

            # 载重约束
            combined_demand = route_demands[idx_i] + route_demands[idx_j]
            if combined_demand > vehicle_capacity:
                continue

            # 尝试两种合并顺序，选择总成本较低的
            candidates = []
            # 顺序1: route_i 后接 route_j (去掉 route_j 的起点 0)
            new_route1 = route_i[:-1] + [x for x in route_j if x != 0]
            # 顺序2: route_j 后接 route_i
            new_route2 = route_j[:-1] + [x for x in route_i if x != 0]

            for new_route in [new_route1, new_route2]:
                # 行驶成本
                travel_cost = 0.0
                for k in range(len(new_route)-1):
                    travel_cost += G_matrix[new_route[k], new_route[k+1]]
                # 时间窗惩罚
                timing = self.simulate_route_timing(new_route, start_time, t_actual, time_windows)
                total = travel_cost + timing['total_penalty']
                candidates.append({
                    'route': new_route,
                    'travel_cost': travel_cost,
                    'penalty': timing['total_penalty'],
                    'total': total,
                    'timing': timing
                })

            if candidates:
                best = min(candidates, key=lambda x: x['total'])
                # 执行合并
                routes[idx_i] = best['route']
                routes.pop(idx_j)
                route_demands[idx_i] = combined_demand
                route_demands.pop(idx_j)

        # 过滤空路线
        final_routes = [r for r in routes if len(r) > 2]

        # 计算最终总成本
        total_travel = 0.0
        total_penalty = 0.0
        all_timings = []
        for route in final_routes:
            for k in range(len(route)-1):
                total_travel += G_matrix[route[k], route[k+1]]
            timing = self.simulate_route_timing(route, start_time, t_actual, time_windows)
            total_penalty += timing['total_penalty']
            all_timings.append(timing)

        return {
            'routes': final_routes,
            'total_cost': total_travel + total_penalty,
            'travel_cost': total_travel,
            'penalty_cost': total_penalty,
            'vehicle_count': len(final_routes),
            'timing_results': all_timings
        }


# ==================== 主程序：在这里填写你的数据 ====================
if __name__ == "__main__":
    optimizer = XintianDeliveryOptimizer()

    # ------------------------------
    # 1. 定义节点顺序（索引 0 为配送中心，1~n 为客户）
    # 例如：0-东升农场, 1-新圩镇, 2-石羊镇, 3-金陵镇, 4-陶岭镇, 5-其他镇
    # ------------------------------
    num_nodes = 6   # 总节点数（含配送中心）

    # ========== 在这里填写你的数据 ==========
    # 2. 距离矩阵 d_matrix (公里)  对称矩阵，对角线为0
    d_matrix = np.array([
        [0, 11.5, 24.5, 15.0, 16.0, 15.9],
        [11.5, 0, 0, 0, 0, 0],
        [24.5, 0, 0, 0, 0, 0],
        [15.0, 0, 0, 0, 0, 0],
        [16.0, 0, 0, 0, 0, 0],
        [15.9, 0, 0, 0, 0, 0]
    ])
    # 补全对称
    for i in range(num_nodes):
        for j in range(i+1, num_nodes):
            d_matrix[j,i] = d_matrix[i,j]

    # 3. 路况系数矩阵 r_matrix (无量纲，越大表示道路越差/成本越高)  与拥堵无关
    r_matrix = np.array([
        [1.0, 1.2, 1.5, 1.2, 1.0, 1.5],
        [1.2, 1.0, 1.2, 1.5, 1.2, 1.0],
        [1.5, 1.2, 1.0, 1.2, 1.5, 1.2],
        [1.2, 1.5, 1.2, 1.0, 1.2, 1.5],
        [1.0, 1.2, 1.5, 1.2, 1.0, 1.2],
        [1.5, 1.0, 1.2, 1.5, 1.2, 1.0]
    ])

    # 4. 拥堵等级矩阵 (1=畅通, 2=缓行, 3=拥堵)  用于计算实际行驶时间
    congestion_level = np.array([
        [1, 2, 3, 2, 1, 3],
        [2, 1, 2, 3, 2, 1],
        [3, 2, 1, 2, 3, 2],
        [2, 3, 2, 1, 2, 3],
        [1, 2, 3, 2, 1, 2],
        [3, 1, 2, 3, 2, 1]
    ])
    # 对称化
    for i in range(num_nodes):
        for j in range(i+1, num_nodes):
            congestion_level[j,i] = congestion_level[i,j]

    # 5. 各客户需求量 (公斤)  索引0为配送中心，填0
    demands = [0, 300, 400, 250, 350, 200]

    # 6. 各客户时间窗 (小时)  格式: (最早时间, 最晚时间)  配送中心无约束
    time_windows = [
        (0, 24),        # 0: 配送中心
        (7.0, 9.0),     # 1: 新圩镇
        (7.5, 9.5),     # 2: 石羊镇
        (8.0, 10.0),    # 3: 金陵镇
        (7.0, 9.0),     # 4: 陶岭镇
        (8.5, 10.5)     # 5: 其他镇
    ]

    # 7. 车辆容量 (公斤) 和 出发时间 (小时)
    vehicle_capacity = 1500
    start_time = 6.0   # 早上6:00

    # ========== 数据填写结束 ==========

    # 步骤1: 计算理论时间矩阵（使用基准速度）
    t_theoretical = d_matrix / optimizer.base_speed

    # 步骤2: 计算实际行驶时间矩阵（由拥堵等级决定速度）
    # 拥堵速度映射 (km/h)
    speed_map = {1: 50, 2: 25, 3: 12}
    t_actual = np.zeros_like(d_matrix)
    for i in range(num_nodes):
        for j in range(num_nodes):
            if i == j:
                t_actual[i,j] = 0
            else:
                level = congestion_level[i,j]
                speed = speed_map[level]
                t_actual[i,j] = d_matrix[i,j] / speed   # 小时

    # 步骤3: 计算 AHP 综合成本矩阵 G_ij
    G_matrix = optimizer.calculate_comprehensive_cost(d_matrix, t_theoretical, r_matrix)

    # 步骤4: 运行节约算法
    print("="*60)
    print("新田县配送路径优化结果")
    print("="*60)
    result = optimizer.savings_algorithm_with_time_windows(
        G_matrix, demands, time_windows, t_actual,
        vehicle_capacity, start_time
    )

    # 输出结果
    print(f"使用车辆数: {result['vehicle_count']}")
    print(f"总行驶成本 (AHP综合): {result['travel_cost']:.4f}")
    print(f"时间窗惩罚成本: {result['penalty_cost']:.2f} 元")
    print(f"总成本: {result['total_cost']:.2f} 元")
    print("\n详细路线:")
    for idx, route in enumerate(result['routes']):
        print(f"  车辆{idx+1}: {' → '.join(map(str, route))}")
        timing = result['timing_results'][idx]
        for node, arr_time in timing['arrival_times']:
            et, lt = time_windows[node]
            print(f"    到达节点{node}: {arr_time:.2f}h (时间窗 [{et:.1f}, {lt:.1f}])")