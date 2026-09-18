# 各站點的品牌色（從官網實際量測的主色）跟 icon，給 embed 的 author icon / 側邊色條用。
# icon_url 不能直接指向這些網站自己的網域：missav/supjav 都有 Cloudflare 保護，
# 我們自己的爬蟲能過是因為用 FlareSolverr/真瀏覽器解盾，但 Discord 自己的伺服器渲染
# embed 時是直接拿 icon_url 去抓圖，沒有解盾能力，一碰到 Cloudflare 擋下來圖就抓不到、
# 顯示壞掉。改用 Google 的 favicon 代理服務（掛在 gstatic.com，沒有 Cloudflare 擋著）。
MISSAV = {
    "name": "MissAV",
    "icon_url": "https://www.google.com/s2/favicons?domain=missav.ai&sz=128",
    "color": 0xFE628E,
}

JABLE = {
    "name": "Jable",
    "icon_url": "https://i.meee.com.tw/E6CBtQX.jpg",
    "color": 0x0078B0,
}

SUPJAV = {
    "name": "Supjav",
    "icon_url": "https://www.google.com/s2/favicons?domain=supjav.com&sz=128",
    "color": 0xD8201D,
}
