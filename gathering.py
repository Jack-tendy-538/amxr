"""
这个程序将在高德开放平台api接口上爬取数据,并将数据保存到本地文件中。
api密钥将从命令行参数中获取,数据将以json格式保存到data/option-data.csv中。
我们通过研究个体农产品商户运输产品的“通行成本”,了解居民到企业配送中心的可及性（accessibility）,考虑下面的要素:

路程:用导航可以直接获得
路况:指标包括途经红绿灯数、路面情况与拥堵情况
成本:运输成本与时间成本

用AHP层次分析法就好办了

维度1:相同时间段相同出行方式,不同企业配送中心间的“通行成本”
如,7:30~8:30电动单车,比较新圩镇（A）、石羊镇（B）、金陵镇（C）间的“通行成本”
结论:五乡圩到先云路的“通行成本”最低

维度2:相同目的地相同出行方式,不同时间段对“通行成本”的影响
调查A到B间,4:30~5:30、7:30~8:30及15:30~16:30的“通行成本”
结论:7:30~8:30“通行成本”最高

维度3:不同交通工具对“通行成本”的印象
A到B间,使用电动单车、摩头车及小汽车各自的“通行成本”
结论:三轮车“通行成本”最低（尽管如此,三轮车对交通堵塞的印象太大了）
"""
import requests
import csv
import os
import argparse

locations = {
    'A': (112.271926, 25.808093),  # 新圩镇
    'B': (112.2431, 25.73685),     # 石羊镇
    'C': (112.203287, 25.904305)   # 金陵镇
}

def get_route(api_key, origin, destination, mode):
    """根据出行方式调用高德API"""
    base_url = "https://restapi.amap.com/v3/direction/"
    if mode == '驾车':
        url = f"{base_url}driving?origin={origin}&destination={destination}&key={api_key}&extensions=base&strategy=0"
    elif mode == '骑行':
        url = f"{base_url}cycling?origin={origin}&destination={destination}&key={api_key}"
    elif mode == '公交':
        url = f"{base_url}transit/integrated?origin={origin}&destination={destination}&key={api_key}&city=永州"
    else:
        raise ValueError(f"不支持的出行方式: {mode}")

    resp = requests.get(url)
    data = resp.json()
    if data.get('status') != '1':
        print(f"API错误: {data.get('info')}")
        return None
    return data

def parse_route_data(data, mode):
    """从API返回中提取距离、时间、成本（成本需自定义）"""
    if mode == '驾车':
        path = data['route']['paths'][0]
        distance = path['distance']
        duration = path['duration']
        # 成本示例：高速费 + 油费估算（油费按0.5元/km）
        tolls = float(path.get('cost', {}).get('tolls', 0))
        distance_km = float(distance) / 1000
        fuel_cost = distance_km * 0.5
        cost = tolls + fuel_cost
    elif mode == '骑行':
        path = data['route']['paths'][0]
        distance = path['distance']
        duration = path['duration']
        cost = float(distance) / 1000 * 0.025 * 0.5  # 电动单车电费
    elif mode == '公交':
        # 公交数据较复杂，可简化：取票价或估算
        distance = data['route']['distance']
        duration = data['route']['duration']
        cost = data['route']['transits'][0]['cost'] if data['route'].get('transits') else 2.0
    else:
        distance = duration = cost = None
    return distance, duration, cost

def write_csv(file_path, data_row, fieldnames):
    """追加写入CSV，若文件不存在则写入表头"""
    file_exists = os.path.isfile(file_path)
    with open(file_path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(data_row)

def fetch_data(api_key, start, destination, mode, output_file):
    # 将经纬度元组转为字符串
    start_str = f"{start[0]},{start[1]}"
    dest_str = f"{destination[0]},{destination[1]}"
    data = get_route(api_key, start_str, dest_str, mode)
    if data is None:
        return
    distance, duration, cost = parse_route_data(data, mode)
    row = {
        'start': start_str,
        'destination': dest_str,
        'transport_mode': mode,
        'distance': distance,
        'duration': duration,
        'cost': cost
    }
    fieldnames = ['start', 'destination', 'transport_mode', 'distance', 'duration', 'cost']
    write_csv(output_file, row, fieldnames)

def search_1(api_key):
    file_path = 'Dimension-1.csv'
    # 两两组合
    pairs = [('A','B'), ('B','C'), ('A','C')]
    for start_key, end_key in pairs:
        fetch_data(api_key, locations[start_key], locations[end_key], '驾车', file_path)

def search_3(api_key):
    file_path = 'Dimension-3.csv'
    modes = ['驾车', '骑行', '公交']
    for mode in modes:
        fetch_data(api_key, locations['A'], locations['B'], mode, file_path)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--token', dest='api', required=True, help='高德API Key')
    args = parser.parse_args()
    search_1(args.api)
    search_3(args.api)

if __name__ == '__main__':
    main()