import { expect, test } from "@playwright/test";

test("home page shows Commander Sky", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Commander Sky/ })).toBeVisible();
});

test("session page offers the start button and fails friendly without config", async ({
  page,
}) => {
  // Dev server runs without LiveKit credentials — the token API returns 500 and
  // the kid must see a friendly message, never a raw error.
  await page.goto("/session");
  const start = page.getByTestId("start-session");
  await expect(start).toBeVisible();
  await start.click();
  await expect(page.getByTestId("session-error")).toContainText("mission control");
});

test("parent gate requires hold then math", async ({ page }) => {
  await page.goto("/parent");

  // Settings must not be visible up front.
  await expect(page.getByRole("heading", { name: "Parent settings" })).toHaveCount(0);

  // A short tap must NOT pass the gate.
  const hold = page.getByTestId("hold-button");
  await hold.dispatchEvent("pointerdown");
  await page.waitForTimeout(300);
  await hold.dispatchEvent("pointerup");
  await expect(page.getByTestId("math-question")).toHaveCount(0);

  // A full 3-second hold advances to the math step.
  await hold.dispatchEvent("pointerdown");
  await page.waitForTimeout(3300);
  await expect(page.getByTestId("math-question")).toBeVisible();

  // Wrong answer is rejected.
  await page.getByTestId("math-answer").fill("1");
  await page.getByTestId("math-submit").click();
  await expect(page.getByText("Not quite")).toBeVisible();

  // Correct answer opens settings.
  const question = await page.getByTestId("math-question").innerText();
  const [, a, b] = question.match(/What is (\d+) \+ (\d+)\?/) ?? [];
  await page.getByTestId("math-answer").fill(String(Number(a) + Number(b)));
  await page.getByTestId("math-submit").click();
  await expect(page.getByRole("heading", { name: "Parent settings" })).toBeVisible();
});
