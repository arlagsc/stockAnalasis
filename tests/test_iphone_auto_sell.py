# -*- coding: utf-8 -*-
"""Playwright iPhone 视口下验证 AI 智能巡检平仓交互与报告抽屉"""

import asyncio
from playwright.async_api import async_playwright

async def run_iphone_auto_sell_test():
    async with async_playwright() as p:
        iphone = p.devices['iPhone 14 Pro']
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            **iphone,
            locale='zh-CN',
        )
        page = await context.new_page()

        # 访问移动端
        await page.goto("http://127.0.0.1:8000")
        await page.wait_for_timeout(1000)

        # 点击底部导航中的“虚拟操盘”
        await page.click("div.nav-item[data-tab='tab-trade']")
        await page.wait_for_selector("#tab-trade.active", timeout=10000)
        await page.wait_for_timeout(1000)

        # 切换为 AI 智能操盘模式
        await page.click("#pill-ai")
        await page.wait_for_timeout(1000)

        # 截图 1: 展示 AI 模式下包含【🤖 AI 一键建仓】与【🛡️ AI 巡检平仓】操作栏
        screenshot_path1 = "C:/Users/Administrator/.gemini/antigravity-ide/brain/5e5def10-41bd-4e75-af5e-5503515c3964/iphone_trading_ai_autosell_btn.png"
        await page.screenshot(path=screenshot_path1)
        print("Captured screenshot 1:", screenshot_path1)

        # 点击【🛡️ AI 巡检平仓】按钮
        await page.click(".btn-ai-autosell")
        # 等待弹窗抽屉弹出
        await page.wait_for_selector("#auto-sell-modal.active", timeout=15000)
        await page.wait_for_timeout(1500)

        # 截图 2: 展示 AI 持仓智能巡检报告抽屉
        screenshot_path2 = "C:/Users/Administrator/.gemini/antigravity-ide/brain/5e5def10-41bd-4e75-af5e-5503515c3964/iphone_trading_ai_autosell_modal.png"
        await page.screenshot(path=screenshot_path2)
        print("Captured screenshot 2:", screenshot_path2)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_iphone_auto_sell_test())
