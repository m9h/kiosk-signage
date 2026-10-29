package org.mhough.kiosk;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.KeyEvent;
import android.view.View;
import android.view.WindowManager;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/**
 * One full-screen WebView on one URL. Reloads every RELOAD_MS so new content
 * appears, retries RETRY_MS after a failed main-frame load, keeps the screen on.
 * Back is swallowed, except that EXIT_PRESSES presses within EXIT_WINDOW_MS
 * leave the kiosk (the Fire TV phone app cannot hold a key); Home leaves too.
 *
 * Change the URL without rebuilding:
 *   adb shell am start -n org.mhough.kiosk/.KioskActivity --es url https://example.org
 * and the rotation (degrees clockwise; 90 or 270 for a portrait-mounted screen):
 *   adb shell am start -n org.mhough.kiosk/.KioskActivity --ei rotation 270
 */
public class KioskActivity extends Activity {
    private static final long RELOAD_MS = 15 * 60 * 1000L;
    private static final long RETRY_MS = 30 * 1000L;
    private static final int EXIT_PRESSES = 3;
    private static final long EXIT_WINDOW_MS = 2 * 1000L;
    private static final int DEFAULT_ROTATION = 270;

    private final Handler handler = new Handler(Looper.getMainLooper());
    private WebView web;
    private RotatedFrame frame;
    private final long[] backPresses = new long[EXIT_PRESSES];
    private int backCount;
    private String url;

    private final Runnable reload = new Runnable() {
        @Override
        public void run() {
            web.loadUrl(url);
            handler.postDelayed(this, RELOAD_MS);
        }
    };

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        web = new WebView(this);
        web.setBackgroundColor(Color.BLACK);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        web.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedError(WebView view, WebResourceRequest req, WebResourceError err) {
                if (req.isForMainFrame()) {
                    handler.removeCallbacks(reload);
                    handler.postDelayed(reload, RETRY_MS);
                }
            }
        });
        frame = new RotatedFrame(this);
        frame.setBackgroundColor(Color.BLACK);
        frame.addView(web);
        setContentView(frame);

        url = resolveUrl(getIntent());
        applyRotation(getIntent());
        handler.post(reload);
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        applyRotation(intent);
        if (intent.hasExtra("url")) {
            url = resolveUrl(intent);
            handler.removeCallbacks(reload);
            handler.post(reload);
        }
    }

    private String resolveUrl(Intent intent) {
        SharedPreferences prefs = getSharedPreferences("kiosk", MODE_PRIVATE);
        String given = intent.getStringExtra("url");
        if (given != null && !given.isEmpty()) {
            prefs.edit().putString("url", given).apply();
            return given;
        }
        return prefs.getString("url", getString(R.string.default_url));
    }

    private void applyRotation(Intent intent) {
        SharedPreferences prefs = getSharedPreferences("kiosk", MODE_PRIVATE);
        if (intent.hasExtra("rotation")) {
            prefs.edit().putInt("rotation", intent.getIntExtra("rotation", DEFAULT_ROTATION)).apply();
        }
        frame.setDegrees(prefs.getInt("rotation", DEFAULT_ROTATION));
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) {
            getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY | View.SYSTEM_UI_FLAG_FULLSCREEN
                | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION);
        }
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK) {
            if (event.getRepeatCount() == 0) {
                backPresses[backCount++ % EXIT_PRESSES] = event.getEventTime();
                long oldest = backPresses[backCount % EXIT_PRESSES];
                if (backCount >= EXIT_PRESSES && event.getEventTime() - oldest <= EXIT_WINDOW_MS) {
                    finish();
                }
            }
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    @Override
    protected void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        web.destroy();
        super.onDestroy();
    }
}
