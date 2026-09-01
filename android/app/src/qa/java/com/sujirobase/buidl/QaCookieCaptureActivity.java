package com.sujirobase.buidl;

/** Offline fixture compiled ONLY into the separate com.sujirobase.buidl.qa app. */
public class QaCookieCaptureActivity extends CookieCaptureActivity {
    @Override protected void openSite() {
        browser.getSettings().setBlockNetworkLoads(true);
        browser.loadDataWithBaseURL(START_URL,
                "<html><body><h2>BUIDL QA</h2><p>Offline synthetic login fixture</p></body></html>",
                "text/html","UTF-8",START_URL);
    }
}
