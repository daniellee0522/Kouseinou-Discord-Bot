<img src="docs/images/logo.png" width="128" height="128" alt="Kouseinou Bot logo">

# 高性能bot (Kouseinou Bot)

[![Discord Bot Status](https://img.shields.io/badge/Verified-✓%20BOT-%235865F2?style=flat-square&logo=Discord&logoColor=FFFFFF)](https://discord.com/discovery/applications/1243841697637601310)
[![Discord Bot Install count](https://img.shields.io/badge/dynamic/json?url=https://enderdaniel.work/server_count&query=$.server_count&label=高性能bot&suffix=%20servers&color=%235865F2&logo=Discord&style=flat-square&logoColor=FFFFFF)](https://discord.com/discovery/applications/1243841697637601310)
[![Discord Bot server](https://img.shields.io/discord/1263477574785564703?label=Support%20server&style=flat-square&logo=Discord&logoColor=FFFFFF)](https://discord.gg/ERSk9sYWyP)
![License](https://img.shields.io/badge/License-MIT-orange?style=flat-square&logo=License&logoColor=FFFFFF)

A Discord bot inspired by [ermiana](https://github.com/canaria3406/ermiana), with richer link previews, anime update notifications from [動畫瘋](https://ani.gamer.com.tw), and a Blue Archive gacha simulator.

- [Add the bot](https://discord.com/discovery/applications/1243841697637601310)
- [Support server](https://discord.gg/ERSk9sYWyP) — questions, suggestions, and bug reports
- [Terms of service](docs/Terms_of_service.md) · [繁體中文服務條款](docs/Terms_of_service_zh_TW.md) · [Privacy policy](docs/Privacy_policy.md)

## Link previews

Paste a link in chat and the bot replies with a rich preview. Supported sites: Bahamut's 場外 board, Facebook, Mobile01, nhentai, wnacg, 禁漫天堂 (18comic), E-Hentai / ExHentai, hitomi, kemono / coomer, MissAV, Jable, Supjav, Hanime1, Iwara, XVideos, and Pornhub.

- Facebook previews show the post text, up to four photos, reactions, and video links.
- Mobile01 previews show the board, author, view count, and attached photos.
- Server managers can turn previews for individual sites on or off with `/解析網頁開關`.

<img src="docs/images/link-previews.png" width="560" alt="Bahamut, Facebook and Mobile01 link previews">

### Gallery reader

Gallery previews (nhentai, wnacg, 禁漫天堂, E-Hentai / ExHentai, hitomi, and multi-image kemono / coomer posts) show the author, tags, and page count, with first / previous / next / last page buttons right in the message. Right-click the message → **Apps → 跳轉頁數** to jump straight to any page.

<img src="docs/images/gallery-preview.png" width="600" alt="Gallery preview with page buttons">

### Bookmarks

Right-click a preview → **Apps → 加入書籤** and the bot DMs you the page you're on, with working page buttons. Keep reading in the DM and the bookmark follows your latest page; bookmarking the same gallery again replaces the old one.

- `/書籤 列表` lists your bookmarks, optionally filtered by site, each with its own delete button.
- `/書籤 新增` adds a bookmark from a message link.

<img src="docs/images/bookmark-dm.png" width="600" alt="Bookmark sent to your DMs">

<img src="docs/images/bookmark-list.png" width="560" alt="/書籤 列表 bookmark list">

### Lookup commands

| Command | Purpose |
| --- | --- |
| `/nhentai` | Look up a gallery by ID. |
| `/wnacg` | Look up an album by ID. |
| `/jm` | Look up a 禁漫天堂 album by ID. |
| `/ehentai` | Look up an E-Hentai / ExHentai gallery by number, link, or `gid token`. |
| `/av番號查詢` | Search by video code across MissAV, Jable, and Supjav. |
| `/missav` | Look up a video on MissAV. |
| `/jable` | Look up a video on Jable. |
| `/supjav` | Search Supjav by video code. |

## Anime update notifications

Subscribe to shows on 動畫瘋 and the bot posts in your server as soon as a new episode is up.

| Command | Purpose |
| --- | --- |
| `/新番列表` | Show this season's airing anime. |
| `/查詢新番` | Search for an anime and subscribe with one click. |
| `/訂閱` | Subscribe to an anime. |
| `/訂閱列表` | Show the server's subscriptions. |
| `/刪除訂閱` | Remove a subscription. |
| `/設定頻道` | Send notifications to the current channel. |

<img src="docs/images/anime-list.png" width="580" alt="Anime list">

<img src="docs/images/anime-search.png" width="500" alt="Anime search with subscribe button">

<img src="docs/images/anime-subscribe.png" width="420" alt="Anime subscription">

<img src="docs/images/anime-notification.png" width="560" alt="New episode notification">

## Blue Archive gacha simulator

Send `-1200` for a ten-pull, played out in a single message: envelope, Arona, result sheet, then the cards. Press **再抽十連** to pull again. Pulling the rate-up student shows their memorial lobby art.

The rate-up banner follows the Global server automatically, and the pity system follows the official recruitment rules.

- `/統計` shows your pull statistics; `/歸零` resets them.
- `/換池` picks which rate-up student is active.
- `/上鎖` and `/解鎖` let admins turn the simulator off or on in a channel.

<img src="docs/images/gacha-result.png" width="460" alt="Gacha ten-pull result">
<img src="docs/images/gacha-pu.png" width="460" alt="Rate-up student pulled">

![Gacha statistics](https://i.imgur.com/X5b6jFl.png)

## Earthquake alerts

Working with 地牛 Wake UP!, the bot posts an alert with the expected intensity and arrival time before shaking reaches you. The collaboration directory is set in 地牛 Wake UP! under `setting > others`.

<img src="docs/images/earthquake-alert.png" width="520" alt="Earthquake alert example">

![地牛 Wake UP! collaboration setting](https://i.imgur.com/z1Kxj6T.png)

## Other

- `/歡迎訊息` sets a message the bot posts when someone joins, in the channel where you run it.
- `/help` lists the available commands.
- Right-click one of the bot's messages → **Apps → 刪除訊息** to delete it.

## Contributing

Report problems or suggest features in the [support server](https://discord.gg/ERSk9sYWyP) or the repository's issues.
