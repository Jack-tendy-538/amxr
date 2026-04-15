import matplotlib.pyplot as plt
import numpy as np

# 定义地点名称和坐标 (纬度, 经度)
locations = {
    "东升农场": (25.94996, 112.25664),
    "新圩镇": (25.808093, 112.271926),
    "石羊镇": (25.73685, 112.2431),
    "金陵镇": (25.904305, 112.203287),
    "陶岭镇": (25.90751, 112.19782),
    "枧头镇": (25.811557, 112.144810)
}

# 定义节点顺序：0-东升农场, 1-新圩镇, 2-石羊镇, 3-金陵镇, 4-陶岭镇, 5-枧头镇
order = ["东升农场", "新圩镇", "石羊镇", "金陵镇", "陶岭镇", "枧头镇"]

# 距离矩阵（单位：公里）—— 从之前的数据填入
d_matrix = np.array([
    [0.000, 49.101, 57.540, 34.172, 33.108, 34.408],   # 0 -> 各点
    [49.101, 0.000, 11.525, 14.921, 15.996, 15.877],
    [57.540, 11.525, 0.000, 24.473, 25.549, 25.430],
    [34.172, 14.921, 24.473, 0.000, 1.063,  0.957],
    [33.108, 15.996, 25.549, 1.063,  0.000, 1.331],
    [34.408, 15.877, 25.430, 0.957,  1.331,  0.000]
])

# 提取坐标列表（按顺序）
coords = [locations[name] for name in order]   # 每个元素为 (lat, lon)

# 画图
plt.figure(figsize=(12, 10))
# 设置字体
plt.rcParams['font.sans-serif'] = ['SimHei']  # 用黑体显示中文
plt.rcParams['axes.unicode_minus'] = False    # 解决负号显示问题
# 绘制点
lats = [c[0] for c in coords]
lons = [c[1] for c in coords]
plt.scatter(lons, lats, c='red', s=100, zorder=5)

# 添加地点标注
for name, (lat, lon) in locations.items():
    plt.annotate(name, (lon, lat), xytext=(8, 8), textcoords='offset points', fontsize=10, fontweight='bold')

# 连线：从东升农场（索引0）到其他所有点
center_idx = 0
for i in range(1, len(coords)):
    x1, y1 = lons[center_idx], lats[center_idx]
    x2, y2 = lons[i], lats[i]
    plt.plot([x1, x2], [y1, y2], 'b-', linewidth=1, alpha=0.7)
    
    # 计算线段中点位置，标注距离
    mid_x = (x1 + x2) / 2
    mid_y = (y1 + y2) / 2
    dist = d_matrix[center_idx, i]
    plt.text(mid_x, mid_y, f'{dist:.1f} km', fontsize=9, ha='center', va='center',
             bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor='none', alpha=0.7))

# 可选：如果你还想画客户之间的某些重要连线（比如相邻很近的点），可以单独添加，例如金陵镇-陶岭镇（距离1.06km）
# 这里演示画一条近邻连线
close_pairs = [(3,4), (3,5), (4,5)]  # 索引3金陵镇,4陶岭镇,5枧头镇
for i,j in close_pairs:
    x1, y1 = lons[i], lats[i]
    x2, y2 = lons[j], lats[j]
    plt.plot([x1, x2], [y1, y2], 'g--', linewidth=1, alpha=0.5)
    mid_x = (x1 + x2) / 2
    mid_y = (y1 + y2) / 2
    dist = d_matrix[i,j]
    plt.text(mid_x, mid_y, f'{dist:.1f} km', fontsize=8, ha='center', va='center',
             bbox=dict(boxstyle='round,pad=0.2', facecolor='lightyellow', edgecolor='none', alpha=0.7))

plt.xlabel("经度")
plt.ylabel("纬度")
plt.title("新田县配送点相对位置及距离（东升农场→各点）")
plt.grid(True, linestyle='--', alpha=0.5)
plt.axis('equal')  # 保持经纬度比例，真实反映形状
plt.tight_layout()
plt.show()