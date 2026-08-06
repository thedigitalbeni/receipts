const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const artifactDir = '/home/beneyas/.gemini/antigravity/brain/8f79aef0-2f72-4cd3-8a49-e6b068ecd680/';

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: '/usr/bin/google-chrome' });
  const page = await browser.newPage();
  await page.setViewportSize({ width: 430, height: 932 });
  
  console.log('Testing Success State and Download...');
  await page.goto('http://localhost:3000');
  
  // Create a mock successful response
  await page.route('**/verify', async route => {
    await new Promise(resolve => setTimeout(resolve, 2000));
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: "cf4ede2f-ea3f-41a6-bb28-7238c3530e0d", // using known ID
        classification: "Recirculated / Out of Context",
        evidence_strength: "Strong",
        evidence: ["Original context found (2018)", "Different location"],
        interpretation: "Image is old.",
        processing_time_ms: 500,
        receipt_image_url: "http://localhost:3000/api/receipt/cf4ede2f-ea3f-41a6-bb28-7238c3530e0d",
        cached: false
      })
    });
  });

  const dummyFile = path.resolve('/tmp/dummy.jpg');
  fs.writeFileSync(dummyFile, 'dummy data');
  await page.setInputFiles('input[type="file"]', dummyFile);
  
  // Wait for the success state (img to load)
  await page.waitForSelector('img#receipt-image');
  await page.waitForTimeout(1000); // Wait for transition
  await page.screenshot({ path: path.join(artifactDir, 'success.png') });
  console.log('Saved success.png');
  
  // Test desktop download
  console.log('Testing share/download fallback...');
  const [download] = await Promise.all([
    page.waitForEvent('download', { timeout: 10000 }),
    page.click('button#share-btn')
  ]);
  
  const downloadPath = await download.path();
  console.log(`Download triggered successfully. Temp file: ${downloadPath}`);
  console.log(`Suggested filename: ${download.suggestedFilename()}`);
  
  await browser.close();
})();
