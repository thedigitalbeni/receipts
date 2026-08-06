const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const artifactDir = '/home/beneyas/.gemini/antigravity/brain/8f79aef0-2f72-4cd3-8a49-e6b068ecd680/';

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: '/usr/bin/google-chrome' });
  const page = await browser.newPage();
  
  // Set viewport to a mobile-ish size to look like an Instagram Story
  await page.setViewportSize({ width: 430, height: 932 });
  
  console.log('Testing Dropzone State...');
  await page.goto('http://localhost:3000');
  await page.waitForTimeout(2000); // wait for ambient glows to load
  await page.screenshot({ path: path.join(artifactDir, 'dropzone.png') });
  console.log('Saved dropzone.png');
  
  console.log('Testing timeout/Analysis State...');
  // Intercept the /verify route to delay indefinitely
  await page.route('**/verify', async route => {
    // Keep it hanging to trigger the frontend timeout
    // Wait for 65 seconds
    await new Promise(resolve => setTimeout(resolve, 65000));
    route.abort('timedout');
  });

  // Upload an image
  const dummyFile = path.resolve('/tmp/dummy.jpg');
  fs.writeFileSync(dummyFile, 'dummy data');
  
  await page.setInputFiles('input[type="file"]', dummyFile);
  
  // Take screenshot of Analysis state shortly after upload
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(artifactDir, 'analysis.png') });
  console.log('Saved analysis.png');
  
  // Now wait for the timeout error state (60s + 1s buffer)
  console.log('Waiting for timeout (61s)...');
  await page.waitForTimeout(61000);
  await page.screenshot({ path: path.join(artifactDir, 'timeout_error.png') });
  console.log('Saved timeout_error.png');
  
  // Cleanup
  await page.unroute('**/verify');
  
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

  await page.setInputFiles('input[type="file"]', dummyFile);
  
  // Wait for the success state (img to load)
  await page.waitForSelector('img#receipt-image');
  await page.waitForTimeout(1000); // Wait for transition
  await page.screenshot({ path: path.join(artifactDir, 'success.png') });
  console.log('Saved success.png');
  
  // Test desktop download
  console.log('Testing share/download fallback...');
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.click('button#share-btn')
  ]);
  
  const downloadPath = await download.path();
  console.log(`Download triggered successfully. Temp file: ${downloadPath}`);
  console.log(`Suggested filename: ${download.suggestedFilename()}`);
  
  await browser.close();
})();
