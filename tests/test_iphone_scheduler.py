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

        # 监听 dialog 自动点击确定
        page.on("dialog", lambda dialog: asyncio.create_task(dialog.accept()))

        print("1. 导航至移动端首页...")
        await page.goto("http://127.0.0.1:8000/", wait_until="networkidle")
        await asyncio.sleep(1)

        # 切换至虚拟操盘 Tab
        print("2. 切换至 [虚拟操盘] Tab...")
        await page.click('.nav-item[data-tab="tab-trade"]')
        await asyncio.sleep(1.5)

        # 切换至 AI 智能操盘
        print("3. 切换至 [AI 智能操盘] 模式...")
        await page.click('#btn-acc-ai')
        await asyncio.sleep(1.5)

        # 截图 1: 待机就绪状态下的无人操盘卡片与急停断电按钮
        shot1 = ARTIFACTS_DIR / "iphone_scheduler_standby.png"
        await page.screenshot(path=str(shot1))
        print(f"待机状态截图已保存: {shot1}")

        # 4. 点击【开启托管】
        print("4. 点击【开启托管】按钮...")
        await page.click('#btn-scheduler-toggle')
        await asyncio.sleep(2)

        # 截图 2: 激活无人托管运行中状态
        shot2 = ARTIFACTS_DIR / "iphone_scheduler_running.png"
        await page.screenshot(path=str(shot2))
        print(f"运行中状态截图已保存: {shot2}")

        # 5. 点击【急停】
        print("5. 点击【急停】按钮...")
        await page.click('#btn-kill-switch')
        await asyncio.sleep(2)

        # 截图 3: 全局紧急急停断电状态
        shot3 = ARTIFACTS_DIR / "iphone_scheduler_emergency.png"
        await page.screenshot(path=str(shot3))
        print(f"急停熔断状态截图已保存: {shot3}")

        # 6. 解除急停
        print("6. 点击【解除急停】...")
        await page.click('#btn-scheduler-toggle')
        await asyncio.sleep(2)

        await browser.close()
        print("实机视口截图自动化巡检捕获完毕！")


if __name__ == "__main__":
    asyncio.run(run())
