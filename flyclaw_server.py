#!/usr/bin/env python3
"""
FlyClaw 价格服务 - 集成真实 FlyClaw 开源项目
提供真实航班价格查询
"""

import sys
import os

# 添加 FlyClaw 到 Python 路径
sys.path.insert(0, 'e:/TraeProjects/FlyClaw')

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
from math import radians, sin, cos, sqrt, atan2

# 导入 FlyClaw 模块（自动初始化）
from flyclaw import _merge_records, _deduplicate_codeshares
from airport_manager import airport_manager
import config as cfg

def haversine_distance(lat1, lon1, lat2, lon2):
    """使用Haversine公式计算两点之间的球面距离（单位：公里）"""
    R = 6371
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

# 机场数据库（用于获取机场信息）
AIRPORTS = {
    'PEK': {'name': '北京首都国际机场', 'lat': 40.0799, 'lon': 116.5891, 'city': '北京', 'country': 'CN'},
    'PKX': {'name': '北京大兴国际机场', 'lat': 39.5098, 'lon': 116.3958, 'city': '北京', 'country': 'CN'},
    'PVG': {'name': '上海浦东国际机场', 'lat': 31.1443, 'lon': 121.8083, 'city': '上海', 'country': 'CN'},
    'SHA': {'name': '上海虹桥国际机场', 'lat': 31.1944, 'lon': 121.3350, 'city': '上海', 'country': 'CN'},
    'CAN': {'name': '广州白云国际机场', 'lat': 23.3939, 'lon': 113.2997, 'city': '广州', 'country': 'CN'},
    'SZX': {'name': '深圳宝安国际机场', 'lat': 22.6273, 'lon': 113.8916, 'city': '深圳', 'country': 'CN'},
    'HGH': {'name': '杭州萧山国际机场', 'lat': 30.3399, 'lon': 120.3556, 'city': '杭州', 'country': 'CN'},
    'WUH': {'name': '武汉天河国际机场', 'lat': 30.7609, 'lon': 114.3899, 'city': '武汉', 'country': 'CN'},
    'TSN': {'name': '天津滨海国际机场', 'lat': 39.1342, 'lon': 117.4183, 'city': '天津', 'country': 'CN'},
    'NKG': {'name': '南京禄口国际机场', 'lat': 31.8752, 'lon': 118.7892, 'city': '南京', 'country': 'CN'},
    'CGO': {'name': '郑州新郑国际机场', 'lat': 34.5259, 'lon': 113.8074, 'city': '郑州', 'country': 'CN'},
    'XMN': {'name': '厦门高崎国际机场', 'lat': 24.5436, 'lon': 118.1253, 'city': '厦门', 'country': 'CN'},
    'CKG': {'name': '重庆江北国际机场', 'lat': 29.7174, 'lon': 106.6576, 'city': '重庆', 'country': 'CN'},
    'TFU': {'name': '成都天府国际机场', 'lat': 30.5728, 'lon': 104.4669, 'city': '成都', 'country': 'CN'},
    'KMG': {'name': '昆明长水国际机场', 'lat': 25.0492, 'lon': 102.9162, 'city': '昆明', 'country': 'CN'},
    'CTU': {'name': '成都双流国际机场', 'lat': 30.5788, 'lon': 103.9442, 'city': '成都', 'country': 'CN'},
    'XIY': {'name': '西安咸阳国际机场', 'lat': 34.3439, 'lon': 108.7536, 'city': '西安', 'country': 'CN'},
    'NRT': {'name': '东京成田国际机场', 'lat': 35.7720, 'lon': 140.3929, 'city': '东京', 'country': 'JP'},
    'HND': {'name': '东京羽田国际机场', 'lat': 35.5494, 'lon': 139.7798, 'city': '东京', 'country': 'JP'},
    'ICN': {'name': '首尔仁川国际机场', 'lat': 37.4602, 'lon': 126.4406, 'city': '首尔', 'country': 'KR'},
    'SIN': {'name': '新加坡樟宜国际机场', 'lat': 1.3644, 'lon': 103.9915, 'city': '新加坡', 'country': 'SG'},
    'BKK': {'name': '曼谷素万那普国际机场', 'lat': 13.6929, 'lon': 100.7501, 'city': '曼谷', 'country': 'TH'},
    'LAX': {'name': '洛杉矶国际机场', 'lat': 33.9425, 'lon': -118.4081, 'city': '洛杉矶', 'country': 'US'},
    'JFK': {'name': '纽约肯尼迪国际机场', 'lat': 40.6413, 'lon': -73.7781, 'city': '纽约', 'country': 'US'},
    'LHR': {'name': '伦敦希思罗机场', 'lat': 51.4700, 'lon': -0.4543, 'city': '伦敦', 'country': 'GB'},
    'CDG': {'name': '巴黎戴高乐机场', 'lat': 49.0097, 'lon': 2.5479, 'city': '巴黎', 'country': 'FR'},
    'FRA': {'name': '法兰克福国际机场', 'lat': 50.0333, 'lon': 8.5706, 'city': '法兰克福', 'country': 'DE'},
    'DXB': {'name': '迪拜国际机场', 'lat': 25.2532, 'lon': 55.3657, 'city': '迪拜', 'country': 'AE'}
}

class PriceHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        # 设置响应头
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        # 健康检查
        if parsed.path == '/health':
            response = {'status': 'ok', 'service': 'FlyClaw Price API'}
            self.wfile.write(json.dumps(response).encode())
            return

        # 价格查询
        if parsed.path == '/price':
            from_iata = params.get('from', [''])[0].strip().upper()
            to_iata = params.get('to', [''])[0].strip().upper()
            date = params.get('date', [''])[0]

            # 验证参数
            if not from_iata or not to_iata:
                response = {'error': 'Missing parameters: from and to are required'}
                self.wfile.write(json.dumps(response).encode())
                return

            if from_iata == to_iata:
                response = {'error': 'Origin and destination cannot be the same'}
                self.wfile.write(json.dumps(response).encode())
                return

            # 获取机场信息
            from_airport = AIRPORTS.get(from_iata)
            to_airport = AIRPORTS.get(to_iata)

            if from_airport is None:
                response = {'error': 'Origin airport not found: ' + from_iata}
                self.wfile.write(json.dumps(response).encode())
                return

            if to_airport is None:
                response = {'error': 'Destination airport not found: ' + to_iata}
                self.wfile.write(json.dumps(response).encode())
                return

            # 计算距离
            distance = haversine_distance(
                from_airport['lat'],
                from_airport['lon'],
                to_airport['lat'],
                to_airport['lon']
            )

            # 使用 FlyClaw 获取真实航班信息
            flights = self.get_real_flights(from_iata, to_iata, date)

            # 返回完整响应（只返回真实数据，如果没有则返回空航班列表）
            response = {
                'from': {
                    'iata': from_iata,
                    'name': from_airport['name'],
                    'city': from_airport['city']
                },
                'to': {
                    'iata': to_iata,
                    'name': to_airport['name'],
                    'city': to_airport['city']
                },
                'date': date,
                'distance_km': round(distance, 1),
                'flights': flights,
                'currency': 'CNY'
            }

            print("%s | %s->%s | %.1fkm | %d flights" % (date, from_iata, to_iata, distance, len(flights)))
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode())
            return

        # 其他路径
        response = {'error': 'Endpoint not found'}
        self.wfile.write(json.dumps(response).encode())

    def get_real_flights(self, from_iata, to_iata, date):
        """使用 FlyClaw 获取真实航班信息"""
        try:
            import argparse
            
            # 创建模拟的 args 对象
            class Args:
                from_station = from_iata
                to_station = to_iata
                date = date if date else "today"
                stops = "0"
                cabin = "economy"
                sort = None
                limit = None
                return_date = None
                adults = 1
                children = 0
                infants = 0
                show_codeshare = False
                layover_max_hours = None
                timeout = 30
                return_time = None
                verbose = False

            args = Args()
            
            # 获取配置
            conf = cfg.get_config()
            
            # 解析机场代码
            filter_inactive = conf["query"].get("filter_inactive_airports", True)
            origins = airport_manager.resolve_all(args.from_station, filter_inactive=filter_inactive)
            dests = airport_manager.resolve_all(args.to_station, filter_inactive=filter_inactive)
            
            if not origins or not dests:
                return []

            # 构建查询任务
            from flyclaw import _query_fr24_route, _query_sk_route, _query_fliggy_route, _execute_concurrent_queries, _iata_to_city_cn
            
            tasks = []
            sources_cfg = conf["sources"]
            
            # FR24
            if sources_cfg["fr24"]["enabled"]:
                timeout = sources_cfg["fr24"]["timeout"]
                tasks.append(("FR24", _query_fr24_route, (origins[0], dests[0], args.date, timeout)))
            
            # Skiplagged
            sk_cfg = sources_cfg.get("skiplagged", {})
            if sk_cfg.get("enabled", False) and args.date:
                sk_timeout = sk_cfg["timeout"]
                import functools
                for o in origins:
                    for d in dests:
                        pair_task = functools.partial(
                            _query_sk_route, o, d, args.date, sk_timeout,
                            stops=0, cabin=args.cabin
                        )
                        label = f"Skiplagged-{o}→{d}"
                        tasks.append((label, lambda t=pair_task: t(), ()))
            
            # Fliggy MCP (主要数据源)
            fg_cfg = sources_cfg.get("fliggy_mcp", {})
            if fg_cfg.get("enabled", False) and args.date:
                import functools
                fg_origin = _iata_to_city_cn(origins[0])
                fg_dest = _iata_to_city_cn(dests[0])
                fg_timeout = fg_cfg.get("timeout", 10)
                fg_task = functools.partial(
                    _query_fliggy_route,
                    fg_origin, fg_dest, args.date, fg_timeout,
                    cabin=args.cabin, stops=0,
                    api_key=fg_cfg.get("api_key", ""),
                    sign_secret=fg_cfg.get("sign_secret", ""),
                )
                tasks.append(("Fliggy", lambda t=fg_task: t(), ()))
            
            # 执行查询
            if tasks:
                ss_cfg = conf["query"].get("sufficient_source", "")
                sufficient = [ss_cfg] if ss_cfg else None
                results = _execute_concurrent_queries(tasks, 30, 10, sufficient_sources=sufficient)
                
                # 合并结果
                merged = _merge_records(results)
                merged = _deduplicate_codeshares(merged)
                
                # 转换为统一格式
                flights = []
                for rec in merged:
                    # 只保留有价格的航班
                    if rec.get("price") is None or rec.get("price") == 0:
                        continue
                    
                    flight = {
                        'flight_number': rec.get("flight_number", ""),
                        'airline': rec.get("airline", rec.get("airline_name", "")),
                        'airline_code': rec.get("airline_code", ""),
                        'aircraft': rec.get("aircraft", rec.get("aircraft_type", "")),
                        'departure_time': self.format_time(rec.get("scheduled_departure", "")),
                        'arrival_time': self.format_time(rec.get("scheduled_arrival", "")),
                        'duration_minutes': rec.get("duration_minutes", 0),
                        'price': round(float(rec.get("price", 0)), 0),
                        'source': rec.get("source", "")
                    }
                    flights.append(flight)
                
                # 按价格排序
                flights.sort(key=lambda f: f['price'])
                return flights[:5]  # 返回前5个最低价格的航班
        
        except Exception as e:
            print(f"FlyClaw query failed: {e}", flush=True)
        
        return []

    def format_time(self, iso_str):
        """格式化时间字符串"""
        if not iso_str:
            return ""
        # 提取时间部分
        if 'T' in iso_str:
            time_part = iso_str.split('T')[1]
            return time_part[:5]  # 返回 HH:MM
        return iso_str[:5]

    def log_message(self, format, *args):
        pass

def run_server(port=8081):
    """启动服务"""
    server_address = ('', port)
    httpd = HTTPServer(server_address, PriceHandler)
    print("Starting FlyClaw Price Service...")
    print("Server address: http://localhost:%d" % port)
    print("API endpoint: /price?from={origin}&to={dest}&date={date}")
    print("Supported airports: " + ", ".join(sorted(AIRPORTS.keys())))
    print("-" * 60)
    httpd.serve_forever()

if __name__ == '__main__':
    run_server()