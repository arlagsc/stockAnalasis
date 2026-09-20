import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

ARTIFACTS_DIR = Path(r"C:\Users\Administrator\.gemini\antigravity-ide\brain\5e5def10-41bd-4e75-af5e-5503515c3964")

async def run():
    async with async_playwright() as p:
        iphone = p.devices['iPhone 14 Pro']
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            **iphone,
            locale='zh-CN',
            timezone_id='Asia/Shanghai',
        )
        page = await context.new_page()

        print("1. 导航至移动端 PWA 首页...")
        await page.goto("http://127.0.0.1:8000/", wait_until="networkidle")
        await asyncio.sleep(2)

        # 截图 1: 全景大盘与今日涨幅榜
        shot1 = ARTIFACTS_DIR / "iphone_pwa_market_rankings.png"
        await page.screenshot(path=str(shot1))
        print(f"全景大盘截图已保存: {shot1}")

        # 2. 点击切换到 [成交额榜]
        print("2. 切换排行榜药丸至 [成交额榜]...")
        await page.click('button[data-category="volume"]')
        await asyncio.sleep(1.5)
        shot2 = ARTIFACTS_DIR / "iphone_pwa_volume_rankings.png"
        await page.screenshot(path=str(shot2))
        print(f"成交额榜截图已保存: {shot2}")

        # 3. 在顶部搜索框输入拼音简拼 PAYH
        print("3. 在搜索框键入 PAYH 测试首字母模糊查询...")
        await page.fill("#global-search-input", "PAYH")
        await asyncio.sleep(1.5)
        shot3 = ARTIFACTS_DIR / "iphone_pwa_pinyin_search_payh.png"
        await page.screenshot(path=str(shot3))
        print(f"拼音首字母联想浮层截图已保存: {shot3}")

        # 4. 点击联想项跳转到 [个股研判]
        print("4. 点击联想项跳转到个股研判...")
        await page.click(".search-item")
        await asyncio.sleep(2)
        shot4 = ARTIFACTS_DIR / "iphone_pwa_detail_jump.png"
        await page.screenshot(path=str(shot4))
        print(f"研判跳转截图已保存: {shot4}")

        # 5. 点击底部第 2 个 Tab [我的自选]
        print("5. 切换到 [我的自选] Tab...")
        await page.click('.nav-item[data-tab="tab-watchlist"]')
        await asyncio.sleep(1.5)
        shot5 = ARTIFACTS_DIR / "iphone_pwa_watchlist_tab.png"
        await page.screenshot(path=str(shot5))
        print(f"自选池截图已保存: {shot5}")

        await browser.close()
        print("所有 iPhone 实机视口测试截图捕获完毕！")

if __name__ == "__main__":
    asyncio.run(run())
