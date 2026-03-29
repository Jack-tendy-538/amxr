"""
OpenStreetMap 路径规划模块（替代高德 API）
完全开源免费，无调用次数限制，适用于学术研究。

本脚本实现了 gathering.py 中的两个核心功能：
- search_dimension1: 相同时间段相同出行方式（驾车），比较不同配送中心间的通行成本
- search_dimension3: 相同起点终点，比较不同交通工具的通行成本
结果保存为 CSV 文件，包含距离（米）、时间（秒）、成本（元）等字段。

依赖安装：
    pip install osmnx networkx pandas numpy
"""

import os
import csv
import numpy as np
import networkx as nx
import osmnx as ox

# ==================== 配置 OSMnx（兼容 1.0+ 版本） ====================
if hasattr(ox, 'config'):
    # 旧版本（<1.0）
    ox.config(use_cache=True, log_console=False, timeout=60)
else:
    # 新版本（>=1.0）
    ox.settings.use_cache = True
    ox.settings.log_console = False
    ox.settings.timeout = 60

# ==================== 地点坐标（与 gathering.py 完全一致） ====================
# 注意：OSMnx 使用 (纬度, 经度) 顺序，与高德返回的 (经度,纬度) 不同
locations = {
    'A': (25.808093, 112.271926),   # 新圩镇
    'B': (25.73685,  112.2431),     # 石羊镇
    'C': (25.904305, 112.203287),   # 金陵镇
    'D': (25.90751,112.19782),  # 新田县政府
    'E': (25.905820,112.207372)  # 新田县文体中心
}

# ==================== 路网管理器（支持多种出行方式） ====================
class OSMNavigator:
    """基于 OSMnx 的路由引擎，支持驾车、骑行、步行"""

    def __init__(self, place_name="新田县, 永州市, 湖南省, 中国", network_type='drive'):
        """
        参数：
            place_name: 行政区划名称（或经纬度边界框）
            network_type: 'drive'（驾车）, 'bike'（骑行）, 'walk'（步行）
        """
        self.network_type = network_type
        print(f"📥 正在加载 {place_name} 的 {network_type} 路网...")
        # 下载路网（首次运行会从 OpenStreetMap 下载，之后使用缓存）
        self.graph = ox.graph_from_place(
            place_name,
            network_type=network_type,
            simplify=True
        )
        # 投影到 UTM 坐标系（距离单位为米）
        self.graph_proj = ox.project_graph(self.graph)
        print(f"✅ 路网加载完成：{len(self.graph.nodes)} 节点，{len(self.graph.edges)} 边")

    def get_closest_node(self, lat, lon):
        """返回离给定经纬度最近的路网节点 ID"""
        # OSMnx 的 nearest_nodes 参数顺序为 (G, X, Y)，即 (经度, 纬度)
        return ox.distance.nearest_nodes(self.graph, lon, lat)

    def get_route(self, start_lat, start_lon, end_lat, end_lon, weight='length', avg_speed_kmh=None):
        """
        计算两点间最短路径

        参数：
            start_lat, start_lon: 起点坐标
            end_lat, end_lon: 终点坐标
            weight: 最短路径权重（'length' 按距离，'travel_time' 按时间）
            avg_speed_kmh: 平均速度（km/h），用于时间估算。若不指定则根据网络类型自动设置。
        返回：
            dict: 包含距离（米）、时间（秒）、路径节点列表等
        """
        # 获取最近节点
        start_node = self.get_closest_node(start_lat, start_lon)
        end_node = self.get_closest_node(end_lat, end_lon)

        # 计算最短路径
        try:
            route_nodes = nx.shortest_path(
                self.graph_proj,
                source=start_node,
                target=end_node,
                weight=weight
            )
        except nx.NetworkXNoPath:
            print(f"❌ 未找到可达路径：({start_lat},{start_lon}) -> ({end_lat},{end_lon})")
            return None

        # 计算总距离和总时间
        total_dist_m = 0.0
        # 若未指定速度，根据出行方式设置默认值
        if avg_speed_kmh is None:
            speed_map = {'drive': 30, 'bike': 15, 'walk': 5}
            avg_speed_kmh = speed_map.get(self.network_type, 10)
        speed_ms = avg_speed_kmh / 3.6

        for i in range(len(route_nodes) - 1):
            u = route_nodes[i]
            v = route_nodes[i + 1]
            edge_data = self.graph_proj.get_edge_data(u, v)
            if edge_data:
                # 取第一条边（若有多条平行边，长度最小的那条）
                first_edge = list(edge_data.values())[0]
                dist = first_edge.get('length', 0)
                total_dist_m += dist

        total_time_s = total_dist_m / speed_ms if speed_ms > 0 else 0

        return {
            'distance_meters': total_dist_m,
            'distance_km': total_dist_m / 1000.0,
            'duration_seconds': total_time_s,
            'duration_minutes': total_time_s / 60.0,
            'route_nodes': route_nodes
        }

# ==================== 成本计算函数 ====================
def compute_cost(distance_km, transport_mode):
    """
    根据出行方式估算成本（元）
    参考 gathering.py 中的逻辑：
        - 驾车：油费 + 高速费（此处简化仅油费，0.5元/公里）
        - 骑行：电动单车电费（0.025度/公里 × 0.5元/度）
        - 步行：无直接成本
    """
    if transport_mode == '驾车':
        # 假设油耗 0.5元/公里
        return distance_km * 0.5
    elif transport_mode == '骑行':
        # 电动单车：每公里耗电 0.025 度，电价 0.5 元/度
        return distance_km * 0.025 * 0.5
    elif transport_mode == '步行':
        return 0.0
    else:
        return 0.0

