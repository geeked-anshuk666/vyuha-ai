import { chromium, test, expect } from '@playwright/test';
import * as path from 'path';

/**
 * Run this via: npx playwright test record_pitch.ts --headed
 * It will capture the demo flow perfectly for the hackathon pitch!
 */
test('Cinematic Vyuha AI Demo Sequence', async () => {
  // Launch browser and record video to output/ folder
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({
    recordVideo: {
      dir: path.join(__dirname, 'output'),
      size: { width: 1920, height: 1080 }
    },
    viewport: { width: 1920, height: 1080 }
  });
  
  const page = await context.newPage();

  console.log("🎬 STARTING SCENE: Opening Mission Control...");
  await page.goto('http://localhost:3000');
  
  // Close the Walkthrough overlay to see the pure dashboard
  await page.waitForTimeout(2000);
  const closeWalkthroughBtn = page.locator('button:has(.lucide-x)'); // The X icon
  if (await closeWalkthroughBtn.isVisible()) {
    await closeWalkthroughBtn.click();
  }
  
  console.log("⏱️ HOLD: Showing steady state traffic (50 req/sec)...");
  await page.waitForTimeout(5000);

  console.log("🔥 INJECTING CHAOS: Dead Node-B...");
  // Click Node-B Hard Kill button
  const nodeBKillBtn = page.locator('button:has-text("HARD KILL (DEAD)")').nth(1);
  await nodeBKillBtn.click();

  console.log("⏱️ HOLD: Watching the graph drop and waiting for AI Triage...");
  // Wait for the proposal card to appear
  await page.waitForTimeout(6000);

  console.log("🤖 AGENT REASONING: Scrolling and reading AI proposal...");
  await page.mouse.wheel(0, 400);
  await page.waitForTimeout(3000);

  console.log("✅ COMMANDING: Human Approval...");
  // Identify the feedback input and approve button
  const feedbackInput = page.locator('input[placeholder*="Add human feedback"]');
  await feedbackInput.fill("Automated Approval. Do it.");
  await page.waitForTimeout(1000);
  
  const approveBtn = page.locator('button:has-text("Approve")').first();
  await approveBtn.click();

  console.log("⏱️ HOLD: Waiting for graph healing and system recovery...");
  await page.waitForTimeout(5000);

  console.log("💬 SCENE 2: Chat Interrogation...");
  await page.mouse.wheel(0, window.innerHeight);
  
  const chatInput = page.locator('input[placeholder*="Ask why a node was disabled"]');
  await chatInput.fill("Why did you just kill Node-B?");
  await chatInput.press('Enter');
  
  console.log("⏱️ HOLD: Reading GLM-5.1 response...");
  await page.waitForTimeout(5000);

  console.log("🎬 END SCENE! Recording saved to demo_automation/output/");
  await context.close();
  await browser.close();
});
