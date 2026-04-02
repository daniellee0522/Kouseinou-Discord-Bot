import urllib.request as req
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import config


def deal_earthquake(url, m=0):
    alt = []    # 防止重複地震
    time = []
    max_level = []
    img = []
    lat = []
    lon = []
    loc = []
    mag = []
    depth = []
    with open(config.MD5_JSON_PATH, "r") as f:
        current = json.load(f)
    current_num = current[m]

    request = req.Request(url, headers={
        "cookie": "over18=1",
        "user-agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Mobile Safari/537.36"
    })
    with req.urlopen(request) as response:
        data = json.loads(response.read().decode('utf8'))[
            "records"]["Earthquake"]

    # 地震編號
    Num = [item["EarthquakeNo"] for item in data]
    for i, item in enumerate(Num):
        if item in current_num or item in alt:
            pass
        else:
            alt.append(item)
            time.append(data[i]["EarthquakeInfo"]["OriginTime"])
            max_level.append(data[i]["ReportContent"][-3:-1])
            img.append(data[i]["ReportImageURI"])
            lat.append(data[i]["EarthquakeInfo"]
                       ["Epicenter"]["EpicenterLatitude"])
            lon.append(data[i]["EarthquakeInfo"]
                       ["Epicenter"]["EpicenterLongitude"])
            loc.append(data[i]["EarthquakeInfo"]["Epicenter"]["Location"])
            mag.append(data[i]["EarthquakeInfo"]
                       ["EarthquakeMagnitude"]["MagnitudeValue"])
            depth.append(data[i]["EarthquakeInfo"]["FocalDepth"])

    output = [
        {'time': time, 'max_level': max_level, 'img': img, 'lat': lat,
            'lon': lon, 'loc': loc, 'mag': mag, 'depth': depth}
        for time, max_level, img, lat, lon, loc, mag, depth in zip(time, max_level, img, lat, lon, loc, mag, depth)
    ]

    current[m] = Num

    with open(config.MD5_JSON_PATH, 'w', encoding='utf8') as f:
        json.dump(current, f,
                  ensure_ascii=False, indent=4)

    return output


if __name__ == "__main__":
    print(deal_earthquake(f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/E-A0016-001?Authorization={config.CWA_API_TOKEN}&limit=20&format=JSON", m=1))
