import geopandas as gpd
from shapely.geometry import box

# 1. 用 GeoPandas 读取大文件
gdf = gpd.read_file('./China.gpkg')

# 2. 定义新田县的边界框（坐标顺序为 xmin, ymin, xmax, ymax）
xin_tian_bbox = box(112.10, 25.70, 112.35, 25.95)

# 3. 进行空间过滤
xin_tian_gdf = gdf[gdf.geometry.intersects(xin_tian_bbox)]

# 4. 保存过滤后的数据
xin_tian_gdf.to_file('xin_tian.gpkg', driver='GPKG')