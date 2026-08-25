import json
import re
from playwright.sync_api import sync_playwright


URL = "https://www.planetcinema.co.il/cinemas/Rishon_Letziyon/1072"


def dismiss_cookies(page):
    for text in [
        "דחה את כל העוגיות",
        "קבל את כל העוגיות",
    ]:
        try:
            button = page.get_by_text(text, exact=False)
            if button.count() and button.first.is_visible():
                button.first.click(timeout=3000)
                page.wait_for_timeout(700)
                return
        except Exception:
            pass


def get_date(page):
    text = page.locator("body").inner_text()

    match = re.search(
        r"(?:ראשון|שני|שלישי|רביעי|חמישי|שישי|שבת)"
        r"\s+\d{1,2}/\d{1,2}/\d{4}",
        text,
    )

    return match.group(0) if match else "UNKNOWN"


def inspect_odyssey(page):
    title = page.get_by_text("האודיסאה", exact=True)

    if title.count() == 0:
        print("Odyssey not found on this day.")
        return

    target = None

    for i in range(title.count()):
        try:
            if title.nth(i).is_visible():
                target = title.nth(i)
                break
        except Exception:
            continue

    if target is None:
        print("No visible Odyssey title.")
        return

    data = target.evaluate(
        """
        (el) => {
            let root = el;

            // Find the smallest useful movie container.
            for (let i = 0; i < 12 && root; i++) {
                const text = (root.innerText || "").trim();

                if (
                    text.includes("האודיסאה") &&
                    text.toUpperCase().includes("IMAX") &&
                    text.length < 5000
                ) {
                    break;
                }

                root = root.parentElement;
            }

            if (!root) {
                return null;
            }

            const timeRegex = /^([01]?\\d|2[0-3]):[0-5]\\d$/;

            const candidates = Array.from(
                root.querySelectorAll("*")
            ).filter(node => {
                const text = (
                    node.innerText ||
                    node.textContent ||
                    ""
                ).trim();

                return timeRegex.test(text);
            });

            const results = [];

            for (const node of candidates) {
                const time = (
                    node.innerText ||
                    node.textContent ||
                    ""
                ).trim();

                let clickable = node;

                for (let level = 0; level < 8; level++) {
                    if (!clickable) break;

                    const tag = clickable.tagName;

                    if (
                        tag === "A" ||
                        tag === "BUTTON" ||
                        clickable.getAttribute("role") === "button" ||
                        clickable.hasAttribute("onclick") ||
                        clickable.hasAttribute("href")
                    ) {
                        break;
                    }

                    clickable = clickable.parentElement;
                }

                if (!clickable) {
                    clickable = node;
                }

                const attrs = {};

                for (const attr of clickable.attributes || []) {
                    attrs[attr.name] = attr.value;
                }

                let parent = clickable;
                let context = "";

                for (let level = 0; level < 5 && parent; level++) {
                    const t = (parent.innerText || "").trim();

                    if (
                        t.toUpperCase().includes("IMAX") &&
                        t.length < 1200
                    ) {
                        context = t;
                        break;
                    }

                    parent = parent.parentElement;
                }

                results.push({
                    time: time,
                    tag: clickable.tagName,
                    href: clickable.href || null,
                    attributes: attrs,
                    context: context.substring(0, 1000),
                    html: clickable.outerHTML.substring(0, 4000),
                });
            }

            return {
                root_text: (root.innerText || "").substring(0, 5000),
                results: results
            };
        }
        """
    )

    print("\n===== ODYSSEY LINK DEBUG =====")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print("===== END LINK DEBUG =====\n")


def click_day(page, label):
    try:
        matches = page.get_by_text(label, exact=True)

        for i in range(matches.count()):
            item = matches.nth(i)

            try:
                if not item.is_visible():
                    continue

                box = item.bounding_box()

                if box and box["y"] < 1000:
                    item.click(timeout=5000)
                    page.wait_for_timeout(2500)
                    return True
            except Exception:
                continue

    except Exception:
        pass

    return False


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        page = browser.new_page(
            viewport={"width": 1440, "height": 1200},
            locale="he-IL",
        )

        page.goto(
            URL,
            wait_until="domcontentloaded",
            timeout=90000,
        )

        page.wait_for_timeout(6000)
        dismiss_cookies(page)

        labels = [
            "היום",
            "א׳",
            "ב׳",
            "ג׳",
            "ד׳",
            "ה׳",
            "ו׳",
            "ש׳",
        ]

        seen = set()

        # Current day
        date = get_date(page)
        seen.add(date)

        print(f"\n######## {date} ########")
        inspect_odyssey(page)

        # Other days
        for label in labels:
            if not click_day(page, label):
                continue

            date = get_date(page)

            if date in seen:
                continue

            seen.add(date)

            print(f"\n######## {date} ########")
            inspect_odyssey(page)

        browser.close()


if __name__ == "__main__":
    main()
