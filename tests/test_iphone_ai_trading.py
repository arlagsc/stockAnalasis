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

        print("1. 导航至移动端首页...")
        await page.goto("http://127.0.0.1:8000/", wait_until="networkidle")
        await asyncio.sleep(1.5)

        # 切换至虚拟操盘 Tab
        print("2. 切换至 [虚拟操盘] Tab...")
        await page.click('.nav-item[data-tab="tab-trade"]')
        await asyncio.sleep(2)

        # 截图 1: 人类主观操盘默认视图 (含 PK 战报与军规)
        shot1 = ARTIFACTS_DIR / "iphone_trading_manual_pk.png"
        await page.screenshot(path=str(shot1))
        print(f"人类操盘与 PK 战报已保存: {shot1}")

        # 切换至 AI 智能操盘
        print("3. 点击切换至 [AI 智能操盘] 模式...")
        await page.click('#btn-acc-ai')
        await asyncio.sleep(2)

        # 截图 2: AI 智能操盘视图 (AI 紫色资产、AI 持仓与军规库)
        shot2 = ARTIFACTS_DIR / "iphone_trading_ai_mode.png"
        await page.screenshot(path=str(shot2))
        print(f"AI 操盘视图已保存: {shot2}")

        # 触发 AI 一键自动建仓
        print("4. 点击 [AI 一键全自动计算建仓]...")
        await page.click('.btn-ai-autotrade')
        await asyncio.sleep(3)

        # 截图 3: AI 自动建仓决策报告弹窗
        shot3 = ARTIFACTS_DIR / "iphone_trading_ai_autotrade_modal.png"
        await page.screenshot(path=str(shot3))
        print(f"AI 决策报告已保存: {shot3}")

        await browser.close()
        print("全部实机视口截图捕获完毕！")

if __name__ == "__main__":
    asyncio.run(run())