# ==================== CSV 写入辅助函数 ====================
def write_to_csv(file_path, data_row, fieldnames):
    """追加写入 CSV，若文件不存在则写入表头"""
    file_exists = os.path.isfile(file_path)
    with open(file_path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(data_row)

# ==================== 数据采集函数（替代原 fetch_data） ====================
def fetch_route_data(api_key_ignored, start_coords, end_coords, transport_mode, output_file):
    """
    参数：
        api_key_ignored: 保留此参数以兼容原接口，实际不用
        start_coords, end_coords: (lat, lon) 元组
        transport_mode: '驾车', '骑行', '步行'
        output_file: CSV 文件路径
    """
    # 映射出行方式到 OSMnx 网络类型
    mode_map = {
        '驾车': 'drive',
        '骑行': 'bike',
        '步行': 'walk'
    }
    osm_mode = mode_map.get(transport_mode, 'drive')

    # 创建导航器（首次调用会加载路网，后续使用缓存）
    # 注意：每次创建不同 network_type 时都会重新下载，建议在外部预创建并复用
    # 这里为简化，每次创建，但实际运行时会因为缓存而不会重复下载
    nav = OSMNavigator(place_name="新田县, 永州市, 湖南省, 中国", network_type=osm_mode)

    # 获取路线结果
    route = nav.get_route(
        start_coords[0], start_coords[1],
        end_coords[0], end_coords[1]
    )
    if route is None:
        print(f"⚠️ 跳过 {transport_mode} 路线：{start_coords} -> {end_coords}")
        return

    # 计算成本
    cost = compute_cost(route['distance_km'], transport_mode)

    # 准备写入数据
    row = {
        'start': f"{start_coords[0]},{start_coords[1]}",
        'destination': f"{end_coords[0]},{end_coords[1]}",
        'transport_mode': transport_mode,
        'distance': route['distance_meters'],
        'duration': route['duration_seconds'],
        'cost': cost
    }
    fieldnames = ['start', 'destination', 'transport_mode', 'distance', 'duration', 'cost']
    write_to_csv(output_file, row, fieldnames)

# ==================== 研究维度1：不同配送中心间驾车成本比较 ====================
def search_dimension1(output_file='Dimension-1.csv'):
    """
    相同出行方式（驾车），不同起点终点间的通行成本比较。
    计算 A→B, B→C, A→C, A→D, A→E, B→D, B→E, C→D, C→E, D→E 共10条路线。
    """
    print("\n🔍 开始维度1数据采集（驾车）...")
    # 预创建驾车导航器，避免重复下载
    nav_drive = OSMNavigator(place_name="新田县, 永州市, 湖南省, 中国", network_type='drive')

    # 定义要计算的配对
    pairs = [('A', 'B'), ('B', 'C'), ('A', 'C'),('A','D'),('A','E'),('B','D'),('B','E'),('C','D'),('C','E'),('D','E')]
    for start_key, end_key in pairs:
        start_coords = locations[start_key]
        end_coords = locations[end_key]
        print(f"  正在计算 {start_key} → {end_key} ...")
        route = nav_drive.get_route(start_coords[0], start_coords[1],
                                    end_coords[0], end_coords[1])
        if route:
            cost = compute_cost(route['distance_km'], '驾车')
            row = {
                'start': f"{start_coords[0]},{start_coords[1]}",
                'destination': f"{end_coords[0]},{end_coords[1]}",
                'transport_mode': '驾车',
                'distance': route['distance_meters'],
                'duration': route['duration_seconds'],
                'cost': cost
            }
            fieldnames = ['start', 'destination', 'transport_mode', 'distance', 'duration', 'cost']
            write_to_csv(output_file, row, fieldnames)
    print(f"✅ 维度1数据已保存至 {output_file}")

# ==================== 研究维度3：不同交通工具成本比较 ====================
def search_dimension3(output_file='Dimension-3.csv'):
    """
    相同起点（A）和终点（B），不同出行方式（驾车、骑行、步行）的成本比较。
    """
    print("\n🔍 开始维度3数据采集（A→B，多种方式）...")
    # 为每种出行方式单独创建导航器
    start_coords = locations['A']
    end_coords = locations['B']
    modes = ['驾车', '骑行', '步行']
    for mode in modes:
        print(f"  正在计算 {mode} 路线...")
        osm_mode = {'驾车': 'drive', '骑行': 'bike', '步行': 'walk'}[mode]
        nav = OSMNavigator(place_name="新田县, 永州市, 湖南省, 中国", network_type=osm_mode)
        route = nav.get_route(start_coords[0], start_coords[1],
                              end_coords[0], end_coords[1])
        if route:
            cost = compute_cost(route['distance_km'], mode)
            row = {
                'start': f"{start_coords[0]},{start_coords[1]}",
                'destination': f"{end_coords[0]},{end_coords[1]}",
                'transport_mode': mode,
                'distance': route['distance_meters'],
                'duration': route['duration_seconds'],
                'cost': cost
            }
            fieldnames = ['start', 'destination', 'transport_mode', 'distance', 'duration', 'cost']
            write_to_csv(output_file, row, fieldnames)
    print(f"✅ 维度3数据已保存至 {output_file}")

# ==================== 主程序 ====================
def main():
    """
    运行两个研究维度的数据采集。
    """
    # 注意：OSMnx 首次下载路网可能需要几分钟，请耐心等待
    print("=" * 60)
    print("OSMnx 路径规划分析（基于 OpenStreetMap）")
    print("=" * 60)
    # 维度1：驾车路线
    search_dimension1('data/works/Dimension-1.csv')
    # 维度3：不同交通工具
    search_dimension3('data/works/Dimension-3.csv')
    print("\n🎉 所有数据采集完成！")

if __name__ == "__main__":
    main()