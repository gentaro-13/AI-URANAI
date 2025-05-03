# engine.py  —  天体位置計算ユーティリティ
import sys, json, datetime, pytz, ephem, os, math
from skyfield.api import load, wgs84
from skyfield.almanac import find_discrete, sunrise_sunset

def is_valid_date(date_str):
    try:
        # 日付形式を統一
        date_str = date_str.replace('/', '-')
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False

def get_chart(date_str, time_str, timezone_str):
    try:
        # 日付をISO形式に変換
        date_iso = date_str.replace('/', '-')
        dt = datetime.strptime(f"{date_iso}T{time_str}", '%Y-%m-%dT%H:%M')
        
        # タイムゾーンを設定
        tz = pytz.timezone(timezone_str)
        dt = tz.localize(dt)
        
        # 観測者の位置を設定（東京）
        tokyo = wgs84.latlon(35.6895, 139.6917)
        
        # 太陽の位置を計算
        ts = load.timescale()
        t = ts.from_datetime(dt)
        eph = load('de421.bsp')
        sun = eph['sun']
        earth = eph['earth']
        
        # 太陽の位置を計算
        astrometric = earth.at(t).observe(sun)
        ra, dec, distance = astrometric.radec()
        
        # 太陽の黄経を計算
        sun_lon = ra.degrees
        
        # 星座を判定
        zodiac_sign = get_zodiac_sign(sun_lon)
        
        return f"あなたの星座は {zodiac_sign} です。"
    except Exception as e:
        print(f"Error in get_chart: {str(e)}")
        return None

def get_zodiac_sign(sun_lon):
    """黄経から星座を判定"""
    # 星座の境界（黄経）
    zodiac_boundaries = [
        (0, "おひつじ座"),
        (30, "おうし座"),
        (60, "ふたご座"),
        (90, "かに座"),
        (120, "しし座"),
        (150, "おとめ座"),
        (180, "てんびん座"),
        (210, "さそり座"),
        (240, "いて座"),
        (270, "やぎ座"),
        (300, "みずがめ座"),
        (330, "うお座")
    ]
    
    # 星座を判定
    for boundary, sign in zodiac_boundaries:
        if sun_lon < boundary:
            return sign
    return "おひつじ座"

if __name__ == "__main__":
    d, t, z = sys.argv[1:4]
    print(json.dumps(get_chart(d, t, z), ensure_ascii=False, indent=2))

