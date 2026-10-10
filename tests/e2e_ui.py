"""End-to-end click-through of the whole app in a real browser. Not part of pytest.

    pip install playwright && playwright install chromium
    python -m pitwall.server --port 8000 --no-browser      # in another terminal
    python tests/e2e_ui.py [http://127.0.0.1:8000] [outdir]

Clicks every control on all three screens at two screen sizes, waits for each race to load,
and fails if the browser reports any error. Screenshots go to outdir (default e2e_shots/).
"""
import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e_shots")
EXE = {"executable_path": sys.argv[3]} if len(sys.argv) > 3 else {}
checks: list[str] = []


async def wait_race(pg, timeout=60000):
    await pg.wait_for_selector(".lap-big", timeout=timeout)
    await pg.wait_for_function("!document.querySelector('.new-race')?.disabled", timeout=timeout)


async def run(size):
    W, H = size
    errors = []
    async with async_playwright() as p:
        b = await p.chromium.launch(**EXE)
        pg = await b.new_page(viewport={"width": W, "height": H})
        pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        pg.on("console", lambda m: errors.append(f"console: {m.text[:160]}") if m.type == "error" and "404" not in m.text else None)
        shot = lambda name: pg.screenshot(path=str(OUT / f"{W}_{name}.png"))  # noqa: E731

        # ---- Live race
        await pg.goto(URL)
        await wait_race(pg)
        pills = pg.locator(".scenarios .pill:not(.custom)")
        for k in range(await pills.count()):
            await pills.nth(k).click()
            await wait_race(pg)
            await pg.locator(".scrub input").fill("25")
            await pg.wait_for_timeout(400)
            await shot(f"live_demo{k}")
            checks.append(f"{W}: demo race {k} loads and scrubs")
        # the multiverse, opened by hand
        btn = pg.locator("button.linkish", has_text="See the futures")
        for lap in range(2, 40):
            await pg.locator(".scrub input").fill(str(lap))
            await pg.wait_for_timeout(120)
            if await btn.count():
                await btn.first.click()
                await pg.wait_for_selector(".mv", timeout=5000)
                await pg.wait_for_timeout(1500)
                await shot("multiverse")
                await pg.locator(".mv .btn", has_text="Continue").click()
                checks.append(f"{W}: multiverse opens at lap {lap} and closes")
                break
        # custom race: every rules / weather / safety-car option
        await pg.locator(".pill.custom").click()
        for label in ("Endurance", "Wet race", "Lots", "F1", "Dry", "None", "Usual"):
            await pg.locator(".setup .seg2 button", has_text=label).first.click()
            await wait_race(pg)
            checks.append(f"{W}: custom '{label}' loads")
        await pg.locator(".setup .seg2 button", has_text="Endurance").first.click()
        await wait_race(pg)
        await pg.locator(".scrub input").fill("30")
        await pg.wait_for_timeout(500)
        await shot("live_endurance")
        assert await pg.locator(".fuel-bar").count() == 4, "fuel gauges missing in endurance"
        checks.append(f"{W}: endurance shows 4 fuel gauges")
        await pg.locator(".setup .seg2 button", has_text="F1").first.click()
        await wait_race(pg)
        # race number box and new random race
        await pg.locator(".race-no input").fill("4242")
        await pg.locator(".race-no input").press("Enter")
        await wait_race(pg)
        assert "4242" in await pg.locator(".race-sub").inner_text()
        await pg.locator(".new-race").click()
        await wait_race(pg)
        checks.append(f"{W}: race number and new random race")
        # weather / safety-car buttons mid-race, then Dry; each kind can be used once per race
        await pg.locator(".scrub input").fill("15")
        force = lambda label: pg.locator(".force").get_by_role("button", name=label, exact=True)  # noqa: E731
        for label in ("Heavy rain", "Dry", "Safety car", "Rain"):
            if await force(label).is_enabled():
                await force(label).click()
                await wait_race(pg)
                checks.append(f"{W}: '{label}' now works")
            await pg.locator(".mv .btn").click() if await pg.locator(".mv").count() else None
        for label in ("Rain", "Heavy rain", "Dry", "Safety car"):
            assert not await force(label).is_enabled(), f"'{label}' can be pressed twice"
        checks.append(f"{W}: each forced event only once per race")
        await shot("live_forced")
        # a car that runs out of fuel: Monza, endurance, wet, lots of safety cars, race 13
        await pg.locator(".setup select").select_option("monza")
        await wait_race(pg)
        for label in ("Endurance", "Wet race", "Lots"):
            await pg.locator(".setup .seg2 button", has_text=label).first.click()
            await wait_race(pg)
        await pg.locator(".race-no input").fill("13")
        await pg.locator(".race-no input").press("Enter")
        await wait_race(pg)
        await pg.locator(".scrub input").fill("35")
        await pg.wait_for_timeout(500)
        assert "out of fuel" in (await pg.locator(".stage").inner_text()).lower(), "out-of-fuel car not shown"
        await shot("live_out_of_fuel")
        await pg.locator(".scrub input").fill("53")
        await pg.wait_for_timeout(500)
        verdict = await pg.locator(".verdict2").inner_text()
        assert "ran out of fuel" in verdict.lower(), f"{verdict!r} / {await pg.locator('.race-sub').inner_text()!r}"
        checks.append(f"{W}: a car that runs out of fuel is shown as out, verdict says so")
        # switching race mid-play never leaves the futures view open
        await pg.locator(".scrub input").fill("2")
        await pg.locator(".timeline .btn").first.click()
        await pg.wait_for_timeout(300)
        await pg.locator(".scenarios .pill:not(.custom)").first.click()
        await wait_race(pg)
        await pg.wait_for_timeout(300)
        assert await pg.locator(".mv").count() == 0, "futures view left open after switching race"
        await pg.wait_for_timeout(4500)          # start lights
        if await pg.locator(".mv").count():
            await pg.locator(".mv .btn", has_text="Continue").click()
        await pg.locator(".scrub input").fill("1")   # seeking pauses
        checks.append(f"{W}: switching race mid-play closes everything cleanly")
        # speeds and play/pause
        for s in ("1 s/lap", "5 s/lap", "2 s/lap"):
            await pg.locator(".timeline .seg2 button", has_text=s).click()
        await pg.locator(".timeline .btn").first.click()
        await pg.wait_for_timeout(1500)
        await pg.locator(".timeline .btn").first.click()
        checks.append(f"{W}: speeds and play/pause")

        # ---- Proof
        await pg.locator(".tab", has_text="Proof").click()
        await pg.wait_for_selector(".board-tile")
        tiles = pg.locator(".board-tile")
        for k in range(await tiles.count()):
            await tiles.nth(k).click()
            await pg.wait_for_timeout(700)
        await shot("proof")
        await pg.locator(".proof .seg2 button", has_text="Endurance").click()
        await pg.wait_for_timeout(1000)
        await shot("proof_endurance")
        checks.append(f"{W}: proof, every track and both rule sets")

        # ---- Real races
        await pg.locator(".tab", has_text="Real races").click()
        for race_name in ("Bahrain 2023", "Monza 2023", "Singapore 2023"):
            await pg.locator(".real-pick .seg2 button", has_text=race_name).click()
            await pg.wait_for_selector(".tower2", timeout=60000)
            drivers = pg.locator(".real-pick .seg2").nth(1).locator("button")
            for k in range(min(3, await drivers.count())):
                await drivers.nth(k).click()
                await pg.wait_for_selector(".tower2 li", timeout=60000)
                await pg.wait_for_timeout(300)
            # click fast through every driver, then check the screen shows the one picked last
            n = await drivers.count()
            for k in range(n):
                await drivers.nth(k).click()
            code = (await drivers.nth(n - 1).inner_text()).split()[0]
            await pg.wait_for_function(f"document.querySelector('.vtile-label')?.textContent.includes('{code}')", timeout=60000)
            await pg.wait_for_timeout(1500)
            assert code in await pg.locator(".vtile-label").first.inner_text(), f"stale replay shown for {code}"
            checks.append(f"{W}: replay {race_name}, every driver, fast clicks show the right one")
        await shot("real_grid")
        await pg.locator(".timeline .btn.primary").click()   # lights out
        await pg.wait_for_timeout(5000)
        await shot("real_running")
        await pg.locator(".scrub input").fill("30")
        await pg.wait_for_timeout(500)
        await shot("real_lap30")
        skip = pg.locator("button.linkish", has_text="Skip to the flag")
        if await skip.count():
            await skip.click()
            await pg.wait_for_timeout(500)
        await shot("real_flag")
        checks.append(f"{W}: lights out, scrub, skip to the flag")
        await b.close()
    return errors


async def main():
    OUT.mkdir(exist_ok=True)
    all_errors = []
    for size in ((1920, 1080), (1366, 768)):
        all_errors += await run(size)
    print("\n".join(f"ok  {c}" for c in checks))
    if all_errors:
        print("\nBROWSER ERRORS:\n" + "\n".join(all_errors))
        sys.exit(1)
    print(f"\nall {len(checks)} checks passed, no browser errors")


if __name__ == "__main__":
    asyncio.run(main())
